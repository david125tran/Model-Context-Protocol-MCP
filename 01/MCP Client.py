# MCP Client.py

# ---------------------------------- Libraries ----------------------------------
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import asyncio
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastmcp.client import Client
from fastmcp.client.transports import SSETransport
import os
import re


# ---------------------------------- Functions ----------------------------------
def print_banner(text: str) -> None:
    """
    Create a banner for easier visualization of what's going on
    """
    banner_len = len(text)
    mid = 49 - banner_len // 2

    print("\n\n\n")
    print("*" + "-*" * 50)
    if (banner_len % 2 != 0):
        print("*"  + " " * mid + text + " " * mid + "*")
    else:
        print("*"  + " " * mid + text + " " + " " * mid + "*")
    print("*" + "-*" * 50)



# ---------------------------------- Variables ----------------------------------
script_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(script_dir)

SERVER_URL = "http://127.0.0.1:8000/sse"  



# ---------------------------------- Load DB Environment Variables ----------------------------------
print_banner("Load DB Environment Variables")

# Load db environment variables
load_dotenv(dotenv_path=parent_dir + r"\db.env", override=True)

# Load database variables
DB_USER             = os.getenv("mysql_username")
DB_PW               = os.getenv("mysql_pw")
DB_HOST             = os.getenv("mysql_host")
DB_PORT             = os.getenv("mysql_port")
DB_DATABASE_NAME    = os.getenv("mysql_database")
DB_TABLE_NAME       = os.getenv("mysql_table_name")

# View the first few characters in the key
print(f"MYSQL_USER // MYSQL_PW: {DB_USER[:3]}//{DB_PW[:3]}...")


# ---------------------------------- Ping MCP Server to Test ----------------------------------
# print_banner("Ping MCP Server to Test")

# async def main():
#     # Connect to MCP server via SSE
#     transport = SSETransport(url=SERVER_URL)
#     client = Client(transport)

#     async with client:
#         # Discover what the server exposes
#         tools = await client.list_tools()
#         print("Tools:", [t.name for t in tools])

#         # Ask the server which tables are readable 
#         res = await client.call_tool("list_tables", {})
#         tables = res.data.get("tables", [])
#         print("list_tables:", res.data)

#         if not tables:
#             print("No tables are visible. Check your server's allowlist (mysql_table_allowlist) and DB credentials.")
#             return

#         # Prefer DB_TABLE_NAME from env if it exists, else fall back to the first table
#         table = DB_TABLE_NAME or tables[0]
#         if table not in tables:
#             print(
#                 f"Configured DB_TABLE_NAME='{DB_TABLE_NAME}' is not in the server-visible tables {tables}. "
#                 f"Falling back to '{tables[0]}'."
#             )
#             table = tables[0]

#         # Inspect the chosen table
#         desc = await client.call_tool("describe_table", {"table": table})
#         print("describe_table:", desc.data)

#         # Preview a few rows
#         prev = await client.call_tool("preview", {"table": table, "limit": 5})
#         print(f"preview rows (first 5): {prev.data['count']}")

#         # Simple raw SQL example (the server verifies it's a SELECT and caps results)
#         sql_res = await client.call_tool(
#             "sql_query",
#             {"sql": "SELECT NOW() AS server_now", "max_rows": 10}
#         )
#         print("sql_query:", sql_res.data)

#         # Test a natural-language prompt from the LLM where the LLM converts the natural language to raw SQL code to 
#         # have the server side script read the db. 
#         try:
#             nl_payload = {
#                 "question": f"Show 5 rows from {table}", 
#                 "table_hint": table,                       
#                 "max_rows": 5
#             }
#             nl_res = await client.call_tool("nl2sql_query", nl_payload)
#             # Print a concise summary of what happened
#             print("nl2sql_query summary:", nl_res.data.get("summary"))
#             print("nl2sql_query sql:", nl_res.data.get("sql"))
#             print("nl2sql_query returned:", nl_res.data.get("returned"))
#         except Exception as e:
#             print("nl2sql_query failed:", e)
#             print("Tip: Ensure the server strips trailing semicolons and blocks non-allowlisted tables in nl2sql_query.")

# # Run main
# asyncio.run(main())


# ---------------------------------- UI ----------------------------------
print_banner("UI")

