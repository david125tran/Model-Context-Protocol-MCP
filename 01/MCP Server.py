# MCP Server.py
# https://platform.openai.com/docs/mcp


# ---------------------------------- Libraries ----------------------------------
from dotenv import load_dotenv
from fastmcp import FastMCP
import logging
try:
    from mcp.server.errors import ToolError
except ImportError:
    # Fallback so code still runs if the mcp package isn't present yet
    class ToolError(Exception):
        pass

from openai import OpenAI as OpenAIClient
import os
import re
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import SQLAlchemyError
import threading
import time
from typing import Any, Dict, List
from urllib.parse import quote_plus


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


# ---------------------------------- Load LLM Environment Variables ----------------------------------
print_banner("Load LLM Environment Variables")

# Load environment variables and create OpenAI client
load_dotenv(dotenv_path=os.path.join(parent_dir, ".env"), override=True)

# Load openai api key
openai_api_key = os.getenv("OPENAI_API_KEY")

# (Do not print secrets in prod logs)
if not openai_api_key:
    raise RuntimeError("OPENAI_API_KEY not set")

# Configure APIs
openai_client = OpenAIClient(api_key=openai_api_key)

print("LLM Environment Variables loaded...")


# ---------------------------------- Load DB Environment Variables ----------------------------------
print_banner("Load DB Environment Variables")

# Load db environment variables
load_dotenv(dotenv_path=os.path.join(parent_dir, "db.env"), override=True)

# Load database variables
DB_USER             = os.getenv("mysql_username")
DB_PW               = os.getenv("mysql_pw")
DB_HOST             = os.getenv("mysql_host")
DB_PORT             = os.getenv("mysql_port")
DB_DATABASE_NAME    = os.getenv("mysql_database")
DB_TABLE_NAME       = os.getenv("mysql_table_name")

print("LLM DB Variables loaded...")


# ---------------------------------- Functions ----------------------------------
print_banner("Functions")

# Statements to prevent transactions other than SELECT from the LLM in case the LLM is 
# jailbroken from prompt injection attack
SQL_DISALLOWED_PATTERNS = [
    r";",                           # no multi-statements
    r"--", r"/\*", r"\*/",          # comments
    r"\b(drop|alter|truncate|insert|update|delete|replace|create|grant|revoke)\b",
    r"\b(load\s+data|outfile|infile)\b",
    r"\b(sleep|benchmark)\s*\(",    # time-based tricks
]

def sanitize_sql(sql: str) -> str:
    """
    Sanitizer to only allow for read-only SELECT statements and not allow other table
    transaction.  This function helps prevent prompt injection attacks.  
    """
    # Empty SQL statements
    if not sql:
        raise ToolError("Empty SQL.")
    # Strip trailing text, spaces, and trailing semicolons from LLM's query
    s = sql.strip()
    s = s.rstrip(" \t\r\n;")
    # Prevent transactions other than SELECT
    if not s.lower().startswith("select"):
        raise ToolError("Only SELECT statements are allowed.")
    lowered = s.lower()
    # Prevent any transactions that slip through other than SELECT
    for statement in SQL_DISALLOWED_PATTERNS:
        if re.search(statement, lowered):
            raise ToolError(f"Disallowed SQL construct matched: {statement}")
    return s

def referenced_tables(sql_text: str) -> set[str]:
    """
    Extract table names after FROM/JOIN; handles optional backticks and schema qualifiers.
    """
    pat = re.compile(r"\b(?:from|join)\s+`?([\w.]+)`?", re.I)
    names = set()
    for name in pat.findall(sql_text):
        names.add(name.split(".")[-1])  # drop schema prefix if present
    return names

def enforce_table_allowlist(sql: str, insp) -> None:
    """
    Ensure all referenced tables are in the allowlist/visible set.
    """
    norm = lambda s: s.lower() if isinstance(s, str) else s
    visible = insp.get_table_names()
    visible_norm = {norm(t) for t in visible}
    if ALLOWLIST:
        visible_norm = {t for t in visible_norm if t in {norm(a) for a in ALLOWLIST}}
    if not visible_norm:
        raise ToolError("No readable tables available.")
    refs = {norm(n) for n in referenced_tables(sql)}
    if refs and not refs.issubset(visible_norm):
        raise ToolError(
            f"SQL references disallowed tables: {', '.join(sorted(refs - visible_norm))}"
        )

