#
import os
import random
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from groq import Groq
from dotenv import load_dotenv
from pypdf import PdfReader
from io import BytesIO
import re
import json
import datetime
import io
import sys

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
    # Structured Q/A log for analytics + transcript export
    # Each entry: {question_id, phase, question, answer, score, persona, is_edge_case, timestamp_iso}
    "qa_log": [],
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

QUESTION_BANK = {
    "dsa": [
        {
            "id": "dsa_two_sum",
            "title": "Two Sum",
            "difficulty": "Easy",
            "prompt": "You are given an integer array nums and an integer target. Your task is to return the indices of the two numbers such that they add up to target.\n\nInput:\n- nums: an array of integers (can contain positive, negative, and zero values)\n- target: an integer\n\nOutput:\n- A pair of indices [i, j] (0-based) such that nums[i] + nums[j] = target and i != j.\n\nConstraints:\n- 2 <= nums.length <= 10^5\n- -10^9 <= nums[i], target <= 10^9\n- There will always be exactly one solution.\n- You may not use the same element twice.\n\nExamples:\n1) Input: nums = [2,7,11,15], target = 9\n   Output: [0,1]\n   Explanation: nums[0] + nums[1] = 2 + 7 = 9.\n\n2) Input: nums = [3,2,4], target = 6\n   Output: [1,2]\n\n3) Input: nums = [3,3], target = 6\n   Output: [0,1]\n\nVisible test cases:\n- Small arrays with positive numbers\n- Arrays with negative and positive numbers\n- Arrays with duplicate values\n\nHidden test cases:\n- Large arrays to test O(n) vs O(n^2)\n- Edge values near -10^9 and 10^9\n\nYour solution will be tested against multiple visible and hidden cases. Aim for an O(n) time solution using a hash map.",
            "tags": ["Array", "Hash Table"],
            "python_signature": "def two_sum(nums, target):",
            "python_tests": [
                {"id": 1, "input": {"nums": [2, 7, 11, 15], "target": 9}, "expected": [0, 1]},
                {"id": 2, "input": {"nums": [3, 2, 4], "target": 6}, "expected": [1, 2]},
                {"id": 3, "input": {"nums": [3, 3], "target": 6}, "expected": [0, 1]}
            ]
        },
        {
            "id": "dsa_reverse_linked_list",
            "title": "Reverse Linked List",
            "difficulty": "Easy",
            "prompt": "Given the head of a singly linked list, reverse the list and return the head of the reversed list.\n\nInput:\n- A singly linked list head where each node has: val (int), next (pointer to next node or null).\n\nOutput:\n- The new head of the reversed linked list.\n\nConstraints:\n- The number of nodes in the list is in the range [0, 5 * 10^4].\n- -10^5 <= Node.val <= 10^5.\n\nExamples:\n1) Input: 1 -> 2 -> 3 -> 4 -> 5 -> null\n   Output: 5 -> 4 -> 3 -> 2 -> 1 -> null\n\n2) Input: 1 -> 2 -> null\n   Output: 2 -> 1 -> null\n\n3) Input: null\n   Output: null\n\nVisible test cases:\n- Short lists (length 0, 1, 2)\n- Lists with increasing values\n\nHidden test cases:\n- Long lists (5 * 10^4 nodes)\n- Values with negatives and duplicates\n\nYour solution will be executed against multiple test cases; prefer an iterative O(n) time, O(1) space approach.",
            "tags": ["Linked List"],
            "python_signature": "def reverse_list(head):",
            "python_tests": [
                {
                    "id": 1,
                    "input": {"head": [1, 2, 3, 4, 5]},
                    "expected": [5, 4, 3, 2, 1]
                },
                {
                    "id": 2,
                    "input": {"head": [1, 2]},
                    "expected": [2, 1]
                },
                {
                    "id": 3,
                    "input": {"head": []},
                    "expected": []
                }
            ]
        },
        {
            "id": "dsa_longest_substring",
            "title": "Longest Substring Without Repeating Characters",
            "difficulty": "Medium",
            "prompt": "Given a string s, return the length of the longest substring without repeating characters.\n\nInput:\n- s: a string consisting of English letters, digits, symbols, and spaces.\n\nOutput:\n- An integer representing the maximum length of a substring of s that contains no repeated characters.\n\nConstraints:\n- 0 <= s.length <= 5 * 10^4\n- s may contain any printable ASCII characters.\n\nExamples:\n1) Input: s = \"abcabcbb\"\n   Output: 3\n   Explanation: The answer is \"abc\", with the length of 3.\n\n2) Input: s = \"bbbbb\"\n   Output: 1\n   Explanation: The answer is \"b\".\n\n3) Input: s = \"pwwkew\"\n   Output: 3\n   Explanation: The answer is \"wke\".\n\nVisible test cases:\n- Empty string\n- Strings with all unique characters\n- Strings with all same characters\n\nHidden test cases:\n- Long strings (length ~50k)\n- Mix of letters, digits, and symbols\n\nThe judge will run multiple visible and hidden tests; an optimal solution should be O(n) using a sliding window.",
            "tags": ["String", "Sliding Window"],
            "python_signature": "def length_of_longest_substring(s):",
            "python_tests": [
                {"id": 1, "input": {"s": "abcabcbb"}, "expected": 3},
                {"id": 2, "input": {"s": "bbbbb"}, "expected": 1},
                {"id": 3, "input": {"s": "pwwkew"}, "expected": 3}
            ]
        },
        {
            "id": "dsa_merge_intervals",
            "title": "Merge Intervals",
            "difficulty": "Medium",
            "prompt": "You are given an array of intervals where intervals[i] = [start_i, end_i], representing the start and end of an interval on the real number line. Your task is to merge all overlapping intervals and return an array of the non-overlapping intervals that cover all the intervals in the input.\n\nInput:\n- intervals: a list of intervals where each interval is a two-element list [start_i, end_i]\n\nOutput:\n- A new list of intervals where all overlapping intervals are merged.\n- The result should be sorted by start time.\n\nConstraints:\n- 0 <= intervals.length <= 10^4\n- -10^5 <= start_i <= end_i <= 10^5\n\nExamples:\n1) Input: intervals = [[1,3],[2,6],[8,10],[15,18]]\n   Output: [[1,6],[8,10],[15,18]]\n   Explanation: [1,3] and [2,6] overlap and are merged into [1,6].\n\n2) Input: intervals = [[1,4],[4,5]]\n   Output: [[1,5]]\n   Explanation: Intervals that just touch at endpoints are considered overlapping.\n\n3) Input: intervals = []\n   Output: []\n\nVisible test cases:\n- No intervals\n- Intervals that do not overlap\n- Intervals that all overlap into a single large interval\n\nHidden test cases:\n- Large number of intervals (up to 10^4)\n- Intervals with negative values\n\nAn optimal solution should run in O(n log n) time due to sorting, with O(1) or O(n) extra space depending on implementation.",
            "tags": ["Array", "Sorting"],
            "python_signature": "def merge(intervals):",
            "python_tests": [
                {"id": 1, "input": {"intervals": [[1,3],[2,6],[8,10],[15,18]]}, "expected": [[1,6],[8,10],[15,18]]},
                {"id": 2, "input": {"intervals": [[1,4],[4,5]]}, "expected": [[1,5]]},
                {"id": 3, "input": {"intervals": []}, "expected": []}
            ]
        },
        {
            "id": "dsa_max_subarray",
            "title": "Maximum Subarray",
            "difficulty": "Easy",
            "prompt": "Given an integer array nums, find the contiguous subarray (containing at least one number) which has the largest sum and return its sum.\n\nInput:\n- nums: an array of integers (can be positive, negative, or zero)\n\nOutput:\n- An integer representing the maximum possible sum of any non-empty contiguous subarray of nums.\n\nConstraints:\n- 1 <= nums.length <= 10^5\n- -10^4 <= nums[i] <= 10^4\n\nExamples:\n1) Input: nums = [-2,1,-3,4,-1,2,1,-5,4]\n   Output: 6\n   Explanation: The subarray [4,-1,2,1] has the largest sum = 6.\n\n2) Input: nums = [1]\n   Output: 1\n\n3) Input: nums = [5,4,-1,7,8]\n   Output: 23\n\nVisible test cases:\n- All positive numbers\n- All negative numbers\n- Mix of positive and negative\n\nHidden test cases:\n- Large arrays (length ~10^5)\n- Edge cases where the best subarray is at the beginning or end of the array\n\nAn optimal solution should run in O(n) time using Kadane's algorithm and O(1) extra space.",
            "tags": ["Array", "Dynamic Programming"],
            "python_signature": "def max_sub_array(nums):",
            "python_tests": [
                {"id": 1, "input": {"nums": [-2,1,-3,4,-1,2,1,-5,4]}, "expected": 6},
                {"id": 2, "input": {"nums": [1]}, "expected": 1},
                {"id": 3, "input": {"nums": [5,4,-1,7,8]}, "expected": 23}
            ]
        },
    ],
    "sql": [
        {
            "id": "sql_top_earners",
            "title": "Top Earners by Department",
            "difficulty": "Easy",
            "prompt": "You are given two tables:\n\n1) Employees(emp_id, name, salary, dept_id)\n2) Departments(dept_id, dept_name)\n\nWrite an SQL query to return the highest-paid employee in each department.\n\nOutput columns:\n- dept_name\n- emp_id\n- name\n- salary\n\nRequirements:\n- If multiple employees in a department share the same highest salary, return all of them.\n- Order the result by dept_name ascending, then salary descending.\n\nExample:\nEmployees:\nemp_id | name   | salary | dept_id\n1      | Alice  | 100000 | 10\n2      | Bob    | 120000 | 10\n3      | Carol  | 90000  | 20\n\nDepartments:\ndept_id | dept_name\n10      | Engineering\n20      | Marketing\n\nOutput:\ndept_name   | emp_id | name  | salary\nEngineering | 2      | Bob   | 120000\nMarketing   | 3      | Carol | 90000\n\nVisible test cases:\n- Departments with a single employee\n- Departments with multiple employees and a clear single top earner\n\nHidden test cases:\n- Departments where multiple employees tie for top salary\n- Departments with no employees (should they show up or not?)",
            "tags": ["JOIN", "Aggregation"]
        },
        {
            "id": "sql_user_retention",
            "title": "User Retention",
            "difficulty": "Medium",
            "prompt": "You are given a table logins(user_id, login_date) where each row represents a login event by a user on a specific date.\n\nTask:\nWrite an SQL query to calculate, for each calendar week, the percentage of users who logged in on two or more distinct days within that week.\n\nAssumptions:\n- login_date is a DATE (or TIMESTAMP) column.\n- A \"week\" can be assumed to start on Monday (use your SQL dialect's week function accordingly).\n\nOutput columns:\n- week_start_date (or week identifier)\n- total_users_in_week\n- users_with_2plus_days\n- retention_percentage (users_with_2plus_days / total_users_in_week * 100)\n\nVisible test cases:\n- Weeks with only one login per user\n- Weeks where some users log in many times\n\nHidden test cases:\n- Multiple months of data spanning many weeks\n- Users active in multiple weeks\n\nYour solution should use aggregation and (optionally) window functions to compute the weekly retention percentage.",
            "tags": ["Window Functions", "Aggregation"]
        },
    ],
    "ml": [
        {
            "id": "ml_binary_classifier",
            "title": "Binary Classification Pipeline",
            "difficulty": "Medium",
            "prompt": "You are given a CSV dataset with customer features and a binary target label churn (0 = did not churn, 1 = churned).\n\nInput:\n- A table with columns such as: customer_id, age, tenure, monthly_charges, total_charges, contract_type, payment_method, etc.\n- A binary target column churn (0/1).\n\nTask:\nDesign and (if possible) implement a scikit-learn pipeline that:\n1) Performs preprocessing:\n   - Handles missing values.\n   - Encodes categorical variables (e.g., OneHotEncoder).\n   - Scales numerical features (e.g., StandardScaler).\n2) Trains a binary classifier (e.g., LogisticRegression, RandomForestClassifier, or XGBoost).\n3) Evaluates the model using ROC-AUC on a hold-out validation set.\n4) Persists the trained model to disk (e.g., using joblib or pickle).\n\nYou should explain:\n- How you would split the data (train/validation/test).\n- Which metrics you monitor (ROC-AUC, precision, recall, etc.).\n- How you would handle class imbalance if it exists.\n\nVisible test cases:\n- Balanced dataset with clean features\n\nHidden test cases:\n- Imbalanced dataset\n- Missing values and unseen categories in validation set",
            "tags": ["scikit-learn", "Classification"]
        },
        {
            "id": "ml_model_selection",
            "title": "Model Selection for Imbalanced Data",
            "difficulty": "Medium",
            "prompt": "You are working on a fraud detection problem where only ~1% of transactions are fraudulent.\n\nTask:\nExplain and, if possible, implement how you would:\n1) Explore and preprocess the data.\n2) Handle the heavy class imbalance (e.g., class weights, SMOTE, undersampling).\n3) Choose and tune models (e.g., tree-based models, gradient boosting).\n4) Evaluate performance with appropriate metrics (e.g., ROC-AUC, PR-AUC, recall at fixed precision).\n5) Avoid data leakage and ensure your evaluation is reliable (cross-validation, time-based splits if needed).\n\nVisible test cases:\n- Synthetic dataset with moderate imbalance\n\nHidden test cases:\n- More extreme imbalance\n- Noisy features requiring regularization or feature selection",
            "tags": ["Imbalanced Data", "Evaluation"]
        },
    ],
    "data_analysis": [
        {
            "id": "da_sales_insights",
            "title": "Sales Insights Dashboard",
            "difficulty": "Easy",
            "prompt": "You are given a transactional sales dataset with columns:\n- order_id\n- customer_id\n- order_date\n- product\n- category\n- amount (numeric)\n\nTask:\nDescribe and, if possible, implement in Python (using pandas) an analysis that computes:\n1) Monthly revenue trend (total revenue per calendar month).\n2) Top 5 products by total revenue.\n3) Repeat-customer rate (percentage of customers with 2 or more orders).\n\nYou should outline:\n- How you would parse dates and handle time zones if needed.\n- How you would deal with missing or inconsistent data.\n- How you would visualize the results (e.g., line charts, bar charts).\n\nVisible test cases:\n- Small dataset spanning a few months\n\nHidden test cases:\n- Larger dataset with thousands of rows\n- Edge cases like customers with only one big order vs many small ones",
            "tags": ["Pandas", "Aggregation"]
        },
        {
            "id": "da_ab_test",
            "title": "A/B Test Analysis",
            "difficulty": "Medium",
            "prompt": "You ran an A/B test on a website to compare variant A (control) and variant B (treatment).\n\nYou have a table with columns:\n- user_id\n- group (\"A\" or \"B\")\n- conversion_flag (0/1)\n\nTask:\nDescribe and, if possible, implement how you would analyze whether variant B is significantly better than A.\nYour answer should cover:\n1) How you would explore the data (sample sizes, conversion rates per group).\n2) Which statistical test you would use (e.g., z-test for proportions) and why.\n3) How you would compute confidence intervals for the lift.\n4) How you would handle multiple tests, if any.\n5) How you would interpret practical vs statistical significance.\n\nVisible test cases:\n- Balanced sample sizes\n- Clear difference in conversion rates\n\nHidden test cases:\n- Unbalanced groups\n- Very small effect sizes requiring careful interpretation",
            "tags": ["Statistics", "Experimentation"]
        },
    ],
}

