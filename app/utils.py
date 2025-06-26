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
    from app.db import DB_SCHEMA
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
