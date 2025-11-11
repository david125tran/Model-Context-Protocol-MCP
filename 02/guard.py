# guard.py

# ---------------------------------- Libraries ----------------------------------
from typing import Iterable
try:
    from mcp.server.errors import ToolError
except ImportError:
    # Fallback so code still runs if the mcp package isn't present yet
    class ToolError(Exception):
        pass
import re


# ---------------------------------- Functions ----------------------------------
DANGEROUS_WORDS = re.compile(
    r"(?i)\b(ignore previous|override.*instructions|system prompt|jailbreak|"
    r"developer mode|bypass|prompt injection|sudo rm -rf|;--|/\*|\*/|xp_cmdshell)\b"
)
SQL_SIGNS = re.compile(r"(?i)\b(UNION SELECT|--|#|/\*|\*/|;|DROP|INSERT|UPDATE|DELETE)\b")

URL_RE = re.compile(r"https?://[^\s)>\]]+")

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"(?i)aws_?(secret|access)_?key\s*[:=]\s*[A-Za-z0-9/+=]{20,}"),
]

# ---------------------------------- Functions ----------------------------------
def _enforce_length(name: str, s: str, min_len: int, max_len: int):
    if not isinstance(s, str):
        raise ToolError(f"{name} must be a string.")
    s2 = s.strip()
    if len(s2) < min_len:
        raise ToolError(f"{name} too short (min {min_len}).")
    if len(s2) > max_len:
        raise ToolError(f"{name} too long (max {max_len}).")
    return s2

def _reject_patterns(name: str, s: str, patterns: Iterable[re.Pattern]):
    for pat in patterns:
        if pat.search(s):
            raise ToolError(f"{name} failed security checks.")
    return s

def validate_query(query: str, *, min_len=3, max_len=300) -> str:
    q = _enforce_length("query", query, min_len, max_len)
    q = _reject_patterns("query", q, [DANGEROUS_WORDS, SQL_SIGNS])
    return q

def validate_question(question: str, *, min_len=3, max_len=500) -> str:
    q = _enforce_length("question", question, min_len, max_len)
    q = _reject_patterns("question", q, [DANGEROUS_WORDS])
    return q

def sanitize_context(s: str, *, max_len=8000) -> str:
    """Trim overly large web context; ensure it's string."""
    if not isinstance(s, str):
        s = str(s)
    if len(s) > max_len:
        s = s[:max_len] + "…"
    return s

def extract_urls(s: str, limit=5):
    return URL_RE.findall(s)[:limit]

def redact(s: str) -> str:
    out = s
    for pat in SECRET_PATTERNS:
        out = pat.sub("[REDACTED]", out)
    return out

def validate_summary(summary: str, *, min_len=1, max_len=2000) -> str:
    s = _enforce_length("summary", summary, min_len, max_len)
    return redact(s)