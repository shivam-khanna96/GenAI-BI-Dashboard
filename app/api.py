from fastapi import APIRouter
from pydantic import BaseModel
import ast
from app.chains import (
    classification_chain, agent_executor, generate_query_chain, narrative_chain,
    get_axis_titles_llm, get_ai_chart_recommendation
)
from app.db import db, DB_SCHEMA
from app.utils import is_currency_column_smart, format_currency

router = APIRouter()

class QueryRequest(BaseModel):
    query: str

DESCRIPTIVE_CACHE = {}

@router.post("/get-insight")
def handle_get_insight(request: QueryRequest):
    question = request.query
    generated_sql = "N/A"
    result_data = []
    narrative = ""
    try:
        intent_result = classification_chain.invoke({"question": question})
        intent = intent_result.get("intent")
        print(f"Detected Intent: {intent}")
        if intent == "destructive_request":
            narrative = "Error: This request has been blocked as it was identified as potentially destructive."
            return {"query": question, "sql": "BLOCKED", "data": [], "narrative": narrative, "chartType": "none", "error": narrative}
        if intent == "data_query":
            sql_with_markdown = generate_query_chain.invoke({"question": question})
            generated_sql = sql_with_markdown.strip().replace("```sqlite", "").replace("```", "").replace("```sqlite", "").strip()
            result_str = db.run(generated_sql)
            if str(result_str).startswith("Error:"):
                raise Exception(result_str)
            data_tuples = ast.literal_eval(str(result_str))
            if data_tuples:
                column_names = [desc[0] for desc in db._engine.execute(generated_sql).cursor.description]
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
                bullets = []
                axis_titles = {"x": "", "y": ""}
        else:
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
