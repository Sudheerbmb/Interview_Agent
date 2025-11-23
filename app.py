import os
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from groq import Groq
from dotenv import load_dotenv
from pypdf import PdfReader
from io import BytesIO
import re
import json
import datetime

# Optional PDF export (requires reportlab)
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

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
    "selected_role": "",
    "current_question": "Introduction",
    "interview_phase": "Introduction",
    "question_count": 0,
    "all_scores": [],
    "interview_history": [],
    "started": False,
    "edge_cases_detected": [],
    "red_flags_history": [],
    "start_time": None,
    "question_times": [],
    "session_id": None
}

# In-memory session storage (in production, use database)
saved_sessions = {}

# Available interview roles with descriptions
AVAILABLE_ROLES = {
    "software_engineer": {
        "name": "Software Engineer",
        "description": "Full-stack development, algorithms, system design",
        "focus_areas": ["Programming languages", "Data structures", "System design", "API development"]
    },
    "data_scientist": {
        "name": "Data Scientist",
        "description": "Machine learning, statistical analysis, data modeling",
        "focus_areas": ["ML algorithms", "Statistics", "Data visualization", "Model evaluation"]
    },
    "product_manager": {
        "name": "Product Manager",
        "description": "Product strategy, roadmap, stakeholder management",
        "focus_areas": ["Product strategy", "User research", "Metrics", "Prioritization"]
    },
    "sales_engineer": {
        "name": "Sales Engineer",
        "description": "Technical sales, customer demos, solution architecture",
        "focus_areas": ["Technical presentation", "Customer engagement", "Solution design", "Objection handling"]
    },
    "devops_engineer": {
        "name": "DevOps Engineer",
        "description": "CI/CD, infrastructure, cloud platforms, automation",
        "focus_areas": ["CI/CD pipelines", "Cloud platforms", "Containerization", "Monitoring"]
    },
    "data_engineer": {
        "name": "Data Engineer",
        "description": "Data pipelines, ETL, data warehousing, big data",
        "focus_areas": ["ETL processes", "Data pipelines", "Data warehousing", "Big data tools"]
    },
    "frontend_engineer": {
        "name": "Frontend Engineer",
        "description": "UI/UX implementation, web frameworks, responsive design",
        "focus_areas": ["JavaScript frameworks", "CSS/HTML", "Performance optimization", "Accessibility"]
    },
    "backend_engineer": {
        "name": "Backend Engineer",
        "description": "API development, databases, microservices, scalability",
        "focus_areas": ["API design", "Database design", "Microservices", "Scalability"]
    },
    "qa_engineer": {
        "name": "QA Engineer",
        "description": "Test automation, quality assurance, bug tracking",
        "focus_areas": ["Test automation", "Testing strategies", "Bug analysis", "Quality metrics"]
    },
    "security_engineer": {
        "name": "Security Engineer",
        "description": "Cybersecurity, vulnerability assessment, security architecture",
        "focus_areas": ["Security protocols", "Vulnerability assessment", "Encryption", "Compliance"]
    },
    "ml_engineer": {
        "name": "ML Engineer",
        "description": "Machine learning systems, model deployment, MLOps",
        "focus_areas": ["ML models", "Model deployment", "Feature engineering", "MLOps"]
    },
    "cloud_architect": {
        "name": "Cloud Architect",
        "description": "Cloud infrastructure, architecture design, scalability",
        "focus_areas": ["Cloud platforms", "Architecture patterns", "Scalability", "Cost optimization"]
    }
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
    selected_role = request.form.get('role', 'software_engineer')
    
    if resume and jd:
        session_context['resume'] = extract_pdf(resume)
        session_context['jd'] = jd
        session_context['selected_role'] = selected_role
        session_context['question_count'] = 0
        session_context['all_scores'] = []
        session_context['interview_history'] = []
        session_context['started'] = False
        session_context['interview_phase'] = "Introduction"
        session_context['edge_cases_detected'] = []
        session_context['red_flags_history'] = []
        
        role_info = AVAILABLE_ROLES.get(selected_role, AVAILABLE_ROLES['software_engineer'])
        
        return jsonify({
            "status": "success",
            "message": f"Byte is ready for {role_info['name']} interview. Let's begin!",
            "role": role_info['name']
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
        
        # Add edge cases and red flags summary to feedback
        edge_cases_summary = ""
        if session_context['edge_cases_detected']:
            edge_cases_summary = f"\n\n## Edge Cases Detected ({len(session_context['edge_cases_detected'])})\n"
            edge_cases_summary += "The following off-topic questions were detected and handled:\n"
            for i, ec in enumerate(session_context['edge_cases_detected'], 1):
                edge_cases_summary += f"{i}. {ec['question']}\n"
        
        red_flags_summary = ""
        if session_context.get('red_flags_history'):
            red_flags_summary = f"\n\n## Red Flags & Critical Issues Detected ({len(session_context['red_flags_history'])})\n"
            red_flags_summary += "The following issues were identified during the interview:\n"
            memorization_count = sum(1 for rf in session_context['red_flags_history'] if rf.get('memorization_detected'))
            knowledge_gaps_count = sum(1 for rf in session_context['red_flags_history'] if rf.get('knowledge_gaps'))
            
            if memorization_count > 0:
                red_flags_summary += f"- **Memorization Detected**: {memorization_count} instances where answers appeared memorized rather than understood\n"
            if knowledge_gaps_count > 0:
                red_flags_summary += f"- **Knowledge Gaps**: {knowledge_gaps_count} instances where significant knowledge gaps were identified\n"
            
            all_red_flags = []
            for rf in session_context['red_flags_history']:
                all_red_flags.extend(rf.get('red_flags', []))
            if all_red_flags:
                red_flags_summary += f"- **Specific Red Flags**: {', '.join(set(all_red_flags[:10]))}\n"
        
        feedback = feedback + edge_cases_summary + red_flags_summary
        
        return jsonify({
            "response": feedback,
            "interview_complete": True,
            "analytics": {
                "total_questions": session_context['question_count'],
                "average_score": sum(session_context['all_scores']) / len(session_context['all_scores']) if session_context['all_scores'] else 0,
                "highest_score": max(session_context['all_scores']) if session_context['all_scores'] else 0,
                "lowest_score": min(session_context['all_scores']) if session_context['all_scores'] else 0,
                "edge_cases_count": len(session_context['edge_cases_detected'])
            },
            "debug": {
                "persona": "feedback",
                "phase": "Feedback",
                "edge_cases_detected": len(session_context['edge_cases_detected'])
            }
        })

    # Update interview history
    if user_msg and user_msg != "[SYSTEM_TIMEOUT]":
        session_context['interview_history'].append({"role": "user", "content": user_msg})

    # 1. PROFILE THE USER
    profile_data = profiler.analyze(user_msg, history)
    
    # Track edge cases explicitly
    if profile_data.get('persona') == 'edge_case' or not profile_data.get('is_relevant', True):
        edge_case_entry = {
            "question": user_msg[:200],
            "persona": profile_data.get('persona', 'edge_case'),
            "timestamp": len(session_context['interview_history']),
            "red_flags": profile_data.get('red_flags', [])
        }
        session_context['edge_cases_detected'].append(edge_case_entry)
    
    # Track red flags and memorization issues
    if profile_data.get('memorization_detected') or profile_data.get('red_flags'):
        if 'red_flags_history' not in session_context:
            session_context['red_flags_history'] = []
        session_context['red_flags_history'].append({
            "question": user_msg[:200],
            "memorization_detected": profile_data.get('memorization_detected', False),
            "red_flags": profile_data.get('red_flags', []),
            "knowledge_gaps": profile_data.get('knowledge_gaps_detected', False)
        })

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
    role_info = AVAILABLE_ROLES.get(session_context.get('selected_role', 'software_engineer'), AVAILABLE_ROLES['software_engineer'])
    raw_response = interviewer.generate_response(
        user_msg,
        history,
        session_context['resume'],
        session_context['jd'],
        profile_data,
        grader_data,
        session_context['interview_phase'],
        session_context['question_count'],
        role_info
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
            "communication_quality": profile_data.get('communication_quality', 'good'),
            "is_edge_case": profile_data.get('persona') == 'edge_case' or not profile_data.get('is_relevant', True),
            "edge_cases_count": len(session_context['edge_cases_detected']),
            "memorization_detected": profile_data.get('memorization_detected', False) or grader_data.get('memorization_detected', False),
            "red_flags": profile_data.get('red_flags', []) + grader_data.get('red_flags', []),
            "knowledge_gaps": profile_data.get('knowledge_gaps_detected', False),
            "authenticity_score": profile_data.get('authenticity_score', 0.7),
            "specificity_score": profile_data.get('specificity_score', 0.7)
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
    
    # Add edge cases summary to feedback
    if session_context['edge_cases_detected']:
        edge_cases_summary = f"\n\n## Edge Cases Detected ({len(session_context['edge_cases_detected'])})\n"
        edge_cases_summary += "The following off-topic questions were detected and handled:\n"
        for i, ec in enumerate(session_context['edge_cases_detected'], 1):
            edge_cases_summary += f"{i}. {ec['question']}\n"
        feedback = feedback + edge_cases_summary
    
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
            },
            "edge_cases_count": len(session_context['edge_cases_detected'])
        }
    })