SKILL_KEYWORDS = {
    "Data structures": ["array", "linked list", "stack", "queue", "tree", "graph", "heap", "hash", "trie"],
    "Algorithms": ["big-o", "complexity", "dp", "dynamic programming", "greedy", "bfs", "dfs", "dijkstra", "sorting", "search"],
    "System design": ["scale", "scalable", "load balancer", "cache", "redis", "queue", "kafka", "database", "sharding", "replication", "latency", "throughput", "microservice"],
    "APIs": ["api", "rest", "graphql", "endpoint", "http", "authentication", "oauth", "jwt", "rate limit"],
    "Databases": ["sql", "postgres", "mysql", "index", "transaction", "acid", "join", "query", "normalization", "nosql", "mongodb"],
    "ML": ["model", "training", "overfitting", "feature", "cross-validation", "auc", "f1", "precision", "recall", "rmse", "classification", "regression"],
    "Statistics": ["p-value", "hypothesis", "distribution", "variance", "bias", "confidence interval", "bayes", "correlation"],
    "Data visualization": ["dashboard", "plot", "chart", "matplotlib", "seaborn", "tableau", "power bi"],
    "Behavioral (STAR)": ["situation", "task", "action", "result", "conflict", "leadership", "failure", "stakeholder"],
    "DevOps/Cloud": ["ci/cd", "pipeline", "docker", "kubernetes", "terraform", "aws", "gcp", "azure", "monitoring", "logging"],
}


