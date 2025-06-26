import json
from typing import List
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain.chains import create_sql_query_chain
from langchain.agents import create_react_agent, AgentExecutor
from langchain_community.tools.sql_database.tool import ListSQLDatabaseTool, InfoSQLDatabaseTool
from langchain_core.tools import BaseTool
from langchain_community.utilities import SQLDatabase
from app.config import GOOGLE_API_KEY
from app.db import db, DB_SCHEMA
from app.utils import is_currency_column, format_currency

# --- LLM Setup ---
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=GOOGLE_API_KEY, temperature=0)

# --- Intent Classification ---
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

# --- Secure SQL Tool ---
FORBIDDEN_KEYWORDS = ["DROP", "DELETE", "UPDATE", "INSERT", "GRANT", "REVOKE", "ALTER", "TRUNCATE", "CREATE"]
class SafeQuerySQLDataBaseTool(BaseTool):
    name: str = "sql_db_query_checker"
    description: str = "Input to this tool is a SQL query, output is a result from the database. Use this to query the database for information."
    db: SQLDatabase
    def _run(self, query: str) -> str:
        clean_query = query.strip().upper()
        for keyword in FORBIDDEN_KEYWORDS:
            if f" {keyword} " in f" {clean_query} " or clean_query.startswith(keyword + " "):
                return f"Error: The query was blocked because it contained the forbidden keyword '{keyword}'."
        result = self.db.run(query)
        return str(result)

safe_sql_tool = SafeQuerySQLDataBaseTool(db=db)
list_tables_tool = ListSQLDatabaseTool(db=db)
info_sql_tool = InfoSQLDatabaseTool(db=db)

# --- SQL Generation Chain ---
generate_query_chain = create_sql_query_chain(llm, db)

# --- Agent for Descriptive Qs ---
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

# --- Narrative Chain ---
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

# --- Axis Title Generation ---
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
    return {"x": columns[0] if columns else "X", "y": columns[1] if len(columns) > 1 else "Y"}

# --- Chart Recommendation ---
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
