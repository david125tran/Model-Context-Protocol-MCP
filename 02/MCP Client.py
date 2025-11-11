# MCP Client.py

# ---------------------------------- Libraries ----------------------------------
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastmcp.client import Client
from fastmcp.client.transports import SSETransport
import os
from pydantic import BaseModel
import uvicorn


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

class AskPayload(BaseModel):
    question: str

@app.on_event("startup")
async def startup():
    await client.__aenter__()  # connect to MCP

@app.on_event("shutdown")
async def shutdown():
    await client.__aexit__(None, None, None)

@app.get("/search_web")
async def search_web_ep(query: str):
    res = await client.call_tool("search_web", {"query": query}) 
    return res.data

@app.post("/ask")
async def ask(payload: AskPayload):
    try:
        # Call your tool with a dict; adjust key names as your tool expects
        print({"question": payload.question})
        res = await client.call_tool("nlq_to_response", {"question": payload.question})
        data = res.data if isinstance(res.data, dict) else {"summary": str(res.data)}
        return JSONResponse(data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Chat (MCP)</title>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <style>
    body { font: 14px/1.4 system-ui, sans-serif; margin: 2rem; }
    .wrap { max-width: 800px; margin: 0 auto; }
    textarea, input, button { width: 100%; box-sizing: border-box; }
    textarea { height: 110px; }
    pre { background:#f6f8fa; padding:1rem; overflow:auto; }
    .row { display: grid; grid-template-columns: 1fr 180px; gap: 0.75rem; }
    button { padding: .6rem 1rem; }
    label { display:block; margin:.5rem 0 .25rem; font-weight:600; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Ask the LLM to Use Web Search (via MCP)</h1>

    <label for="q">Question</label>
    <textarea id="q" placeholder="e.g. Give me a summary of the current weather in Raleigh, NC."></textarea>

    <div class="row" style="margin: .75rem 0 1rem;">
      <div></div>
      <button id="ask">Ask</button>
    </div>

    <h3>Summary</h3>
    <pre id="summary"></pre>
  </div>

<script>
async function postJSON(url, data) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type":"application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(text || res.statusText);
  }
  return res.json();
}

document.getElementById("ask").addEventListener("click", async () => {
  const qEl = document.getElementById("q");
  const summaryEl = document.getElementById("summary");
  const question = qEl.value.trim();

  if (!question) {
    summaryEl.textContent = "(Please enter a question.)";
    return;
  }

  summaryEl.textContent = "Loading…";
  try {
    const data = await postJSON("/ask", { question });
    summaryEl.textContent = data.summary ?? JSON.stringify(data, null, 2) ?? "(no summary)";
  } catch (e) {
    summaryEl.textContent = "Error: " + (e.message || e);
  }
});
</script>
</body>
</html>
"""

if __name__ == "__main__":
    # Pass the app object directly
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=9001,
        reload=False
    )