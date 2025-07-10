import os
import sqlite3
import yaml
import ast
import json
from typing import List
from dotenv import load_dotenv
from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import sqlalchemy
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain.agents import create_react_agent, AgentExecutor
from langchain_community.tools.sql_database.tool import ListSQLDatabaseTool, InfoSQLDatabaseTool
from langchain_core.tools import BaseTool
from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine, inspect
import uvicorn

# --- config.py content ---
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# --- db.py content ---
DB_FILE = "olist.db"
SCHEMA_FILE = "db_schema.yaml"
db_engine = create_engine(f"sqlite:///{DB_FILE}")
db = SQLDatabase(engine=db_engine)

def get_full_schema(engine):
    inspector = inspect(engine)
    schema = {"tables": []}
    tables = inspector.get_table_names()
    for table_name in tables:
        table_info = {
            "name": table_name,
            "description": "Enter table description here.",
            "columns": [],
            "primary_key": inspector.get_pk_constraint(table_name)['constrained_columns'],
            "foreign_keys": []
        }
        columns = inspector.get_columns(table_name)
        for column in columns:
            table_info["columns"].append({
                "name": column['name'],
                "type": str(column['type']),
                "description": "Enter column description here."
            })
        foreign_keys = inspector.get_foreign_keys(table_name)
        for fk in foreign_keys:
            table_info["foreign_keys"].append({
                "constrained_columns": fk['constrained_columns'],
                "referred_table": fk['referred_table'],
                "referred_columns": fk['referred_columns']
            })
        schema["tables"].append(table_info)
    return schema

def load_or_create_schema():
    if os.path.exists(SCHEMA_FILE):
        print(f"Loading schema from existing file: {SCHEMA_FILE}")
        with open(SCHEMA_FILE, 'r') as f:
            return yaml.safe_load(f)
    else:
        print("Schema file not found. Generating new schema from database...")
        schema_data = get_full_schema(db_engine)
        with open(SCHEMA_FILE, 'w') as f:
            yaml.dump(schema_data, f, default_flow_style=False, sort_keys=False)
        print(f"New schema saved to {SCHEMA_FILE}. You can now edit this file to add descriptions.")
        return schema_data

DB_SCHEMA = load_or_create_schema()
DB_SCHEMA_STRING = yaml.dump(DB_SCHEMA, default_flow_style=False, sort_keys=False)

# --- utils.py content ---
CURRENCY_KEYWORDS = [
    "amount", "price", "cost", "revenue", "total", "spent", "sales", "income", "payment", "charge", "fee", "balance"
]
CURRENCY_SYMBOL = "$"

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

def get_column_type(table, column):
    tables = DB_SCHEMA.get("tables", [])
    for t in tables:
        if t["name"] == table:
            for col in t["columns"]:
                if col["name"].lower() == column.lower():
                    return col["type"].lower()
    return ""

def is_currency_column_smart(col_name, table=None):
    if table:
        col_type = get_column_type(table, col_name)
        if col_type in ("real", "numeric", "decimal", "money", "float") and any(word in col_name.lower() for word in ["amount", "price", "cost", "revenue", "payment", "charge", "fee", "balance"]):
            return True
        return False
    return any(word in col_name.lower() for word in CURRENCY_KEYWORDS)

# --- chains.py content ---
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=GOOGLE_API_KEY, temperature=0)

class Intent(BaseModel):
    intent: str = Field(description="Classify the user's intent. 'data_query' for data requests. 'descriptive_question' for schema questions. 'destructive_request' for any request to modify, delete, or drop data.")

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

FORBIDDEN_KEYWORDS = ["DROP", "DELETE", "UPDATE", "INSERT", "GRANT", "REVOKE", "ALTER", "TRUNCATE", "CREATE"]
class SafeQuerySQLDataBaseTool(BaseTool):
    name: str = "sql_db_query_checker"
    description: str = "Input to this tool is a SQL query, output is a result from the database. Use this to query the database for information."
    db: SQLDatabase
    def _run(self, query: str) -> str:
        # Clean the query of markdown/code block markers
        clean_query = query.strip().replace("```sqlite", "").replace("```", "").strip()
        upper_query = clean_query.upper()
        for keyword in FORBIDDEN_KEYWORDS:
            if f" {keyword} " in f" {upper_query} " or upper_query.startswith(keyword + " "):
                return f"Error: The query was blocked because it contained the forbidden keyword '{keyword}'."
        result = self.db.run(clean_query)
        return str(result)

safe_sql_tool = SafeQuerySQLDataBaseTool(db=db)
list_tables_tool = ListSQLDatabaseTool(db=db)
info_sql_tool = InfoSQLDatabaseTool(db=db)

