# Model-Context-Protocol-MCP
---
## ℹ️ About
This repository contains hands-on MCP projects that demonstrate safely giving LLMs **real-world tools** - databases, web search, and (coming next) external APIs.  Each project isolates a specific capability and security pattern, following OWASP-aligned best practices for LLM tool orchestration.
## ✅ Current Projects
| Project | Capability | Summary |
|---|---|---|
**01 - NL → SQL Database Assistant** | Databases | Secure natural-language interface over a local MySQL store with strict SQL controls |
**02 - LLM Web-Search Pipeline** | Retrieval | Forces real-time external search (Tavily) before response, with strict validation + rate limits |

### 🔜 Coming Soon (Project 03) - API Tooling
This project is designed to progress like a real-world AI engineering track:
> **Local DB → Web Retrieval → External API Execution → Beyond**

**Each Project:**
- Provides its own MCP server + UI
- Implements security checks (input validation, rate limits, prompt-guarding)
- Demonstrates **defense-in-depth** patterns for tool-enabled LLMs
- Is runnable locally and framework-agnostic


---

## Project 01: Natural-Language AI Assistant for Supplement Sales Analytics 🛍️💬
- **Project Overview:** This project builds a local MCP server that lets users query a retail supplement sales database using **plain English** instead of SQL.
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

## Project 02: AI Web-Search - Real-Time Retrieval for LLMs 🌐🧠

- **Project Overview:**  This project creates a secure MCP server that forces an LLM to pull live data from the web before answering.  Instead of hallucinations, the model fetches fresh context using **Tavily Search** + **OpenAI GPT-4o-mini**, then summarizes results for the user.
- **Highlights**
  - 🔍 Forced real-time web search before answering
  - 🧱 Input validation + content sanitization
  - 🚦 Token-bucket rate-limiting (per-tool & global)
  - 🔐 Prompt-injection & misuse filtering
  - 📦 Browser-based UI via FastAPI
  - 💬 Safe LLM orchestration - **no model-initiated tool calls** (server enforces retrieval first)
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

![Client Side UI](https://github.com/david125tran/Model-Context-Protocol-MCP/blob/main/02/ui.png)

---