def guard_table(name: str) -> str:
    if not name:
        raise ToolError("Invalid table name.")
    if ALLOWLIST and name.lower() not in ALLOWLIST:
        raise ToolError(f"Table '{name}' is not in allowlist.")
    return name

def is_select(sql: str) -> None:
    if not sql or not sql.strip().lower().startswith("select"):
        raise ToolError("Only SELECT queries are allowed.")

def rows_to_dicts(result) -> List[Dict[str, Any]]:
    return [dict(r._mapping) for r in result]

print("Functions defined...")


# ---------------------------------- Rate Limiting: Token Bucket ----------------------------------
print_banner("Rate Limiting: Token Bucket")
class TokenBucket:
    """
    capacity: max tokens the bucket can hold
    refill_rate: tokens added per second
    """
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self.tokens = float(capacity)
        self.last = time.monotonic()
        self._lock = threading.Lock()

    def consume(self, n: float = 1.0) -> bool:
        with self._lock:
            now = time.monotonic()
            elapsed = now - self.last
            # refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last = now
            if self.tokens >= n:
                self.tokens -= n
                return True
            return False
        
# Rate limiting (token bucket)
GLOBAL_BUCKET_CAPACITY = int(os.getenv("RATE_CAPACITY_GLOBAL", "60"))     # max 60 requests burst
GLOBAL_BUCKET_REFILL   = float(os.getenv("RATE_REFILL_GLOBAL", "1.0"))    # 1 token/sec (~60/min)

SQL_BUCKET_CAPACITY    = int(os.getenv("RATE_CAPACITY_SQL", "20"))        # burst for heavy tools
SQL_BUCKET_REFILL      = float(os.getenv("RATE_REFILL_SQL", "0.33"))      # ~20/min

NL2SQL_BUCKET_CAPACITY = int(os.getenv("RATE_CAPACITY_NL2SQL", "10"))     # stricter
NL2SQL_BUCKET_REFILL   = float(os.getenv("RATE_REFILL_NL2SQL", "0.16"))   # ~10/min

# Buckets (in-memory)
GLOBAL_BUCKET  = TokenBucket(GLOBAL_BUCKET_CAPACITY, GLOBAL_BUCKET_REFILL)
SQL_BUCKET     = TokenBucket(SQL_BUCKET_CAPACITY, SQL_BUCKET_REFILL)
NL2SQL_BUCKET  = TokenBucket(NL2SQL_BUCKET_CAPACITY, NL2SQL_BUCKET_REFILL)

def require_tokens(bucket: TokenBucket, n: float = 1.0):
    if not bucket.consume(n):
        print("User is being throttled...")
        raise ToolError("Rate limit exceeded. Please retry later.")
    


print("TokenBucket class defined...")


# ---------------------------------- MCP Server Config ----------------------------------
print_banner("MCP Server Config")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Model
MODEL_NAME = "gpt-4o-mini"

# DB Engine
def engine():
    host = DB_HOST
    port = DB_PORT
    name = DB_DATABASE_NAME
    user = DB_USER
    pw   = DB_PW
    url = f"mysql+pymysql://{user}:{quote_plus(pw)}@{host}:{port}/{name}"
    return create_engine(url, pool_pre_ping=True, pool_recycle=3600, future=True)

ENGINE = engine()

# Restrict what the LLM can touch 
ALLOWLIST = {t.strip().lower() for t in os.getenv("mysql_table_allowlist", "").split(",") if t.strip()}

SERVER_INSTRUCTIONS = """
MCP server exposing safe, read-only database tooling plus an LLM-powered NL→SQL tool.
Use list_tables/describe_table/preview to understand schema, then run sql_query or nl2sql_query.
All operations must be read-only.
"""

print("MCP Server Configuration set")


# ---------------------------------- Server Side Logic ----------------------------------
print_banner("Server Side Logic")