@app.route('/reset', methods=['POST'])
def reset():
    """Reset interview session."""
    session_context['resume'] = ""
    session_context['jd'] = ""
    session_context['selected_role'] = ""
    session_context['current_question'] = "Introduction"
    session_context['interview_phase'] = "Introduction"
    session_context['question_count'] = 0
    session_context['all_scores'] = []
    session_context['interview_history'] = []
    session_context['started'] = False
    session_context['edge_cases_detected'] = []
    session_context['red_flags_history'] = []
    
    return jsonify({"status": "success", "message": "Session reset"})

@app.route('/get-roles', methods=['GET'])
def get_roles():
    """Get available interview roles."""
    return jsonify({
        "roles": {k: {"name": v["name"], "description": v["description"]} for k, v in AVAILABLE_ROLES.items()}
    })

@app.route('/save-session', methods=['POST'])
def save_session():
    """Save current interview session."""
    try:
        session_id = request.json.get('session_id') or f"session_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        session_data = {
            "session_id": session_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "role": session_context.get('selected_role', ''),
            "resume": session_context.get('resume', '')[:500],  # Store summary
            "jd": session_context.get('jd', '')[:500],
            "question_count": session_context.get('question_count', 0),
            "all_scores": session_context.get('all_scores', []),
            "average_score": sum(session_context.get('all_scores', [])) / len(session_context.get('all_scores', [])) if session_context.get('all_scores') else 0,
            "interview_history": session_context.get('interview_history', [])[-50:],  # Last 50 messages
            "edge_cases_count": len(session_context.get('edge_cases_detected', [])),
            "duration": sum(session_context.get('question_times', [])) if session_context.get('question_times') else 0
        }
        saved_sessions[session_id] = session_data
        return jsonify({"status": "success", "session_id": session_id, "message": "Session saved successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/load-session/<session_id>', methods=['GET'])
def load_session(session_id):
    """Load a saved interview session."""
    if session_id in saved_sessions:
        return jsonify({"status": "success", "session": saved_sessions[session_id]})
    return jsonify({"status": "error", "message": "Session not found"}), 404

@app.route('/list-sessions', methods=['GET'])
def list_sessions():
    """List all saved sessions."""
    sessions_list = [
        {
            "session_id": sid,
            "timestamp": data.get('timestamp', ''),
            "role": data.get('role', ''),
            "question_count": data.get('question_count', 0),
            "average_score": data.get('average_score', 0),
            "duration": data.get('duration', 0)
        }
        for sid, data in saved_sessions.items()
    ]
    sessions_list.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    return jsonify({"status": "success", "sessions": sessions_list})

@app.route('/export-pdf', methods=['POST'])
def export_pdf():
    """Export interview feedback as PDF."""
    if not PDF_AVAILABLE:
        return jsonify({"status": "error", "message": "PDF export requires reportlab library. Install with: pip install reportlab"}), 500
    try:
        data = request.json
        feedback_text = data.get('feedback', '')
        analytics = data.get('analytics', {})
        role = data.get('role', 'Interview')
        
        # Create PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=18)
        story = []
        
        # Styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#9333ea'),
            spaceAfter=30,
            alignment=TA_CENTER
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#a855f7'),
            spaceAfter=12
        )
        
        # Title
        story.append(Paragraph(f"{role} Interview Feedback Report", title_style))
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph(f"Generated on {datetime.datetime.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Analytics Summary
        if analytics:
            story.append(Paragraph("Performance Summary", heading_style))
            summary_data = [
                ['Metric', 'Value'],
                ['Total Questions', str(analytics.get('total_questions', 0))],
                ['Average Score', f"{analytics.get('average_score', 0):.1f}%"],
                ['Highest Score', f"{analytics.get('highest_score', 0):.1f}%"],
                ['Lowest Score', f"{analytics.get('lowest_score', 0):.1f}%"],
            ]
            if analytics.get('edge_cases_count', 0) > 0:
                summary_data.append(['Edge Cases Detected', str(analytics.get('edge_cases_count', 0))])
            
            summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#9333ea')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#1f2937')),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#4b5563')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#1f2937'), colors.HexColor('#111827')])
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 0.3*inch))
        
        # Feedback Content
        story.append(Paragraph("Detailed Feedback", heading_style))
        # Simple text formatting for feedback
        feedback_paragraphs = feedback_text.split('\n\n')
        for para in feedback_paragraphs:
            if para.strip():
                # Remove markdown formatting for PDF
                clean_para = para.replace('**', '').replace('#', '').replace('|', ' ')
                if clean_para.strip().startswith('##'):
                    clean_para = clean_para.replace('##', '').strip()
                    story.append(Paragraph(clean_para, heading_style))
                elif clean_para.strip().startswith('#'):
                    clean_para = clean_para.replace('#', '').strip()
                    story.append(Paragraph(clean_para, heading_style))
                else:
                    story.append(Paragraph(clean_para, styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'interview-feedback-{datetime.datetime.now().strftime("%Y%m%d")}.pdf'
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/get-learning-resources', methods=['POST'])
def get_learning_resources():
    """Generate AI-powered learning resource recommendations based on interview performance."""
    try:
        data = request.json
        scores = data.get('scores', [])
        feedback = data.get('feedback', '')
        role = data.get('role', '')
        
        # Analyze gaps and generate recommendations
        avg_score = sum(scores) / len(scores) if scores else 0
        weak_areas = []
        
        if avg_score < 60:
            weak_areas.append("Fundamental concepts")
        if any(s < 50 for s in scores):
            weak_areas.append("Core technical skills")
        
        # Generate recommendations using AI
        prompt = f"""Based on this interview performance:
- Role: {role}
- Average Score: {avg_score:.1f}%
- Feedback: {feedback[:500]}

Generate 5-7 specific, actionable learning resources (courses, books, practice platforms) that would help improve performance. Format as JSON with: title, type (course/book/platform), description, url (if applicable), priority (high/medium/low).
"""
        
        completion = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": "You are a learning advisor. Provide specific, actionable learning resource recommendations."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )
        
        resources = json.loads(completion.choices[0].message.content)
        return jsonify({"status": "success", "resources": resources})
    except Exception as e:
        # Fallback recommendations
        return jsonify({
            "status": "success",
            "resources": {
                "recommendations": [
                    {"title": "LeetCode", "type": "platform", "description": "Practice coding problems", "priority": "high"},
                    {"title": "System Design Interview", "type": "book", "description": "Learn system design concepts", "priority": "medium"}
                ]
            }
        })


if __name__ == '__main__':
    app.run(debug=True, port=5000)
