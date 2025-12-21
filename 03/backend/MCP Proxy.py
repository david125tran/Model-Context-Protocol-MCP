# src/backend/mcp proxy.py



from contextlib import asynccontextmanager
from dotenv import load_dotenv
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn

from fastmcp.client import Client
from fastmcp.client.transports import SSETransport

# --- Config ---
load_dotenv(override=True)

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000/sse")

# Create MCP client
transport = SSETransport(url=MCP_SERVER_URL)
client = Client(transport)

@asynccontextmanager
async def lifespan(app: FastAPI):
  # connect to MCP on startup
  await client.__aenter__()
  try:
    yield
  finally:
    await client.__aexit__(None, None, None)

app = FastAPI(lifespan=lifespan)

# --- CORS for React dev server (Vite) ---
app.add_middleware(
  CORSMiddleware,
  allow_origins=[
    "http://localhost:5173",
    "http://127.0.0.1:5173",
  ],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

# --- REST endpoints (browser-friendly) ---

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
  # body: { "sql": "...", "max_rows": 100, "params": {...} }
  res = await client.call_tool("sql_query", body)
  return res.data

@app.post("/ask")
async def ask(body: dict):
  # body: { "question": "...", "table_hint": "supplement_sales_weekly", "max_rows": 100 }
  # passes directly to the MCP tool "nl2sql_query"
  res = await client.call_tool("nl2sql_query", body)
  return res.data  # includes {"sql","rows","summary",...}

@app.get("/", response_class=HTMLResponse)
async def index():
  return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>MCP Proxy</title>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <style>
    body { font: 14px/1.4 system-ui, sans-serif; margin: 2rem; }
    pre { background:#f6f8fa; padding:1rem; overflow:auto; }
    input, textarea { width: 100%; box-sizing:border-box; }
    textarea { height: 90px; }
    .row { display:grid; grid-template-columns: 1fr 160px; gap: 0.75rem; }
    button { padding: .6rem 1rem; margin-right: .5rem; }
  </style>
</head>
<body>
  <h1>MCP Proxy is running</h1>
  <p>POST <code>/ask</code> with JSON: <code>{"question": "...", "table_hint": "...", "max_rows": 100}</code></p>

  <h3>Quick test</h3>
  <textarea id="q" placeholder="Ask something...">Show 5 rows</textarea>
  <div class="row">
    <input id="table" value="supplement_sales_weekly"/>
    <input id="cap" type="number" value="50"/>
  </div>
  <p>
    <button id="ask">Ask</button>
    <button id="tables">List tables</button>
  </p>
  <pre id="out"></pre>

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
  const question = document.getElementById("q").value.trim();
  const table_hint = document.getElementById("table").value.trim();
  const max_rows = parseInt(document.getElementById("cap").value || "50", 10);
  try {
    const data = await postJSON("/ask", { question, table_hint, max_rows });
    document.getElementById("out").textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    document.getElementById("out").textContent = "ERROR: " + e.message;
  }
};

document.getElementById("tables").onclick = async () => {
  try {
    const res = await fetch("/tables");
    const data = await res.json();
    document.getElementById("out").textContent = JSON.stringify(data, null, 2);
  } catch (e) {
    document.getElementById("out").textContent = "ERROR: " + e.message;
  }
};
</script>
</body>
</html>
"""

if __name__ == "__main__":
  uvicorn.run(app, host="127.0.0.1", port=9001, reload=False)
