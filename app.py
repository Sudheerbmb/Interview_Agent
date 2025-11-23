import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from groq import Groq
from dotenv import load_dotenv
from pypdf import PdfReader
from io import BytesIO
import re

# Import Agents
from agents.profiler import ProfilerAgent
from agents.grader import GraderAgent
from agents.interviewer import InterviewerAgent
from agents.feedback_generator import FeedbackGeneratorAgent

load_dotenv()

app = Flask(__name__)
CORS(app)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Initialize all agents
profiler = ProfilerAgent(client)
grader = GraderAgent(client)
interviewer = InterviewerAgent(client)
feedback_generator = FeedbackGeneratorAgent(client)

# Enhanced session context with state tracking
session_context = {
    "resume": "",
    "jd": "",
    "current_question": "Introduction",
    "interview_phase": "Introduction",
    "question_count": 0,
    "all_scores": [],
    "interview_history": [],
    "started": False
}


def extract_pdf(file):
    reader = PdfReader(BytesIO(file.read()))
    return "".join([p.extract_text() for p in reader.pages])


def determine_interview_phase(question_count):
    """Determine interview phase based on question count."""
    if question_count == 0:
        return "Introduction"
    elif question_count <= 3:
        return "Technical"
    elif question_count <= 6:
        return "Behavioral"
    elif question_count <= 9:
        return "Deep_Dive"
    else:
        return "Feedback"


def check_interview_end(user_msg, question_count):
    """Check if user wants to end the interview."""
    end_phrases = [
        "end interview", "finish interview", "conclude interview",
        "that's all", "i'm done", "wrap up", "get feedback",
        "show feedback", "interview complete"
    ]
    user_lower = user_msg.lower()
    return any(phrase in user_lower for phrase in end_phrases) or question_count >= 12


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
        session_context['question_count'] = 0
        session_context['all_scores'] = []
        session_context['interview_history'] = []
        session_context['started'] = False
        session_context['interview_phase'] = "Introduction"
        
        return jsonify({
            "status": "success",
            "message": "Byte is ready. Let's begin your interview!"
        })
    
    return jsonify({"error": "Missing inputs"}), 400


@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_msg = data.get('message', '')
    history = data.get('history', [])

    # Check if interview should end
    should_end = check_interview_end(user_msg, session_context['question_count'])
    
    if should_end and session_context['question_count'] > 0:
        # Generate comprehensive feedback
        feedback = feedback_generator.generate_comprehensive_feedback(
            session_context['interview_history'],
            session_context['resume'],
            session_context['jd'],
            session_context['all_scores'],
            session_context['question_count']
        )
        
        return jsonify({
            "response": feedback,
            "interview_complete": True,
            "analytics": {
                "total_questions": session_context['question_count'],
                "average_score": sum(session_context['all_scores']) / len(session_context['all_scores']) if session_context['all_scores'] else 0,
                "highest_score": max(session_context['all_scores']) if session_context['all_scores'] else 0,
                "lowest_score": min(session_context['all_scores']) if session_context['all_scores'] else 0
            },
            "debug": {
                "persona": "feedback",
                "phase": "Feedback"
            }
        })

    # Update interview history
    if user_msg and user_msg != "[SYSTEM_TIMEOUT]":
        session_context['interview_history'].append({"role": "user", "content": user_msg})

    # 1. PROFILE THE USER
    profile_data = profiler.analyze(user_msg, history)

    # 2. GRADE THE ANSWER (Only if relevant & not silent)
    grader_data = {}
    if profile_data['is_relevant'] and profile_data['persona'] != 'silent' and session_context['started']:
        grader_data = grader.evaluate(
            user_msg,
            session_context['current_question'],
            session_context['jd'],
            session_context['resume'],
            session_context['all_scores']  # Pass previous scores for trend analysis
        )
        
        # Store score
        if 'score' in grader_data:
            session_context['all_scores'].append(grader_data['score'])

    # 3. GENERATE RESPONSE
    raw_response = interviewer.generate_response(
        user_msg,
        history,
        session_context['resume'],
        session_context['jd'],
        profile_data,
        grader_data,
        session_context['interview_phase'],
        session_context['question_count']
    )

    # Extract response text (remove analysis section for storage)
    response_text = raw_response
    if "[RESPONSE]" in raw_response:
        response_text = raw_response.split("[RESPONSE]")[-1].strip()
    
    # Update interview state
    if session_context['started'] or (user_msg and user_msg != "[SYSTEM_TIMEOUT]"):
        session_context['started'] = True
        # Increment question count if this is a new question (not a follow-up)
        if profile_data.get('persona') != 'silent' and not grader_data.get('requires_followup', False):
            session_context['question_count'] += 1
            session_context['interview_phase'] = determine_interview_phase(session_context['question_count'])
    
    # Store current question for next turn's context
    session_context['current_question'] = response_text[:200]
    
    # Update interview history
    session_context['interview_history'].append({"role": "assistant", "content": raw_response})

    # Enhanced debug information
    return jsonify({
        "response": raw_response,
        "interview_complete": False,
        "debug": {
            "persona": profile_data.get('persona', 'normal'),
            "score": grader_data.get('score', 'N/A'),
            "follow_up": grader_data.get('requires_followup', False),
            "phase": session_context['interview_phase'],
            "question_count": session_context['question_count'],
            "average_score": sum(session_context['all_scores']) / len(session_context['all_scores']) if session_context['all_scores'] else 'N/A',
            "confidence": profile_data.get('confidence', 'medium'),
            "communication_quality": profile_data.get('communication_quality', 'good')
        },
        "analytics": {
            "total_questions": session_context['question_count'],
            "scores": session_context['all_scores'],
            "trend": "improving" if len(session_context['all_scores']) > 1 and session_context['all_scores'][-1] > session_context['all_scores'][0] else "stable"
        } if session_context['all_scores'] else {}
    })


@app.route('/get-feedback', methods=['POST'])
def get_feedback():
    """Explicit endpoint to generate feedback at any time."""
    if session_context['question_count'] == 0:
        return jsonify({"error": "No interview conducted yet"}), 400
    
    feedback = feedback_generator.generate_comprehensive_feedback(
        session_context['interview_history'],
        session_context['resume'],
        session_context['jd'],
        session_context['all_scores'],
        session_context['question_count']
    )
    
    return jsonify({
        "feedback": feedback,
        "analytics": {
            "total_questions": session_context['question_count'],
            "average_score": sum(session_context['all_scores']) / len(session_context['all_scores']) if session_context['all_scores'] else 0,
            "highest_score": max(session_context['all_scores']) if session_context['all_scores'] else 0,
            "lowest_score": min(session_context['all_scores']) if session_context['all_scores'] else 0,
            "score_distribution": {
                "excellent": len([s for s in session_context['all_scores'] if s >= 90]),
                "good": len([s for s in session_context['all_scores'] if 70 <= s < 90]),
                "satisfactory": len([s for s in session_context['all_scores'] if 50 <= s < 70]),
                "needs_improvement": len([s for s in session_context['all_scores'] if s < 50])
            }
        }
    })


@app.route('/reset', methods=['POST'])
def reset():
    """Reset interview session."""
    session_context['resume'] = ""
    session_context['jd'] = ""
    session_context['current_question'] = "Introduction"
    session_context['interview_phase'] = "Introduction"
    session_context['question_count'] = 0
    session_context['all_scores'] = []
    session_context['interview_history'] = []
    session_context['started'] = False
    
    return jsonify({"status": "success", "message": "Session reset"})


if __name__ == '__main__':
    app.run(debug=True, port=5000)
