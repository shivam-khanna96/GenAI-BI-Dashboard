import os
import sqlite3
import json
import ast
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Literal, List
import uvicorn

# --- LangChain and SQLAlchemy Imports ---
from langchain_community.utilities import SQLDatabase
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor
from langchain.chains import create_sql_query_chain
from langchain_core.tools import BaseTool
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.prompts import PromptTemplate
from sqlalchemy import create_engine
import langchain
from langchain.globals import set_llm_cache
from langchain_community.cache import InMemoryCache
from langchain_community.tools.sql_database.tool import ListSQLDatabaseTool, InfoSQLDatabaseTool
from langchain.agents import create_react_agent
# from langchain.agents.agent_toolkits import create_agent_executor


# --- Setup LangChain Caching ---
set_llm_cache(InMemoryCache())

# --- Pydantic Models ---
class QueryRequest(BaseModel):
    query: str

# Layer 1: Stricter Pydantic model for Intent Classification
class Intent(BaseModel):
    intent: Literal["data_query", "descriptive_question", "destructive_request"] = Field(
        description="Classify the user's intent. 'data_query' for data requests. 'descriptive_question' for schema questions. 'destructive_request' for any request to modify, delete, or drop data."
    )

# --- Database Connection ---
DB_FILE = "sample_sales.db"
db_engine = create_engine(f"sqlite:///{DB_FILE}")
db = SQLDatabase(engine=db_engine)

# --- Layer 2: Custom, Secure, Read-Only SQL Tool ---
FORBIDDEN_KEYWORDS = ["DROP", "DELETE", "UPDATE", "INSERT", "GRANT", "REVOKE", "ALTER", "TRUNCATE", "CREATE"]

class SafeQuerySQLDataBaseTool(BaseTool):
    """
    A custom tool that wraps the standard SQL query tool with a security check.
    This tool will refuse to execute any SQL containing forbidden keywords.
    This is our primary security guardrail at the execution layer.
    """
    # --- FIX: Added required type hints for Pydantic model fields ---
    name: str = "sql_db_query_checker"
    description: str = "Input to this tool is a SQL query, output is a result from the database. Use this to query the database for information."
    db: SQLDatabase

    def _run(self, query: str) -> str:
        # Security Check: Scan for forbidden keywords before execution.
        clean_query = query.strip().upper()
        for keyword in FORBIDDEN_KEYWORDS:
            # Check for keyword as a whole word to avoid false positives (e.g., 'UPDATEd')
            if f" {keyword} " in f" {clean_query} " or clean_query.startswith(keyword + " "):
                return f"Error: The query was blocked because it contained the forbidden keyword '{keyword}'."
        
        # If the query is safe, execute it.
        result = self.db.run(query)
        return str(result)

# --- Charting Logic ---
def get_chart_recommendation(data):
    if not data or len(data) == 0: return "none"
    if len(data) == 1 and len(data[0]) == 1: return "kpi"
    if len(data[0]) >= 2:
        try:
            second_col_val = list(data[0].values())[1]
            if isinstance(second_col_val, (int, float)):
                if 2 < len(data) <= 7: return "pie"
                return "bar"
        except (IndexError, TypeError):
             return "table"
    return "table"


# --- FastAPI Application ---
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- LangChain Components using Secure Architecture ---
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key="AIzaSyAZr-wGLuaxZd0gSYnCgumuuaiI5rHnnAQ", temperature=0)

# --- Layer 1: Stricter Intent Classification Chain ---
parser = JsonOutputParser(pydantic_object=Intent)
classification_prompt_template = """As a security-focused AI, you must first classify the user's intent.
The user wants to interact with a database. Your primary goal is to identify if their request is a safe data query, a simple descriptive question, or a potentially harmful destructive request.
A 'destructive_request' is ANY request that asks to add, delete, modify, or remove data, tables, or database structure. This includes words like 'delete', 'remove', 'drop', 'insert', 'update', 'add', etc.

Based on the user's question, classify the intent into one of three categories: 'data_query', 'descriptive_question', or 'destructive_request'.

Question: {question}
Format Instructions: {format_instructions}
"""
classification_prompt = PromptTemplate(
    template=classification_prompt_template,
    input_variables=["question"],
    partial_variables={"format_instructions": parser.get_format_instructions()},
)
classification_chain = classification_prompt | llm | parser

# --- Layer 2 & 3: Define tools and chains with the SAFE tool ---
safe_sql_tool = SafeQuerySQLDataBaseTool(db=db)
list_tables_tool = ListSQLDatabaseTool(db=db)
info_sql_tool = InfoSQLDatabaseTool(db=db)

# Direct chain for generating SQL (used for data_query intent)
generate_query_chain = create_sql_query_chain(llm, db)

# Conversational agent now ONLY gets the safe, read-only tools
agent_tools = [safe_sql_tool, list_tables_tool, info_sql_tool]
react_template = """You are an agent designed to interact with a SQL database. Given an input question, use the available tools to answer. Only use the given tools. Do not make up any information.

Available tools:
{tools}
Tool names: {tool_names}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}
"""

