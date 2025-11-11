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