def create_server():
    mcp = FastMCP(name="DB+LLM Server", instructions=SERVER_INSTRUCTIONS)

    @mcp.tool()
    def list_tables() -> Dict[str, Any]:
        """
        Return list of readable tables.
        """
        # Rate limiting
        require_tokens(GLOBAL_BUCKET, 1)
        # Produce an inspection object for the ENGINE target
        insp = inspect(ENGINE)
        # Get a sorted list of tables 
        tables = sorted(insp.get_table_names())
        # Return only tables in the allowed list
        tables = [t for t in tables if t.lower() in ALLOWLIST]
        return {"tables": tables}

    @mcp.tool()
    def describe_table(table: str) -> Dict[str, Any]:
        """
        Return columns + types for a table.
        """
        # Rate limiting
        require_tokens(GLOBAL_BUCKET, 1)
        # Check if in allowed list and not None
        table = guard_table(table)
        # Produce an inspection object for the ENGINE target
        insp = inspect(ENGINE)
        # Is table valid
        if table not in insp.get_table_names():
            raise ToolError(f"Table '{table}' not found.")
        # Get a list of columns in the table
        cols = [{"name": c["name"], "type": str(c["type"]), "nullable": c.get("nullable", True)}
                for c in insp.get_columns(table)]
        return {"table": table, "columns": cols}

    @mcp.tool()
    def preview(table: str, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """
        Preview first N rows of a table.
        """
        # Rate limiting
        require_tokens(GLOBAL_BUCKET, 1)
        # Check if in allowed list and not None
        table = guard_table(table)
        # Set a limit
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        sql = text(f"SELECT * FROM `{table}` LIMIT :limit OFFSET :offset")
        try:
            with ENGINE.connect().execution_options(timeout=15) as conn:
                res = conn.execute(sql, {"limit": limit, "offset": offset})
                rows = rows_to_dicts(res)
        except SQLAlchemyError as e:
            raise ToolError(str(e))
        return {"table": table, "rows": rows, "count": len(rows)}

    @mcp.tool()
    def sql_query(sql: str, params: Dict[str, Any] | None = None, max_rows: int = 1000) -> Dict[str, Any]:
        """
        Run a read-only SELECT with limits. (Raw SQL path)
        """
        # Rate limiting
        # Cap first, then compute row_cost from the capped value
        max_rows = max(1, min(int(max_rows), 5000))
        row_cost = min(max_rows / 1000.0, 4.0)
        require_tokens(SQL_BUCKET, 1 + row_cost)
        # Sanitize the raw sql code and prevent prompt injection
        sql = sanitize_sql(sql)
        # Produce an inspection object for the ENGINE target
        insp = inspect(ENGINE)
        # Ensure referenced table is in the allowlist/visible set.
        enforce_table_allowlist(sql, insp)
        # Max rows
        max_rows = max(1, min(int(max_rows), 5000))
        wrapped = f"SELECT * FROM ({sql}) as _sub LIMIT :_cap"
        try:
            with ENGINE.connect().execution_options(timeout=20) as conn:
                res = conn.execute(text(wrapped), {"_cap": max_rows, **(params or {})})
                rows = rows_to_dicts(res)
        except SQLAlchemyError as e:
            raise ToolError(str(e))
        return {"rows": rows, "returned": len(rows), "capped_at": max_rows}

    @mcp.tool()
    async def nl2sql_query(
        question: str,
        table_hint: str | None = None,
        max_rows: int = 1000,
    ) -> Dict[str, Any]:
        """
        Convert a natural-language question to SQL (read-only), execute it, and (optionally) summarize.
        - Strips trailing semicolons from model SQL (prevents syntax error when wrapping).
        - Enforces allowlist / visible tables.
        - Accepts case-insensitive table_hint.
        """
        # Rate limiting
        require_tokens(GLOBAL_BUCKET, 1)
        # Cap first, then compute row_cost from the capped value
        max_rows = max(1, min(int(max_rows), 5000))
        row_cost = min(max_rows / 1000.0, 4.0)
        require_tokens(NL2SQL_BUCKET, 1 + row_cost)
        # Produce an inspection object for the ENGINE target
        insp = inspect(ENGINE)
        # Get a list of tables 
        visible_tables = insp.get_table_names()

        # Normalize for comparisons (MySQL table names are case-insensitive on Windows/macOS by default)
        norm = lambda s: s.lower() if isinstance(s, str) else s
        visible_norm = {norm(t): t for t in visible_tables}  # map lower->original

        # Apply allowlist in a case-insensitive way
        if ALLOWLIST:
            allow_norm = {norm(t) for t in ALLOWLIST}
            visible_norm = {k: v for k, v in visible_norm.items() if k in allow_norm}

        if not visible_norm:
            raise ToolError("No readable tables are available. Check mysql_table_allowlist or DB credentials.")

        # Resolve table_hint case-insensitively
        resolved_table_hint = None
        if table_hint:
            th = norm(table_hint)
            if th in visible_norm:
                resolved_table_hint = visible_norm[th]

        # Gather lightweight schema context
        schema = {}
        for t in visible_norm.values():
            if resolved_table_hint and t != resolved_table_hint:
                continue
            cols = [c["name"] + " " + str(c["type"]) for c in insp.get_columns(t)]
            schema[t] = cols

        # Configure system prompt.  Prompt the model to produce safe, single-statement SELECT without trailing semicolon
        system_prompt = (
            "You translate questions into **pure SELECT SQL** for MySQL.\n"
            "Rules: read-only; no DDL/DML; no CTEs; no multi-statements; "
            "prefer simple projections; ALWAYS include a LIMIT; "
            "if table or column names contain spaces/special characters, wrap them in backticks; "
            "DO NOT include a trailing semicolon.\n"
            "Return ONLY SQL between <sql> and </sql> tags."
        )

        # Form the user prompt
        user = (
            f"Question: {question}\n\nSchema:\n" +
            "\n".join(f"- {t}: {', '.join(cols[:20])}" for t, cols in schema.items())
        )
        # Message the LLM
        try:
            chat = openai_client.chat.completions.create(
                model=MODEL_NAME,
                temperature=0.0,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user},
                ],
            )
            raw = chat.choices[0].message.content or ""
        except Exception as e:
            raise ToolError(f"LLM error: {e}")

        # Extract the raw SQL code between the '<sql>...</sql>'
        m = re.search(r"<sql>\s*(.+?)\s*</sql>", raw, flags=re.S | re.I)
        if not m:
            raise ToolError("Could not extract SQL from model output.")
        sql = m.group(1).strip()

        # Sanitize & validate
        sql = sanitize_sql(sql)
        enforce_table_allowlist(sql, insp)

        # Execute with safety cap (wrapped subquery)
        max_rows = max(1, min(int(max_rows), 5000))
        wrapped = f"SELECT * FROM ({sql}) as _sub LIMIT :_cap"

        try:
            with ENGINE.connect().execution_options(timeout=25) as conn:
                res = conn.execute(text(wrapped), {"_cap": max_rows})
                rows = rows_to_dicts(res)
        except SQLAlchemyError as e:
            raise ToolError(f"DB error: {e}")

        # Brief summary
        SEND_DATA_TO_LLM = True  # flip to True if to send a few sample rows upstream (with redaction)

        # Reinitialize summary to None
        summary = None

        # Send a message to LLM
        try:
            if SEND_DATA_TO_LLM and rows:
                sample = rows[:5]
                summary_prompt = (
                    f"Question: {question}\nRows returned: {len(rows)}.\n"
                    f"Sample rows (JSON): {sample}"
                )
            else:
                cols = list(rows[0].keys()) if rows else []
                summary_prompt = (
                    f"Question: {question}\nRows returned: {len(rows)}.\n"
                    f"Columns: {cols}\n"
                    "Summarize the result set shape and likely content briefly."
                )

            s = openai_client.chat.completions.create(
                model=MODEL_NAME,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": "Summarize briefly and factually."},
                    {"role": "user", "content": summary_prompt},
                ],
            )
            summary = s.choices[0].message.content
        except Exception:
            summary = None

        return {
            "question": question,
            "sql": sql,
            "rows": rows,
            "returned": len(rows),
            "capped_at": max_rows,
            "summary": summary,
        }

    return mcp


if __name__ == "__main__":
    mcp = create_server()
    # Local-only by default; switch to a reverse proxy + TLS if exposing
    mcp.run(transport="sse", host="127.0.0.1", port=8000)