agent_prompt = PromptTemplate(
    template=react_template,
    input_variables=["input", "agent_scratchpad", "tools", "tool_names"]
)

agent = create_react_agent(llm, agent_tools, agent_prompt)
agent_executor = AgentExecutor(agent=agent, tools=agent_tools, verbose=True, handle_parsing_errors=True)

# --- Narrative chain: structured output for summary and bullet points ---
from langchain_core.output_parsers import JsonOutputParser

class InsightOutput(BaseModel):
    summary: str
    bullets: List[str] = []

insight_parser = JsonOutputParser(pydantic_object=InsightOutput)
narrative_prompt = PromptTemplate(
    template=(
        "Given the user's question: '{question}' and the following data: '{result}', "
        "write a brief summary insight (1-2 sentences) as 'summary', and if there are any key findings, "
        "list them as bullet points in a 'bullets' array. "
        "Respond in JSON with keys 'summary' and 'bullets'."
    ),
    input_variables=["question", "result"]
)
narrative_chain = narrative_prompt | llm | insight_parser

# --- Currency formatting helper ---
CURRENCY_KEYWORDS = [
    "amount", "price", "cost", "revenue", "total", "spent", "sales", "income", "payment", "charge", "fee", "balance"
]
CURRENCY_SYMBOL = "$"  # Change as needed

def is_currency_column(col_name):
    return any(word in col_name.lower() for word in CURRENCY_KEYWORDS)

def format_currency(val):
    try:
        return f"{CURRENCY_SYMBOL}{round(float(val)):,}"
    except Exception:
        return val

def format_result_data(result_data):
    if not result_data:
        return result_data
    formatted = []
    for row in result_data:
        new_row = {}
        for k, v in row.items():
            if is_currency_column(k) and isinstance(v, (int, float)):
                new_row[k] = format_currency(v)
            else:
                new_row[k] = v
        formatted.append(new_row)
    return formatted

def get_column_names_from_sql(sql_query):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute(sql_query)
        if cursor.description:
            return [description[0] for description in cursor.description]
        return []
    finally:
        conn.close()

def extract_db_schema(db_file):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    schema = {}
    try:
        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        for table in tables:
            # Get columns for each table
            cursor.execute(f"PRAGMA table_info({table});")
            columns = [{"name": col[1], "type": col[2]} for col in cursor.fetchall()]
            schema[table] = columns
    finally:
        conn.close()
    return schema

DB_SCHEMA = extract_db_schema(DB_FILE)

# --- AI-driven Visualization Recommendation ---
visualization_prompt = PromptTemplate(
    template=(
        "Given the user's question: '{question}', the following data: '{result}', and the database schema: '{schema}', "
        "recommend the best chart type to visualize the answer. "
        "Choose one from: 'kpi', 'bar', 'pie', 'table'. "
        "Respond ONLY with the chart type."
    ),
    input_variables=["question", "result", "schema"]
)

def get_ai_chart_recommendation(question, result_data, schema):
    prompt = visualization_prompt.format(
        question=question,
        result=json.dumps(result_data),
        schema=json.dumps(schema)
    )
    # Use the LLM directly for a single string output
    ai_response = llm.invoke(prompt)
    if hasattr(ai_response, "content"):
        content = ai_response.content
        if isinstance(content, list):
            content_str = " ".join(str(item) for item in content)
        else:
            content_str = str(content)
        chart_type = content_str.strip().lower()
    else:
        chart_type = str(ai_response).strip().lower()
    # Fallback to 'table' if LLM gives unexpected output
    if chart_type not in {"kpi", "bar", "pie", "table"}:
        chart_type = "table"
    return chart_type

# --- Simple in-memory cache for descriptive queries ---
DESCRIPTIVE_CACHE = {}

# --- Helper: Extract column types for currency detection ---
def get_column_type(table, column):
    cols = DB_SCHEMA.get(table, [])
    for col in cols:
        if col["name"].lower() == column.lower():
            return col["type"].lower()
    return ""

def is_currency_column_smart(col_name, table=None):
    # Use keywords, but also check type and context
    if table:
        col_type = get_column_type(table, col_name)
        if col_type in ("real", "numeric", "decimal", "money", "float") and any(word in col_name.lower() for word in ["amount", "price", "cost", "revenue", "payment", "charge", "fee", "balance"]):
            return True
        return False
    # fallback to old logic
    return any(word in col_name.lower() for word in CURRENCY_KEYWORDS)

# --- Helper: RAG-style schema context for LLM ---
def get_schema_context():
    # Returns a string describing tables, columns, and relationships (if any)
    context = []
    for table, cols in DB_SCHEMA.items():
        col_str = ", ".join([f"{c['name']} ({c['type']})" for c in cols])
        context.append(f"Table '{table}': {col_str}")
    return "\n".join(context)

