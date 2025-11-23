# Insight - AI Interview Practice Partner

An intelligent conversational AI agent that helps users prepare for job interviews through natural conversation. Built as a multi-agent system that adapts to different user personas and provides real-time feedback.

## 🎯 Problem Statement

**Interview Practice Partner** - An AI agent that:
- Conducts mock interviews for specific roles (sales, engineer, retail associate, etc.)
- Asks follow-up questions like a real interviewer would
- Provides post-interview feedback on responses and identifies areas for improvement
- Supports both voice and chat interaction modes

## 🏗️ Architecture

### Multi-Agent System Design

The system employs a **four-agent architecture** that works in parallel to create intelligent, adaptive interview experiences:

```
┌─────────────┐
│   User      │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│         Flask Backend (app.py)              │
│                                              │
│  ┌──────────┐  ┌──────────┐                 │
│  │ Profiler │  │  Grader  │                 │
│  │  Agent   │  │  Agent   │                 │
│  └────┬─────┘  └────┬─────┘                 │
│       │             │                        │
│       └──────┬──────┘                        │
│              ▼                               │
│       ┌──────────────┐                      │
│       │ Interviewer  │                      │
│       │    Agent     │                      │
│       └──────┬───────┘                      │
│              │                              │
│              ▼                              │
│       ┌──────────────────┐                  │
│       │ Feedback        │                  │
│       │ Generator Agent │                  │
│       └──────────────────┘                  │
└──────────────┬──────────────────────────────┘
               │
               ▼
        ┌─────────────┐
        │   Frontend  │
        │  (Chat/Voice)│
        └─────────────┘
```

### Agent Responsibilities

1. **ProfilerAgent** (`agents/profiler.py`)
   - **Purpose**: Advanced behavioral analysis and persona detection
   - **Detects**: Confused, Efficient, Chatty, Edge Case, Normal, Silent, Anxious, or Overconfident users
   - **Output**: Comprehensive persona classification, relevance, sentiment, confidence level, communication quality, engagement metrics
   - **Features**: Context-aware analysis, risk factor detection, positive indicator identification
   - **Model**: Groq Llama-3.3-70B-Versatile with JSON response format

2. **GraderAgent** (`agents/grader.py`)
   - **Purpose**: Multi-dimensional answer evaluation
   - **Evaluates**: Technical accuracy, communication quality, relevance, depth level
   - **Features**: Trend analysis, adaptive scoring, follow-up suggestions, strength/improvement identification
   - **Output**: Comprehensive score breakdown, requires_followup flag, detailed feedback, actionable insights
   - **Model**: Groq Llama-3.3-70B-Versatile with JSON response format

3. **InterviewerAgent** (`agents/interviewer.py`)
   - **Purpose**: Intelligent conversation orchestration with adaptive questioning
   - **Synthesizes**: Profiler and Grader insights into contextual, natural responses
   - **Adapts**: Behavior based on detected persona with sophisticated strategies
   - **Manages**: Interview phases (Introduction → Technical → Behavioral → Deep Dive → Feedback)
   - **Features**: Phase-specific question generation, adaptive difficulty, Socratic questioning, comprehensive feedback generation
   - **Model**: Groq Llama-3.3-70B-Versatile with higher temperature for natural conversation

4. **FeedbackGeneratorAgent** (`agents/feedback_generator.py`) **[NEW]**
   - **Purpose**: Comprehensive post-interview feedback generation
   - **Generates**: Executive summary, performance breakdown, STAR analysis, technical competency map, actionable recommendations
   - **Features**: Score analytics, trend analysis, role fit assessment, learning path recommendations
   - **Model**: Groq Llama-3.3-70B-Versatile

### Design Decisions

#### 1. **Multi-Agent Architecture**
   - **Why**: Separation of concerns allows each agent to specialize
   - **Benefit**: Easier to debug, improve, and scale individual components
   - **Trade-off**: Slightly higher latency (3 API calls per turn), but better quality