@asynccontextmanager
async def lifespan(app):
    # connect to MCP
    await client.__aenter__()
    try:
        yield
    finally:
        # disconnect from MCP
        await client.__aexit__(None, None, None)

app = FastAPI()
transport = SSETransport(url="http://127.0.0.1:8000/sse")
client = Client(transport)


@app.on_event("startup")
async def startup():
    await client.__aenter__()  # connect to MCP

@app.on_event("shutdown")
async def shutdown():
    await client.__aexit__(None, None, None)

@app.get("/tables")
async def tables():
    res = await client.call_tool("list_tables", {})
    return res.data

@app.get("/describe/{table}")
async def describe(table: str):
    res = await client.call_tool("describe_table", {"table": table})
    return res.data

@app.get("/preview/{table}")
async def preview(table: str, limit: int = 20, offset: int = 0):
    res = await client.call_tool("preview", {"table": table, "limit": limit, "offset": offset})
    return res.data

@app.post("/sql")
async def sql(body: dict):
    # body: { "sql": "...", "max_rows": 100 }
    res = await client.call_tool("sql_query", body)
    return res.data

@app.post("/ask")
async def ask(body: dict):
    # body: { "question": "...", "table_hint": "supplement_sales_weekly", "max_rows": 100 }
    res = await client.call_tool("nl2sql_query", body)
    return res.data  # includes {"sql", "rows", "summary", ...}

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>DB Chat (MCP)</title>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <style>
    body { font: 14px/1.4 system-ui, sans-serif; margin: 2rem; }
    .wrap { max-width: 800px; margin: 0 auto; }
    textarea, input { width: 100%; box-sizing: border-box; }
    textarea { height: 110px; }
    pre { background:#f6f8fa; padding:1rem; overflow:auto; }
    .row { display: grid; grid-template-columns: 1fr 180px; gap: 0.75rem; }
    button { padding: .6rem 1rem; }
    label { display:block; margin:.5rem 0 .25rem; font-weight:600; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Ask the database (via MCP)</h1>

    <label>Question</label>
    <textarea id="q" placeholder="e.g. Show total Units Sold by Category, top 5"></textarea>

    <div class="row">
      <div>
        <label>Table hint</label>
        <input id="table" placeholder="supplement_sales_weekly" value="supplement_sales_weekly"/>
      </div>
      <div>
        <label>Max rows</label>
        <input id="cap" type="number" value="50"/>
      </div>
    </div>

    <p><button id="ask">Ask</button>
       <button id="preview">Preview first 10 rows</button></p>

    <h3>Generated SQL</h3>
    <pre id="sql"></pre>

    <h3>Summary</h3>
    <pre id="summary"></pre>

    <h3>Rows</h3>
    <pre id="rows"></pre>
  </div>

<script>
async function postJSON(url, data) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type":"application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

document.getElementById("ask").onclick = async () => {
  const question = document.getElementById("q").value.trim() || "Show 5 rows";
  const table_hint = document.getElementById("table").value.trim() || undefined;
  const max_rows = parseInt(document.getElementById("cap").value || "50", 10);

  try {
    const data = await postJSON("/ask", { question, table_hint, max_rows });
    document.getElementById("sql").textContent = data.sql ?? "(no sql returned)";
    document.getElementById("summary").textContent = data.summary ?? "(no summary)";
    document.getElementById("rows").textContent = JSON.stringify(data.rows ?? [], null, 2);
  } catch (e) {
    document.getElementById("sql").textContent = "ERROR: " + e.message;
    document.getElementById("summary").textContent = "";
    document.getElementById("rows").textContent = "";
  }
};

document.getElementById("preview").onclick = async () => {
  const table = document.getElementById("table").value.trim() || "supplement_sales_weekly";
  try {
    const res = await fetch(`/preview/${encodeURIComponent(table)}?limit=10`);
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    document.getElementById("sql").textContent = "(preview)";
    document.getElementById("summary").textContent = `count: ${data.count}`;
    document.getElementById("rows").textContent = JSON.stringify(data.rows ?? [], null, 2);
  } catch (e) {
    document.getElementById("sql").textContent = "ERROR: " + e.message;
    document.getElementById("summary").textContent = "";
    document.getElementById("rows").textContent = "";
  }
};
</script>
</body>
</html>
    """

if __name__ == "__main__":
    import uvicorn
    # Pass the app object directly
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=9001,
        reload=False
    )