# --- LLM Axis Title Generation ---
axis_title_prompt = PromptTemplate(
    template=(
        "Given the user's question: '{question}', the SQL query: '{sql}', and the column names: {columns}, "
        "suggest the best X and Y axis titles for a chart visualizing this data. "
        "Respond in JSON as: {{'x': <x axis title>, 'y': <y axis title>}}."
    ),
    input_variables=["question", "sql", "columns"]
)
axis_title_parser = JsonOutputParser()
def get_axis_titles_llm(question, sql, columns):
    prompt = axis_title_prompt.format(
        question=question,
        sql=sql,
        columns=json.dumps(columns)
    )
    try:
        result = axis_title_parser.invoke(llm.invoke(prompt))
        if isinstance(result, dict) and "x" in result and "y" in result:
            return result
    except Exception:
        pass
    # fallback to column names
    return {"x": columns[0] if columns else "X", "y": columns[1] if len(columns) > 1 else "Y"}

def postprocess_sql_for_time_series(sql):
    # Remove LIMIT if present
    sql = sql.replace("LIMIT 5", "").replace("limit 5", "")
    # If ordering by month, force ASC
    if "order by" in sql.lower() and "month" in sql.lower():
        sql = sql.replace("DESC", "ASC").replace("desc", "asc")
    return sql

@app.post("/get-insight")
def handle_get_insight(request: QueryRequest):
    question = request.query
    generated_sql = "N/A"
    result_data = []
    narrative = ""

    try:
        # Layer 1: Classify intent as a security checkpoint
        intent_result = classification_chain.invoke({"question": question})
        intent = intent_result.get("intent")
        print(f"Detected Intent: {intent}")

        if intent == "destructive_request":
            narrative = "Error: This request has been blocked as it was identified as potentially destructive."
            return {"query": question, "sql": "BLOCKED", "data": [], "narrative": narrative, "chartType": "none", "error": narrative}

        # Layer 3: Route to the appropriate, secure tool
        if intent == "data_query":
            # Use a direct, sequential, and reliable chain for data queries
            sql_with_markdown = generate_query_chain.invoke({"question": question})
            generated_sql = sql_with_markdown.strip().replace("```sqlite", "").replace("```", "").replace("```sqlite", "").strip()
            # --- Post-process SQL for time series ---
            generated_sql = postprocess_sql_for_time_series(generated_sql)
            print(f"Cleaned SQL for data_query: {generated_sql}")
            
            result_str = safe_sql_tool.invoke(generated_sql)
            print(f"Result from safe tool: {result_str}")

            if result_str.startswith("Error:"):
                 raise Exception(result_str)

            data_tuples = ast.literal_eval(result_str)
            
            if data_tuples:
                column_names = get_column_names_from_sql(generated_sql)
                result_data = [dict(zip(column_names, row)) for row in data_tuples]
                # --- Smarter currency formatting using schema ---
                formatted = []
                for row in result_data:
                    new_row = {}
                    for k, v in row.items():
                        # Try to infer table name from SQL (simple heuristic)
                        table = None
                        if "from" in generated_sql.lower():
                            after_from = generated_sql.lower().split("from")[1].split()[0]
                            table = after_from.strip(",;")
                        if is_currency_column_smart(k, table) and isinstance(v, (int, float)):
                            new_row[k] = format_currency(v)
                        else:
                            new_row[k] = v
                    formatted.append(new_row)
                result_data = formatted
                insight = narrative_chain.invoke({"question": question, "result": result_data})
                summary = insight.get("summary", "")
                bullets = insight.get("bullets", [])
                # --- LLM axis titles ---
                axis_titles = get_axis_titles_llm(question, generated_sql, column_names)
            else:
                summary = "The query executed successfully but returned no results."
                bullets = []
                axis_titles = {"x": "", "y": ""}
        else:
            # Use the conversational agent for descriptive questions
            # --- Caching for descriptive queries ---
            if question in DESCRIPTIVE_CACHE:
                cached = DESCRIPTIVE_CACHE[question]
                summary = narrative = cached["narrative"]
                bullets = cached.get("bullets", [])
            else:
                print("Invoking agent_executor for descriptive_question...")
                agent_result = agent_executor.invoke({"input": question})
                print("Agent_executor returned result.")
                summary = narrative = agent_result.get("output", "")
                bullets = []
                DESCRIPTIVE_CACHE[question] = {
                    "narrative": summary,
                    "bullets": bullets
                }
            axis_titles = {"x": "", "y": ""}
    except Exception as e:
        print(f"An error occurred: {e}")
        error_message = f"An error occurred while processing your request: {str(e)}"
        return {"query": question, "sql": generated_sql, "data": [], "narrative": error_message, "chartType": "none", "error": error_message}

    # --- Use AI to recommend chart type ---
    chart_type = get_ai_chart_recommendation(question, result_data, DB_SCHEMA)
    return {
        "query": question,
        "sql": generated_sql,
        "data": result_data,
        "narrative": summary,
        "bullets": bullets,
        "chartType": chart_type,
        "axisTitles": axis_titles,
        "error": None
    }

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
