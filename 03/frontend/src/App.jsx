// src/App.jsx

// ----------------- Imports -----------------
import React, { useEffect, useMemo, useRef, useState } from "react";
import "./App.css";


// ----------------- Constants / Variables -----------------
// Store chat history
const STORAGE_KEY = "single-chat-storage";


// MCP Proxy Endpoints 
const API_URL_ASK = "http://127.0.0.1:9001/ask";
const API_URL_TABLES = "http://127.0.0.1:9001/tables";
const API_URL_DESCRIBE = (table) =>
  `http://127.0.0.1:9001/describe/${encodeURIComponent(table)}`;


export default function App() {
  // ----------------- Initialize Tables, Describe Panels, Chat, and Text -----------------
  const [tables, setTables] = useState([]);
  const [tablesStatus, setTablesStatus] = useState("Fetching tables…");
  const [selectedTable, setSelectedTable] = useState("");
  const [describeStatus, setDescribeStatus] = useState("Select a table to describe it.");
  const [describeText, setDescribeText] = useState("");
  const [isDescribing, setIsDescribing] = useState(false);

  const initialExchange = useMemo(
    () => ({
      question: "",
      answer: "Select a table in the top left and ask me questions on it to gain insights.",
      ts: Date.now(),
    }),
    []
  );

  const [rawSqlQuery, setRawSqlQuery] = useState("Raw SQL Query…");
  const [statusText, setStatusText] = useState("Waiting for a question…");
  const [rowsText, setRowsText] = useState("Rows will appear here…");


  // ----------------- Initialize Chat State (Restore from localStorage if Possible) -----------------
  const [exchange, setExchange] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) return JSON.parse(saved);
    } catch (err) {
      console.error("Failed to load exchange:", err);
    }
    return initialExchange;
  });


  // ----------------- Save Exchange to localStorage -----------------
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(exchange));
    } catch (err) {
      console.error("Failed to save exchange:", err);
    }
  }, [exchange]);

  
  // ----------------- Input `isWaiting` State -----------------
  const [input, setInput] = useState("");
  const [isWaiting, setIsWaiting] = useState(false);


  // ----------------- Auto-Scroll Bottom of Chat -----------------
  const bottomRef = useRef(null);
  useEffect(() => {
    if (bottomRef.current) bottomRef.current.scrollIntoView({ behavior: "smooth" });
  }, [exchange, isWaiting]);


  // ----------------- Chat Widget Open/Close -----------------
  const [chatOpen, setChatOpen] = useState(true);


  // ----------------- Fetch Tables 1x on Load Up -----------------
  useEffect(() => {
    const ac = new AbortController();

    async function fetchTablesOnce() {
      setTablesStatus("Fetching tables…");
      try {
        const resp = await fetch(API_URL_TABLES, {
          method: "GET",
          signal: ac.signal,
          headers: { Accept: "application/json" },
        });

        if (!resp.ok) throw new Error(await resp.text());
        const data = await resp.json();
        const list = Array.isArray(data?.tables) ? data.tables : [];

        setTables(list);
        setTablesStatus(list.length ? `Loaded ${list.length} table${list.length === 1 ? "" : "s"}.` : "No tables returned.");

        if (list.length && !selectedTable) setSelectedTable(list[0]);
      } catch (err) {
        if (err.name === "AbortError") return;
        setTables([]);
        setTablesStatus(`Error fetching tables: ${err.message}`);
      }
    }

    fetchTablesOnce();
    return () => ac.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);


  // ----------------- When a Table is Selected, Fetch the Description -----------------
  useEffect(() => {
    if (!selectedTable) return;

    const ac = new AbortController();

    async function fetchDescribe() {
      setIsDescribing(true);
      setDescribeStatus(`Describing "${selectedTable}"…`);
      setDescribeText("");

      try {
        const resp = await fetch(API_URL_DESCRIBE(selectedTable), {
          method: "GET",
          signal: ac.signal,
          headers: { Accept: "application/json" },
        });

        if (!resp.ok) throw new Error(await resp.text());
        const data = await resp.json();
        const cols = Array.isArray(data?.columns) ? data.columns : [];

        if (!cols.length) {
          setDescribeStatus(`No columns returned for "${selectedTable}".`);
          setDescribeText("");
          return;
        }

        const pretty =
          `Table: ${data.table || selectedTable}\n` +
          `Columns (${cols.length}):\n\n` +
          cols.map((c) => `• ${c?.name ?? "(unknown)"}`).join("\n");

        setDescribeStatus("Ready");
        setDescribeText(pretty);
      } catch (err) {
        if (err.name === "AbortError") return;
        setDescribeStatus(`Error: ${err.message}`);
        setDescribeText("");
      } finally {
        setIsDescribing(false);
      }
    }

    fetchDescribe();
    return () => ac.abort();
  }, [selectedTable]);


  // ----------------- Ask a Natural Language Question -----------------
  async function askMessage(text) {
    const trimmed = (text || "").trim();
    if (!trimmed || isWaiting) return;

    setExchange({ question: trimmed, answer: "Thinking…", ts: Date.now() });
    setInput("");
    setIsWaiting(true);

    try {
      const resp = await fetch(API_URL_ASK, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: trimmed,
          table_hint: selectedTable || "supplement_sales_weekly",
          max_rows: 100,
        }),
      });

      if (!resp.ok) throw new Error(await resp.text());
      const data = await resp.json();

      setRawSqlQuery(data.sql || "(No SQL returned)");
      setStatusText(data.summary || `Query returned ${data.returned ?? 0} rows`);

      const returned = typeof data.returned === "number" ? data.returned : 0;
      const sample = Array.isArray(data.rows) ? data.rows.slice(0, 5) : [];
      setRowsText(
        `Returned: ${returned}\n\nSample (first ${sample.length} rows):\n` +
          JSON.stringify(sample, null, 2)
      );

      // const summary = data.summary ? `Summary:\n${data.summary}\n\n` : "";
      // const sql = data.sql ? `SQL:\n${data.sql}\n\n` : "";
      // const rowCount = typeof data.returned === "number" ? `Returned: ${data.returned}\n\n` : "";
      // const rows = Array.isArray(data.rows)
        // ? `Rows (first ${Math.min(data.rows.length, 10)} shown):\n${JSON.stringify(data.rows.slice(0, 10), null, 2)}`
        // : "";

      setExchange((prev) => ({
        ...prev,
        answer: `✅ Query completed successfully.`.trim() || "(No data returned)",
      }));
    } catch (err) {
      const msg = `Error: ${err.message}`;
      setExchange((prev) => ({ ...prev, answer: msg }));
      setStatusText(msg);
      setRawSqlQuery("(No SQL returned)");
      setRowsText("(No rows)");
    } finally {
      setIsWaiting(false);
    }
  }


  // ----------------- UI -----------------
  return (
    <div className="App">
      {/* Subtle background decor */}
      <div className="bgOrbs" aria-hidden="true">
        <div className="orb orbA" />
        <div className="orb orbB" />
        <div className="orb orbC" />
      </div>

      {/* Top app header */}
      <div className="appHeader">
        <div className="contentRail">
          <div className="brandRow">
            <div className="brandLeft">
              <div className="brandIcon">📈</div>
              <div>
                <div className="brandTitle">Database Insights ✨</div>
                <div className="brandSubtitle">Ask questions in natural language & gain quick insights.</div>
              </div>
            </div>

            <div className="brandRight">
              <div className="pill">
                <span className="pillDot" />
                <span>{selectedTable ? `Table: ${selectedTable}` : "No table selected"}</span>
              </div>

              <button
                className="btn secondary"
                onClick={() => {
                  setExchange(initialExchange);
                  setInput("");
                  setRawSqlQuery("Raw SQL Query…");
                  setStatusText("Waiting for a question…");
                  setRowsText("Rows will appear here…");
                }}
                disabled={isWaiting}
                title="Clear outputs"
              >
                Clear
              </button>
            </div>
          </div>
        </div>
        <div className="rightRail" aria-hidden="true" />
      </div>

      {/* Top: Tables + Describe */}
      <header className="pageTopBar">
        <div className="contentRail">
          <div className="topGridFull">
            {/* Tables */}
            <section className="panelCard">
              <div className="sectionHeader">
                <span className="sectionLabel">Tables</span>
                <span className="sectionHint">{tablesStatus}</span>
              </div>

              <div className="controlRow">
                <label className="controlLabel" htmlFor="tableSelect">
                  Choose a table
                </label>
                <select
                  id="tableSelect"
                  className="selectModern"
                  value={selectedTable}
                  onChange={(e) => setSelectedTable(e.target.value)}
                  disabled={!tables.length}
                >
                  {!tables.length ? (
                    <option value="">(No tables)</option>
                  ) : (
                    tables.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))
                  )}
                </select>
              </div>

              <div className="panelBody mono panelScroll">{tables.length ? tables.join("\n") : tablesStatus}</div>
            </section>

            {/* Describe */}
            <section className="panelCard">
              <div className="sectionHeader">
                <span className="sectionLabel">Table Description</span>
                <span className={`sectionBadge ${isDescribing ? "loading" : "ready"}`}>
                  {isDescribing ? "Loading…" : describeStatus}
                </span>
              </div>

              <div className="panelBody mono panelScroll">{describeText || "Select a table to see its columns."}</div>
            </section>

            {/* Quick tips card */}
            <section className="panelCard accentCard">
              <div className="sectionHeader">
                <span className="sectionLabel">Tips</span>
                <span className="sectionHint">Try these prompts</span>
              </div>

              <div className="panelBody panelScroll tipsBody">
                <div className="tipItem">
                  <div className="tipTitle">Counts</div>
                  <div className="tipText">“How many squirrels are in the dataset?”</div>
                </div>
                <div className="tipItem">
                  <div className="tipTitle">Top N</div>
                  <div className="tipText">“Top 10 products by revenue this quarter.”</div>
                </div>
                <div className="tipItem">
                  <div className="tipTitle">By location</div>
                  <div className="tipText">“Which Hectare has the most sightings?”</div>
                </div>
                <div className="tipItem">
                  <div className="tipTitle">Data quality</div>
                  <div className="tipText">“Any missing values in key columns?”</div>
                </div>
              </div>
            </section>
          </div>
        </div>
        <div className="rightRail" aria-hidden="true" />
      </header>

      {/* Results: SQL + Summary + Rows */}
      <header className="pageTopBar">
        <div className="contentRail">
          <div className="topGridFull">
            <section className="panelCard">
              <div className="sectionHeader">
                <span className="sectionLabel">Generated SQL</span>
                <span className={`sectionBadge ${isWaiting ? "loading" : "ready"}`}>
                  {isWaiting ? "Running…" : "Ready"}
                </span>
              </div>
              <div className="panelBody mono panelScroll">{rawSqlQuery}</div>
            </section>

            <section className="panelCard">
              <div className="sectionHeader">
                <span className="sectionLabel">Summary</span>
                <span className="sectionHint">Live result overview</span>
              </div>
              <div className="panelBody panelScroll">{statusText}</div>
            </section>

            <section className="panelCard">
              <div className="sectionHeader">
                <span className="sectionLabel">Rows</span>
                <span className="sectionHint">Count + sample</span>
              </div>
              <div className="panelBody mono panelScroll">{rowsText}</div>
            </section>
          </div>
        </div>
        <div className="rightRail" aria-hidden="true" />
      </header>

      {/* Chat Launcher Button */}
      {!chatOpen && (
        <button className="chatLauncher" onClick={() => setChatOpen(true)}>
          Open Chat <span className="arrow">➤</span>
        </button>
      )}

      {/* Chat Widget */}
      {chatOpen && (
        <div className="chatWidget" role="dialog" aria-label="Chat widget">
          <div className="chatHeader">
            <div className="chatHeaderLeft">
              <div className="dot" />
              <div className="chatHeaderTitle">Insights Assistant</div>
              <span className="chatHeaderPill">✨</span>
            </div>

            <div className="chatHeaderRight">
              <button
                className="chatHeaderBtn"
                onClick={() => {
                  setExchange(initialExchange);
                  setInput("");
                  setRawSqlQuery("Raw SQL Query…");
                  setStatusText("Waiting for a question…");
                  setRowsText("Rows will appear here…");
                }}
                disabled={isWaiting}
              >
                Clear
              </button>

              <button className="chatHeaderBtn close" onClick={() => setChatOpen(false)}>
                ✕
              </button>
            </div>
          </div>

          <div className="chatBody">
            {exchange.question ? <div className="msg user">{exchange.question}</div> : null}
            <div className="msg assistant">{exchange.answer}</div>
            <div ref={bottomRef} />
          </div>

          <div className="chatFooter">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && askMessage(input)}
              disabled={isWaiting}
              placeholder="Ask a question…"
            />
            <button className="sendBtn" onClick={() => askMessage(input)} disabled={isWaiting || !input.trim()}>
              Send
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