#### 2. **Persona-Based Adaptation**
   - **Why**: Real interviews require handling different candidate behaviors
   - **Implementation**: Profiler detects persona → Interviewer adapts strategy
   - **Examples**:
     - **Confused User**: Offers hints without giving answers
     - **Efficient User**: Challenges with deeper follow-ups
     - **Chatty User**: Validates then redirects with bridge phrases
     - **Edge Case**: Strict boundary enforcement

#### 3. **Real-Time Feedback Loop**
   - **Why**: Immediate feedback improves learning
   - **Implementation**: Grader evaluates → Interviewer uses score to guide next question
   - **Visualization**: Frontend displays persona badges and scores in real-time

#### 4. **Chain-of-Thought Prompting**
   - **Why**: Transparency and better reasoning
   - **Implementation**: Interviewer outputs `[ANALYSIS]` and `[RESPONSE]` sections
   - **Benefit**: Users can see agent's reasoning process (collapsible in UI)

#### 5. **Voice-First with Chat Fallback**
   - **Why**: Assignment prefers voice, but chat is more accessible
   - **Implementation**: Web Speech API for voice input/output
   - **Fallback**: Text input always available

## 🚀 Setup Instructions

### Prerequisites
- Python 3.8+
- Groq API key ([Get one here](https://console.groq.com/))

### Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd ag
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv age
   # Windows
   age\Scripts\activate
   # Linux/Mac
   source age/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   # Create .env file in root directory
   echo "GROQ_API_KEY=your_groq_api_key_here" > .env
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

6. **Access the application**
   - Open browser to `http://localhost:5000`
   - Upload a resume (PDF) and paste job description
   - Start the interview!

## 📁 Project Structure

```
ag/
├── agents/
│   ├── __init__.py
│   ├── profiler.py           # Advanced persona detection agent
│   ├── grader.py             # Multi-dimensional evaluation agent
│   ├── interviewer.py        # Intelligent conversation agent
│   └── feedback_generator.py # Comprehensive feedback agent
├── templates/
│   └── index.html       # Frontend UI (chat + voice)
├── app.py               # Flask backend & routing
├── requirements.txt     # Python dependencies
├── .env                # Environment variables (gitignored)
└── README.md           # This file
```

## 🎭 User Persona Handling

The system is designed to handle multiple user personas as required by the assignment:

### 1. **The Confused User**
- **Detection**: Says "I don't know", asks for help, gives vague answers
- **Response**: Offers conceptual hints or analogies without giving direct answers
- **Example**: "Let me rephrase that. Think of it like building blocks..."

### 2. **The Efficient User**
- **Detection**: Provides short, one-line answers
- **Response**: Challenges with deeper follow-up questions
- **Example**: "That's technically correct but brief. Can you explain specifically HOW you implemented that?"

### 3. **The Chatty User**
- **Detection**: Talks about off-topic subjects (sports, weather, personal stories)
- **Response**: Validates briefly then redirects with bridge phrases
- **Example**: "I see you like football, but regarding your experience with Python..."

### 4. **The Edge Case User**
- **Detection**: Tries to break the bot, ignores instructions, asks for poems/stories
- **Response**: Strict boundary enforcement
- **Example**: "I am strictly in Interview Mode. Let's focus on your technical skills."

### 5. **The Silent User**
- **Detection**: No response for extended period (frontend timeout)
- **Response**: Gentle prompt to re-engage
- **Example**: "Are you still there? Let me repeat the last question..."

## 🔄 Interview Flow

1. **Setup Phase**: User uploads resume and job description
2. **Introduction**: Agent introduces itself and role, sets expectations
3. **Technical Phase (Questions 2-5)**: 
   - Role-specific technical questions based on JD
   - Adaptive difficulty based on performance
   - Progressive complexity (fundamentals → intermediate → advanced)
4. **Behavioral Phase (Questions 6-8)**: 
   - STAR-method questions about past experiences
   - Focus on problem-solving, leadership, conflict resolution
5. **Deep Dive Phase (Questions 9+)**: 
   - System design / Architecture questions
   - Scenario-based problem solving
   - Trade-off analysis
6. **Feedback Phase**: Comprehensive post-interview feedback with:
   - Executive summary and overall assessment
   - Performance breakdown (technical, communication, behavioral)
   - STAR analysis with improvement suggestions
   - Technical competency map
   - Knowledge gaps identification
   - Actionable improvement tips and learning paths
   - Role fit assessment and readiness timeline

## 🚀 Advanced Features

### Interview State Management
- **Phase Tracking**: Automatic progression through interview phases
- **Question Counting**: Tracks total questions asked
- **Score History**: Maintains all scores for trend analysis
- **Interview History**: Complete conversation log for feedback generation

### Real-Time Analytics
- **Performance Metrics**: Average, highest, lowest scores
- **Trend Analysis**: Improving, stable, or declining performance
- **Score Distribution**: Breakdown by performance tiers
- **Phase-Specific Insights**: Performance by interview phase

### Enhanced Persona Detection
- **7 Persona Types**: Normal, Confused, Efficient, Chatty, Edge Case, Anxious, Overconfident
- **Multi-Dimensional Analysis**: Sentiment, confidence, communication quality, engagement level
- **Risk Factor Detection**: Identifies potential interview issues
- **Positive Indicator Tracking**: Highlights candidate strengths

### Comprehensive Evaluation
- **Multi-Dimensional Scoring**: Technical accuracy, communication quality, relevance
- **Depth Assessment**: Surface, intermediate, advanced, or expert level
- **Follow-up Intelligence**: Suggests specific follow-up questions
- **Strength/Improvement Identification**: Detailed breakdown of what worked and what didn't

### Feedback Generation
- **Automatic Trigger**: Detects interview end phrases or after 12+ questions
- **Manual Trigger**: `/get-feedback` endpoint for on-demand feedback
- **Comprehensive Reports**: Executive summary, detailed analysis, actionable recommendations
- **Role Fit Assessment**: Strong fit / Good fit / Needs development with timeline

### API Endpoints

- `POST /upload-context`: Upload resume and job description
- `POST /chat`: Main conversation endpoint with enhanced analytics
- `POST /get-feedback`: Generate feedback report on demand
- `POST /reset`: Reset interview session

## 🛠️ Technical Stack

- **Backend**: Flask (Python)
- **AI/LLM**: Groq API (GPT-OSS-20B)
- **Frontend**: Vanilla JavaScript, Tailwind CSS
- **Voice**: Web Speech API (Speech Recognition & Synthesis)
- **PDF Processing**: PyPDF

## 📊 Evaluation Criteria Alignment

### ✅ Conversational Quality
- Natural, context-aware responses
- Persona-adaptive behavior
- Smooth conversation flow with memory

### ✅ Agentic Behaviour
- Multi-agent collaboration
- Autonomous decision-making (follow-ups, persona adaptation)
- Proactive feedback and guidance

### ✅ Technical Implementation
- Clean architecture with separation of concerns
- Error handling and fallbacks
- Scalable design (easy to add new agents)

### ✅ Intelligence & Adaptability
- Real-time persona detection
- Dynamic question generation
- Context-aware scoring and feedback

## 🎥 Demo Scenarios

For the demo video, showcase these scenarios:

1. **Confused User**: User says "I don't know" → Agent provides hints
2. **Efficient User**: Short answers → Agent asks deeper follow-ups
3. **Chatty User**: Goes off-topic → Agent redirects gracefully
4. **Edge Case**: Tries to break bot → Agent enforces boundaries
5. **Normal Flow**: Complete interview with feedback

## 🔮 Future Enhancements

- [ ] Session persistence (Redis/Database)
- [ ] Multiple interview types (technical, behavioral, case studies)
- [ ] Interview history and analytics
- [ ] Customizable interview difficulty levels
- [ ] Integration with job boards for automatic JD parsing
- [ ] Multi-language support

## 📝 Notes

- **Session Storage**: Currently uses in-memory storage. For production, implement Redis or a database.
- **API Rate Limits**: Groq API has rate limits. Consider implementing caching for repeated queries.
- **Voice Browser Support**: Voice features require Chrome/Edge (WebKit Speech Recognition).

## 📄 License

This project is created for the Eightfold.ai AI Agent Building Assignment.

---

**Built with ❤️ for intelligent interview preparation**