def infer_skills_from_question(question_text, role_info):
    if not question_text:
        return []
    q = question_text.lower()
    hits = []
    for skill, kws in SKILL_KEYWORDS.items():
        if any(kw in q for kw in kws):
            hits.append(skill)
    # Light biasing toward role focus areas if no keyword hit
    if not hits and role_info and role_info.get("focus_areas"):
        hits = role_info["focus_areas"][:1]
    return hits[:3]


def compute_skill_breakdown(qa_log):
    buckets = {}
    for entry in qa_log or []:
        score = entry.get("score")
        for skill in entry.get("skills", []) or []:
            b = buckets.setdefault(skill, {"count": 0, "scores": []})
            b["count"] += 1
            if isinstance(score, (int, float)):
                b["scores"].append(float(score))
    # Convert to avg
    breakdown = {}
    for skill, b in buckets.items():
        scores = b["scores"]
        breakdown[skill] = {
            "count": b["count"],
            "average_score": (sum(scores) / len(scores)) if scores else 0,
        }
    return breakdown


def get_coding_category_for_role(role_key: str) -> str:
    if role_key in ["software_engineer", "backend_engineer", "frontend_engineer", "devops_engineer", "qa_engineer", "security_engineer"]:
        return "dsa"
    if role_key in ["data_scientist", "ml_engineer"]:
        return "ml"
    if role_key in ["data_engineer", "cloud_architect"]:
        return "sql"
    # Default fallback
    return "dsa"


