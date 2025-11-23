import os

from flask import Flask, render_template, request, jsonify

from flask_cors import CORS

from groq import Groq

from dotenv import load_dotenv

from pypdf import PdfReader

from io import BytesIO



# Import Agents

from agents.profiler import ProfilerAgent

from agents.grader import GraderAgent

from agents.interviewer import InterviewerAgent



load_dotenv()

app = Flask(__name__)

CORS(app)



client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

profiler = ProfilerAgent(client)

grader = GraderAgent(client)

interviewer = InterviewerAgent(client)



# Simple in-memory storage (Use Redis/DB in production)

session_context = {

    "resume": "",

    "jd": "",

    "current_question": "Introduction"

}



def extract_pdf(file):

    reader = PdfReader(BytesIO(file.read()))

    return "".join([p.extract_text() for p in reader.pages])



@app.route('/')

def home():

    return render_template('index.html')



@app.route('/upload-context', methods=['POST'])

def upload():

    resume = request.files.get('resume')

    jd = request.form.get('jd')

    if resume and jd:

        session_context['resume'] = extract_pdf(resume)

        session_context['jd'] = jd

        return jsonify({"status": "success", "message": "Byte is ready."})

    return jsonify({"error": "Missing inputs"}), 400



@app.route('/chat', methods=['POST'])

def chat():

    data = request.json

    user_msg = data.get('message')

    history = data.get('history', [])



    # 1. PROFILE THE USER

    # Detects: Chatty, Confused, Efficient, Edge Case, or Silent

    profile_data = profiler.analyze(user_msg, history)



    # 2. GRADE THE ANSWER (Only if relevant & not silent)

    grader_data = {}

    if profile_data['is_relevant'] and profile_data['persona'] != 'silent':

        grader_data = grader.evaluate(user_msg, session_context['current_question'], session_context['jd'])



    # 3. GENERATE RESPONSE

    # Uses the System Prompt to synthesize A & B

    raw_response = interviewer.generate_response(

        user_msg,

        history,

        session_context['resume'],

        session_context['jd'],

        profile_data,

        grader_data

    )

   

    # Store current question for next turn's context (Naive extraction)

    session_context['current_question'] = raw_response[-100:]



    return jsonify({

        "response": raw_response,

        "debug": {

            "persona": profile_data['persona'],

            "score": grader_data.get('score', 'N/A'),

            "follow_up": grader_data.get('requires_followup', False)

        }

    })



if __name__ == '__main__':

    app.run(debug=True, port=5000)