sql_generation_template = """You are an expert data analyst. Your sole purpose is to write a single, syntactically correct SQL query to answer the user's question.
Base your query ONLY on the provided database schema. Pay close attention to the column and table descriptions, primary keys, and foreign keys for creating joins. Since you have information about the schema, you can use it to create complex queries that involve multiple tables and conditions.

Database Schema:
```yaml
{schema}
```

User Question:
{question}

SQL Query (must be a correct SQL query):
```sqlite
"""
sql_generation_prompt = PromptTemplate(
    template=sql_generation_template,
    input_variables=["question"],
    partial_variables={"schema": DB_SCHEMA_STRING}
)
generate_query_chain = sql_generation_prompt | llm | StrOutputParser()

agent_tools = [safe_sql_tool, list_tables_tool, info_sql_tool]
react_template = """You are an agent designed to interact with a SQL database. Given an input question, use the available tools to answer. Only use the given tools. You also have access to the Database Schema. Use that to return any description and show how one table relates to the other if applicable. Do not make up any information.

Database Schema:
```yaml
{schema}
```

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
    input_variables=["input", "agent_scratchpad", "tools", "tool_names"],
    partial_variables={"schema": DB_SCHEMA_STRING}
)
agent = create_react_agent(llm, agent_tools, agent_prompt)
agent_executor = AgentExecutor(agent=agent, tools=agent_tools, verbose=True, handle_parsing_errors=True)

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
        result_str = llm.invoke(prompt)
        result = axis_title_parser.invoke(result_str)
        if isinstance(result, dict) and "x" in result and "y" in result:
            return result
    except Exception:
        pass
    return {"x": columns[0] if columns else "X", "y": columns[1] if len(columns) > 1 else "Y"}

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
    if chart_type not in {"kpi", "bar", "pie", "table"}:
        chart_type = "table"
    return chart_type

schema_description_template = """
You are a database documentation assistant. Given the following database schema in YAML, return a JSON object with:
- "tables": a list of tables, each with:
    - "name": table name
    - "description": table description
    - "columns": list of columns, each with:
        - "name": column name
        - "type": column type
        - "description": column description
    - "primary_key": list of primary key columns
    - "foreign_keys": list of foreign keys, each with:
        - "column": local column
        - "ref_table": referenced table
        - "ref_column": referenced column
- "relationships": a list of relationships, each with:
    - "from_table": referencing table
    - "from_column": referencing column
    - "to_table": referenced table
    - "to_column": referenced column

