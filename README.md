# GenAI BI Dashboard

A modern, secure, and AI-powered business intelligence dashboard that lets you query your data in natural language and get instant insights, visualizations, and SQL—all powered by LLMs and Plotly.

---

## Features
- **Natural Language Data Queries**: Ask questions about your data in plain English.
- **AI-Powered SQL Generation**: LLMs generate safe, read-only SQL queries.
- **Smart Visualizations**: Automatic chart type and axis title selection using LLMs.
- **Descriptive Q&A**: Ask about your schema, tables, and columns.
- **Security Guardrails**: All queries are intent-classified and checked for safety.
- **Beautiful UI**: React frontend with Plotly charts and modern design.

---

## Project Structure
```
.
├── app/
│   ├── __init__.py
│   ├── main.py         # FastAPI entrypoint
│   ├── api.py          # FastAPI route definitions
│   ├── chains.py       # All LangChain chains/agents/tools
│   ├── db.py           # DB connection, schema extraction, helpers
│   ├── utils.py        # Formatting, currency, and other helpers
│   ├── config.py       # Loads environment variables using python-dotenv
├── genai-bi-frontend/  # React frontend (see its own README)
├── .env                # API keys and secrets (not committed)
├── .gitignore
├── requirements.txt
├── sample_sales.db
└── README.md
```

---

## Getting Started

### 1. Clone the repository
```
git clone <your-repo-url>
cd GenAI\ Use\ Cases/GenAIBIDashboard
```

### 2. Set up the backend
- Create a virtual environment and activate it:
  ```
  python -m venv .venv
  source .venv/bin/activate  # On Windows: .venv\Scripts\activate
  ```
- Install dependencies:
  ```
  pip install -r requirements.txt
  ```
- Create a `.env` file in the root directory:
  ```
  GOOGLE_API_KEY=your-google-api-key-here
  ```
- Start the backend:
  ```
  python -m app.main
  ```
  The API will be available at `http://127.0.0.1:8000`.

### 3. Set up the frontend
- Go to the frontend directory:
  ```
  cd genai-bi-frontend
  ```
- Install dependencies:
  ```
  npm install
  ```
- Start the frontend:
  ```
  npm start
  ```
  The app will be available at `http://localhost:3000`.

---

## Environment Variables
- All secrets and API keys should be placed in the `.env` file (never committed to git).
- Example:
  ```
  GOOGLE_API_KEY=your-google-api-key-here
  ```

---

## Security
- All SQL queries are intent-classified and checked for forbidden keywords.
- Only safe, read-only queries are executed.
- Destructive requests are blocked.

---

## Tech Stack
- **Backend:** FastAPI, LangChain, SQLAlchemy, SQLite, python-dotenv
- **LLM:** Gemini (Google Generative AI)
- **Frontend:** React, Plotly.js, Tailwind CSS

---

## License
MIT License

---

## Acknowledgements
- [LangChain](https://github.com/langchain-ai/langchain)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Plotly.js](https://plotly.com/javascript/)
- [Google Generative AI](https://ai.google.dev/)