def pick_coding_question(role_key: str):
    category = get_coding_category_for_role(role_key)
    questions = QUESTION_BANK.get(category, [])
    if not questions:
        return category, None
    return category, random.choice(questions)

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
    wants_to_end = any(phrase in user_lower for phrase in end_phrases)
    
    # Hard cap: automatically end after 15 questions
    if question_count >= 15:
        return True
    
    # Allow manual end only after at least 10 questions
    if wants_to_end and question_count >= 10:
        return True
    
    return False


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
        session_context['qa_log'] = []
        session_context['started'] = False
        session_context['interview_phase'] = "Introduction"
        session_context['edge_cases_detected'] = []
        session_context['red_flags_history'] = []
        session_context['coding_round'] = None
        
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
        
        # Log the Q/A (this answer corresponds to the previously asked question)
        role_info = AVAILABLE_ROLES.get(session_context.get('selected_role', 'software_engineer'), AVAILABLE_ROLES['software_engineer'])
        session_context['qa_log'].append({
            "question_id": session_context['question_count'],
            "phase": session_context.get('interview_phase', 'Introduction'),
            "question": session_context.get('current_question', ''),
            "answer": user_msg,
            "score": grader_data.get('score'),
            "persona": profile_data.get('persona', 'normal'),
            "is_edge_case": profile_data.get('persona') == 'edge_case' or not profile_data.get('is_relevant', True),
            "skills": infer_skills_from_question(session_context.get('current_question', ''), role_info),
            "timestamp_iso": datetime.datetime.now().isoformat(),
        })

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
    # Always compute analytics so the dashboard can update every question
    analytics = {
        "total_questions": session_context['question_count'],
        "scores": session_context['all_scores'],
        "average_score": (
            sum(session_context['all_scores']) / len(session_context['all_scores'])
            if session_context['all_scores'] else 0
        ),
        "highest_score": max(session_context['all_scores']) if session_context['all_scores'] else 0,
        "lowest_score": min(session_context['all_scores']) if session_context['all_scores'] else 0,
        "edge_cases_count": len(session_context['edge_cases_detected']),
        "trend": (
            "improving"
            if len(session_context['all_scores']) > 1
            and session_context['all_scores'][-1] > session_context['all_scores'][0]
            else "stable"
        ) if session_context['all_scores'] else "baseline",
        "skill_breakdown": compute_skill_breakdown(session_context.get('qa_log', [])),
    }

    return jsonify({
        "response": raw_response,
        "interview_complete": False,
        "coach": {
            "strengths": grader_data.get("strengths", []) if grader_data else [],
            "improvements": grader_data.get("improvements", []) if grader_data else [],
            "followup_suggestions": grader_data.get("followup_suggestions", []) if grader_data else [],
        },
        "debug": {
            "persona": profile_data.get('persona', 'normal'),
            "score": grader_data.get('score', 'N/A'),
            "follow_up": grader_data.get('requires_followup', False),
            "phase": session_context['interview_phase'],
            "question_count": session_context['question_count'],
            "average_score": analytics["average_score"] if session_context['all_scores'] else 'N/A',
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
        "analytics": analytics
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
    session_context['qa_log'] = []
    session_context['started'] = False
    session_context['edge_cases_detected'] = []
    session_context['red_flags_history'] = []
    session_context['coding_round'] = None
    
    return jsonify({"status": "success", "message": "Session reset"})


@app.route('/export-transcript', methods=['GET'])
def export_transcript():
    """Export transcript (JSON) for replay/download."""
    return jsonify({
        "status": "success",
        "role": session_context.get("selected_role", ""),
        "question_count": session_context.get("question_count", 0),
        "qa_log": session_context.get("qa_log", []),
        "analytics": {
            "scores": session_context.get("all_scores", []),
            "skill_breakdown": compute_skill_breakdown(session_context.get("qa_log", [])),
            "edge_cases_count": len(session_context.get("edge_cases_detected", [])),
        },
    })


@app.route('/export-transcript-txt', methods=['GET'])
def export_transcript_txt():
    """Export transcript as plain text."""
    lines = []
    for entry in session_context.get("qa_log", []):
        qid = entry.get("question_id", "")
        phase = entry.get("phase", "")
        score = entry.get("score", "")
        skills = ", ".join(entry.get("skills", []) or [])
        lines.append(f"Q{qid} ({phase}) [{skills}]")
        lines.append(entry.get("question", ""))
        lines.append("")
        lines.append(f"A (score: {score})")
        lines.append(entry.get("answer", ""))
        lines.append("")
        lines.append("-" * 60)
    content = "\n".join(lines) if lines else "No transcript available yet."
    return send_file(
        BytesIO(content.encode("utf-8")),
        mimetype="text/plain",
        as_attachment=True,
        download_name=f"interview-transcript-{datetime.datetime.now().strftime('%Y%m%d')}.txt",
    )

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


@app.route('/start-coding-round', methods=['GET'])
def start_coding_round():
    """Return a coding question based on selected role to start the interview."""
    role_key = session_context.get('selected_role', 'software_engineer')
    category, question = pick_coding_question(role_key)
    if question is None:
        return jsonify({"status": "error", "message": "No coding questions available."}), 500

    session_context['coding_round'] = {
        "category": category,
        "question": question,
        "started_at": datetime.datetime.now().isoformat(),
    }

    return jsonify({
        "status": "success",
        "category": category,
        "question": question,
    })


@app.route('/submit-coding-round', methods=['POST'])
def submit_coding_round():
    """Capture coding solution and return an explanation question to start the interview."""
    if not session_context.get('coding_round'):
        return jsonify({"status": "error", "message": "No active coding round."}), 400

    data = request.json or {}
    code = data.get("code") or ""
    language = (data.get("language") or "python").lower()
    coding = session_context['coding_round']
    q = coding.get("question", {})

    # Log coding round as a QA entry without a numeric score
    role_info = AVAILABLE_ROLES.get(session_context.get('selected_role', 'software_engineer'), AVAILABLE_ROLES['software_engineer'])
    skills = infer_skills_from_question(q.get("title", "") + " " + q.get("prompt", ""), role_info)
    session_context['qa_log'].append({
        "question_id": "coding_round",
        "phase": "Coding",
        "question": f"{q.get('title', '')}: {q.get('prompt', '')}",
        "answer": code,
        "language": language,
        "score": None,
        "persona": "normal",
        "is_edge_case": False,
        "skills": skills,
        "timestamp_iso": datetime.datetime.now().isoformat(),
    })

    # Prepare explanation question that will be used as the first interview question
    explanation_question = (
        f"You just implemented a solution for the coding problem '{q.get('title', '')}'. "
        f"Please explain your approach step by step, including key data structures, algorithms, "
        f"and the time and space complexity of your solution."
    )

    session_context['current_question'] = explanation_question
    session_context['interview_phase'] = "Technical"
    session_context['started'] = True

    return jsonify({
        "status": "success",
        "explanation_question": explanation_question,
    })

@app.route('/generate-study-plan', methods=['POST'])
def generate_study_plan():
    """Generate a 7/14/30 day study plan based on performance."""
    try:
        data = request.json or {}
        scores = data.get('scores') or session_context.get('all_scores', [])
        analytics = data.get('analytics') or {}
        skill_breakdown = analytics.get('skill_breakdown') or compute_skill_breakdown(session_context.get('qa_log', []))
        role = data.get('role') or session_context.get('selected_role', '')

        avg_score = sum(scores) / len(scores) if scores else 0

        prompt = f"""You are an expert interview coach.

Role: {role}
Average score: {avg_score:.1f}
Skill breakdown (average scores per skill): {json.dumps(skill_breakdown)}

Design a concrete, realistic study plan with three tracks:
- 7-day intensive plan
- 14-day standard plan
- 30-day deep-dive plan

For each plan, provide:
- daily objectives
- specific topics to study (mapped to the weakest skills you see)
- suggested practice activities (coding practice, system-design prompts, behavioral questions)
- 2–3 example resources (platforms/books) but no external links are required.

Return JSON with:
{{
  "plans": [
    {{
      "duration_days": 7 | 14 | 30,
      "label": "string",
      "summary": "short description",
      "days": [
        {{
          "day": 1,
          "focus": "string",
          "tasks": ["...","..."]
        }}
      ]
    }}
  ]
}}"""

        completion = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {"role": "system", "content": "You are a strict but supportive interview coach who designs concrete study plans."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.5,
        )

        result = json.loads(completion.choices[0].message.content)
        return jsonify({"status": "success", "plan": result})
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
        }), 500


@app.route('/run-code', methods=['POST'])
def run_code():
    """Very simple coding-round runner for Python snippets."""
    data = request.json or {}
    language = (data.get('language') or 'python').lower()
    code = data.get('code') or ''

    if not code.strip():
        return jsonify({"status": "error", "message": "Code is empty."}), 400

    # For now, only Python execution is supported; other languages are accepted but not executed
    if language != 'python':
        return jsonify({
            "status": "success",
            "output": f"Execution preview is only supported for Python in this demo.\nYour {language} code has been recorded for review."
        })

    # If we have an active coding_round with Python tests, run them and report pass/fail
    coding = session_context.get("coding_round") or {}
    question = coding.get("question") or {}
    tests = question.get("python_tests") or []
    signature = question.get("python_signature")

    # Minimal sandbox: no builtins beyond a safe subset
    safe_globals = {
        "__builtins__": {
            "range": range,
            "len": len,
            "print": print,
            "sum": sum,
            "min": min,
            "max": max,
            "abs": abs,
            "sorted": sorted,
        }
    }
    buffer = io.StringIO()
    old_stdout = sys.stdout
    try:
        sys.stdout = buffer
        exec(code, safe_globals, {})

        # If no structured tests, just return stdout like a REPL
        if not tests or not signature:
            output = buffer.getvalue()
            return jsonify({"status": "success", "output": output})

        fn_name = signature.split("(")[0].replace("def", "").strip()
        fn = safe_globals.get(fn_name)
        if not callable(fn):
            return jsonify({
                "status": "error",
                "output": buffer.getvalue(),
                "message": f"Function {fn_name} is not defined correctly. Please keep the signature as: {signature}"
            }), 400

        results = []
        passed_count = 0
        for t in tests:
            inp = t.get("input", {})
            expected = t.get("expected")
            try:
                actual = fn(**inp)
                ok = actual == expected
            except Exception as e:
                actual = str(e)
                ok = False
            if ok:
                passed_count += 1
            results.append({
                "id": t.get("id"),
                "input": inp,
                "expected": expected,
                "actual": actual,
                "passed": ok,
            })

        if passed_count == len(results):
            summary = f"All {passed_count} tests passed."
        else:
            summary = f"{passed_count}/{len(results)} tests passed."

        return jsonify({
            "status": "success",
            "output": summary,
            "tests": results,
        })
    except Exception as e:
        return jsonify({"status": "error", "output": buffer.getvalue(), "message": str(e)}), 400
    finally:
        sys.stdout = old_stdout


if __name__ == '__main__':
    app.run(debug=True, port=5000)