Schema:
```yaml
{schema}
```
Respond ONLY with a JSON object as described above.
"""
schema_description_prompt = PromptTemplate(
    template=schema_description_template,
    input_variables=[],
    partial_variables={"schema": DB_SCHEMA_STRING}
)
schema_description_parser = JsonOutputParser()
schema_description_chain = schema_description_prompt | llm | schema_description_parser

# --- api.py content ---
router = APIRouter()

class QueryRequest(BaseModel):
    query: str

DESCRIPTIVE_CACHE = {}
QUERY_CACHE = {}


@router.get("/get-schema-structure")
def get_schema_structure():
    schema_structured = schema_description_chain.invoke({})
    return schema_structured

@router.get("/get-table-sample/{table_name}")
def get_table_sample(table_name: str):
    with db._engine.connect() as connection:
        try:
            result_proxy = connection.execute(sqlalchemy.text(f'SELECT * FROM "{table_name}" LIMIT 5'))
            column_names = list(result_proxy.keys())
            rows = result_proxy.fetchall()
            sample_data = [dict(zip(column_names, row)) for row in rows]
            return {"sampleData": sample_data}
        except Exception as e:
            return {"error": str(e)}


@router.post("/get-insight")
def handle_get_insight(request: QueryRequest):
    question = request.query
    intent_result = classification_chain.invoke({"question": question})
    intent = intent_result.get("intent")
    print(f"Detected Intent: {intent}")

    if intent == "data_query" and question in QUERY_CACHE:
        print(f"Returning cached result for data_query: '{question}'")
        return QUERY_CACHE[question]
    
    if intent == "descriptive_question" and question in DESCRIPTIVE_CACHE:
        print(f"Returning cached result for descriptive_question: '{question}'")
        cached = DESCRIPTIVE_CACHE[question]
        return {
            "query": question, "sql": "N/A", "data": [], "narrative": cached["narrative"],
            "bullets": cached.get("bullets", []), "chartType": "none", 
            "axisTitles": {"x": "", "y": ""}, "error": None,
            "schemaStructured": cached.get("schema_structured"),
            "agentAnswer": cached.get("agent_answer")
        }

    generated_sql = "N/A"
    result_data = []
    summary = ""
    bullets = []
    axis_titles = {"x": "", "y": ""}

    try:
        if intent == "destructive_request":
            narrative = "Error: This request has been blocked as it was identified as potentially destructive."
            return {"query": question, "sql": "BLOCKED", "data": [], "narrative": narrative, "chartType": "none", "error": narrative}
        
        if intent == "data_query":
            sql_with_markdown = generate_query_chain.invoke({"question": question})
            generated_sql = sql_with_markdown.strip().replace("```sqlite", "").replace("```", "").strip()
            # Use SQLAlchemy to execute and fetch results
            with db._engine.connect() as connection:
                result_proxy = connection.execute(sqlalchemy.text(generated_sql))
                column_names = list(result_proxy.keys())
                data_tuples = result_proxy.fetchall()
            if data_tuples:
                result_data = [dict(zip(column_names, row)) for row in data_tuples]

                formatted = []
                for row in result_data:
                    new_row = {}
                    for k, v in row.items():
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
                axis_titles = get_axis_titles_llm(question, generated_sql, column_names)
            else:
                summary = "The query executed successfully but returned no results."
        
        else:
            print("Invoking agent_executor for descriptive_question...")
            agent_result = agent_executor.invoke({"input": question})
            agent_answer = None
            if isinstance(agent_result, dict):
                agent_answer = agent_result.get("output", str(agent_result))
            else:
                agent_answer = str(agent_result)

            # Only show full schema if the question is generic
            generic_schema_keywords = [
                "schema", "all tables", "database structure", "show schema", "show tables", "list tables", "database diagram"
            ]
            if any(word in question.lower() for word in generic_schema_keywords):
                narrative = "Please use the Data Exploration feature to view the database schema."
                return {
                    "query": question,
                    "sql": "N/A",
                    "data": [],
                    "narrative": narrative,
                    "bullets": [],
                    "chartType": "none",
                    "axisTitles": {"x": "", "y": ""},
                    "error": None
                }

                # Improved formatting for schema description summary
                tables = schema_structured.get("tables", [])
                relationships = schema_structured.get("relationships", [])
                table_summaries = []
                for t in tables:
                    if isinstance(t, dict):
                        desc = t.get("description", "")
                        name = t.get("name", "Unknown Table")
                        columns = t.get("columns", [])
                        col_str = ", ".join([f"{col['name']} ({col['type']})" for col in columns]) if columns else ""
                        table_summaries.append(
                            f"- {name}: {desc if desc and desc != 'Enter table description here.' else 'No description.'}"
                            + (f"\n    Columns: {col_str}" if col_str else "")
                        )
                rel_summaries = []
                for rel in relationships:
                    rel_summaries.append(
                        f"- {rel.get('from_table')}({rel.get('from_column')}) → {rel.get('to_table')}({rel.get('to_column')})"
                    )
                summary = ""
                if table_summaries:
                    summary += "Tables in the database:\n" + "\n".join(table_summaries)
                if rel_summaries:
                    summary += "\n\nRelationships:\n" + "\n".join(rel_summaries)
                if not summary:
                    summary = "No tables or relationships found in the schema."
                DESCRIPTIVE_CACHE[question] = {
                    "narrative": summary,
                    "bullets": [],
                    "schema_structured": schema_structured,
                    "agent_answer": agent_answer,
                    "schema_sample_data": schema_sample_data
                }
                return {
                    "query": question,
                    "sql": "N/A",
                    "data": [],
                    "narrative": summary,
                    "bullets": [],
                    "chartType": "schema",
                    "axisTitles": {"x": "", "y": ""},
                    "schemaStructured": schema_structured,
                    "agentAnswer": agent_answer,
                    "schemaSampleData": schema_sample_data,
                    "error": None
                }
            else:
                # For specific descriptive questions, return only the agent's answer
                DESCRIPTIVE_CACHE[question] = {
                    "narrative": agent_answer,
                    "bullets": [],
                    "schema_structured": None,
                    "agent_answer": agent_answer,
                    "schema_sample_data": None
                }
                return {
                    "query": question,
                    "sql": "N/A",
                    "data": [],
                    "narrative": agent_answer,
                    "bullets": [],
                    "chartType": "none",
                    "axisTitles": {"x": "", "y": ""},
                    "schemaStructured": None,
                    "agentAnswer": agent_answer,
                    "schemaSampleData": None,
                    "error": None
                }

    except Exception as e:
        print(f"An error occurred: {e}")
        error_message = f"An error occurred while processing your request: {str(e)}"
        return {"query": question, "sql": generated_sql, "data": [], "narrative": error_message, "chartType": "none", "error": error_message}

    chart_type = get_ai_chart_recommendation(question, result_data, DB_SCHEMA)
    response = {
        "query": question,
        "sql": generated_sql,
        "data": result_data,
        "narrative": summary,
        "bullets": bullets,
        "chartType": chart_type,
        "axisTitles": axis_titles,
        "error": None
    }

    if intent == "data_query":
        QUERY_CACHE[question] = response

    return response

# --- main.py content ---
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
