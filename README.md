# Insight — AI Interview Practice Partner

Flask web app for **role-based mock interviews** powered by a **multi-agent LLM loop** (profiler + grader + interviewer + feedback). Upload a resume + paste a job description, then practice with adaptive questions, scoring, and a final feedback report.

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env`:

```bash
GROQ_API_KEY=your_key_here
```

Run:

```bash
python app.py
```

Open `http://localhost:5000`.

## Features

- **Role-based interview flow** (technical + behavioral + deep dive)
- **Live grading & analytics** (scores, trends, skill breakdown)
- **Coding round UI** (LeetCode-style); Python has a safe “run tests” mode
- **Export** transcript/feedback (TXT, optional PDF)
- **Voice input/output** (browser Web Speech APIs)

## Configuration (optional)

| Env var | Default | Purpose |
|---|---:|---|
| `GROQ_API_KEY` | (required) | LLM access |
| `REDIS_URL` | `redis://localhost:6379/0` | Persist session state in Redis (falls back to in-memory if Redis missing) |
| `SESSION_TTL_SECONDS` | `21600` | Redis session TTL (6 hours) |
| `CHROMA_DIR` | `./chroma_store` | ChromaDB persistence path (semantic retrieval; optional) |

## Notes

- Redis / ChromaDB / PDF export are **optional**; the app falls back gracefully if they aren’t installed/available.
- Run Redis locally (optional):

```bash
docker run -p 6379:6379 -d redis:7
```

## Repo layout

- `app.py`: Flask server + routes
- `agents/`: profiler, grader, interviewer, feedback generator
- `templates/index.html`: single-page UI
