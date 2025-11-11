# Model-Context-Protocol-MCP

---

## 01: Natural-Language AI Assistant for Supplement Sales Analytics 🛍️💬
- **Project Overview:** This module builds a local MCP server that lets users query a retail supplement sales database using **plain English** instead of SQL.
- **Highlights:** 
    - The LLM is equipped with controlled database tools. It converts user questions into safe SQL, executes them server-side, and returns structured results + summaries. Examples:
        - *“What were total Vitamin sales in Canada last quarter?”*   
        - *“Which platform sold the most Protein products?”*
    - Runs locally with a lightweight MCP server + browser UI
- **Scripts:**
    - `Local DB.py` - Loads Supplement_Sales_Weekly.csv into MySQL
    - `MCP Server.py` - Secure database MCP server + Natural Language to raw SQL code
    - `MCP Client.py` - UI for interacting with the assistant
- **🔒 Security (OWASP Top Ten Best Practices):**

| OWASP Concept | Implementation |
|---|---|
Prompt Injection Defense | SQL sanitizer enforcing SELECT-only |
Model Abuse Mitigation | Token bucket rate-limiting |
Restrict Model Tools | Table allowlist + column inspection |
Secure Output Handling | Removes multi-statements, comments, semicolons |
LLM-Safe Guards | Regex filters + query wrapping w/ `LIMIT` |
Defense-in-Depth | Raw SQL & NL-SQL paths both sandboxed |
Least-Privilege DB Access | MySQL user granted SELECT-only role |

![Client Side UI](https://github.com/david125tran/Model-Context-Protocol-MCP/blob/main/01/ui.png)

---

## 02: AI Web-Search — Real-Time Retrieval for LLMs 🌐🧠

- **Project Overview:**  This module creates a secure MCP server that forces an LLM to pull live data from the web before answering.  Instead of hallucinations, the model fetches fresh context using **Tavily Search** + **OpenAI GPT-4o-mini**, then summarizes results for the user.
- **Highlights**
  - 🔍 Forced real-time web search before answering
  - 🧱 Input validation + content sanitization
  - 🚦 Token-bucket rate-limiting (per-tool & global)
  - 🔐 Prompt-injection & misuse filtering
  - 📦 Browser-based UI via FastAPI
  - 💬 Safe LLM orchestration — **no model-initiated tool calls** (server enforces retrieval first)
- **Scripts:**
    - `MCP Server.py` - MCP server, forced web search pipeline, safety controls.  This script also has an equipped websearch `search_web()` tool that I wrote but chose not to implement (maybe I will later).
    - `MCP Client.py` - UI for interacting with the assistant
    - `guard.py` - Input sanitizers (regex filters, context limiter, secret redaction)
- **🔒 Security (OWASP Top Ten Best Practices):**

| Risk Category | Implementation |
|---|---|
Prompt Injection Defense | Regex filters for jailbreak terms + enforced system prompt |
Model Tool Abuse Prevention | Server forces web-search before model completion |
Rate Limiting | Token buckets (global + Tavily-specific) |
Input Validation | `validate_query()` + `validate_question()` length & regex checks |
Output Security | `validate_summary()` + context size trimming |
Least Privilege | No DB access; only search tool exposed |
Secrets Protection | `.env` loading + API keys never logged |
Error Safety | Sanitized exception surfacing (ToolError wrapper) |


---

