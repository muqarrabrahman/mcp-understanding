# My MCP Learning Notes

Simple Q&A log as I learn MCP. Revise top to bottom.

---

### Q1: What is MCP?

MCP (Model Context Protocol) is a standard way for an AI assistant (the **client**, e.g. Claude Desktop) to discover and call tools exposed by a separate program (the **server**) — using one common protocol instead of every AI app inventing its own plugin format.

**Simple analogy:** it's like USB-C for AI tools. One standard connector — any compliant client can plug into any compliant server, no custom wiring needed.

**Example:** our `server.py` exposes a `get_employee` tool. Any MCP client — Claude Desktop, Postman, the Inspector — can discover it and call it without us writing any client-specific integration code.

---

### Q2: What are the 3 main components (primitives) an MCP server can expose?

**Tools** — actions the LLM can *call* to do something (run code, query a DB, hit an API) and get a result back. Has side-effect potential. This is the only one we've used so far — `get_employee`, `list_employees`, etc., all defined with `@mcp.tool()`.

**Resources** — data the client can *read* and hand to the LLM as context, addressed by a URI (like `employees://all`). More like "fetch a document" than "call a function" — no arguments to reason about, just data. We could add one with `@mcp.resource("employees://all")` that returns a full dump for the model to read directly instead of calling a tool.

**Prompts** — reusable, parameterized prompt templates the server offers, which the client can surface to the user as a shortcut (like a slash-command), e.g. "summarize this employee's salary history." Defined with `@mcp.prompt()`.

**Simple analogy:** Tools = functions you call, Resources = files you read, Prompts = canned message templates you insert.

**Why we only used Tools:** our use case is entirely "run this query and give me an answer" — actions, not raw documents to browse — so Tools was the natural fit.

---

### Q3: How is an MCP server different from a normal backend/REST server?

A REST API is built for a developer who already knows the exact endpoints (e.g. `/employees/1`) and reads docs to call it correctly. An MCP server is built to be **discovered and driven by an LLM at runtime**: it advertises its tools (name, description, input schema), and the LLM itself decides which tool to call and with what arguments based on a plain-English question.

**Example:** we never call `get_employee(1)` ourselves. We ask "what's employee 1's info?" — the LLM reads the tool's description/schema and decides to call `get_employee(employee_id=1)` on our behalf.

---

### Q4: What's the difference between stdio and HTTP transport?

**stdio** — the client starts your server as a local subprocess and they talk by writing JSON-RPC messages directly to its stdin/stdout. No network, no port. Only works when client and server are on the *same machine*. This is what our `server.py` uses (`mcp.run()` defaults to stdio) — that's why running it alone just hangs with no output: it's waiting for a client to spawn it and start writing to its stdin.

**HTTP** (the modern "Streamable HTTP" transport) — the server runs on its own, listening on a network port/URL (e.g. `http://localhost:8000/mcp`). Any client can connect to it, even from a different machine, and multiple clients can connect to the same running server at once.

**Simple analogy:** stdio is like whispering to someone standing right next to you — only works in the same room (same machine). HTTP is like calling a phone number — the server has an address, and anyone, anywhere, can dial in.

**Example:** Claude Desktop's config gives a `command` + `args` (`python.exe server.py`) and launches the process itself — that's stdio. A hosted MCP server a whole team connects to via a shared URL would be HTTP.

---

### Q5: What is a "JSON-RPC message" exactly?

JSON-RPC is just a tiny, agreed-upon JSON shape for "call a function by name, get a result back." MCP uses it as the message format regardless of transport (stdio or HTTP) — only *how the bytes travel* changes; the message shape stays the same.

- A **request** has: `id` (so the reply can be matched to it), `method` (which action), `params` (arguments).
- A **response** has the same `id`, plus either `result` (success) or `error`.

Over stdio, each message is one line of JSON text written to stdin/stdout — no headers, no connections, just newline-delimited JSON flowing both ways.

**Example — client asks "what tools do you have?"**
```
→ client writes to server's stdin:
{"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}

← server writes to stdout:
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "tools": [
      {
        "name": "get_employee",
        "description": "Get a single employee's details by their employee_id.",
        "inputSchema": {
          "type": "object",
          "properties": { "employee_id": { "type": "integer" } },
          "required": ["employee_id"]
        }
      }
    ]
  }
}
```

**Example — client calls a tool**
```
→ client writes:
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": { "name": "get_employee", "arguments": { "employee_id": 1 } }
}

← server writes back:
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      { "type": "text", "text": "[{\"employee_id\": 1, \"first_name\": \"Alice\", ...}]" }
    ]
  }
}
```

The matching `id: 2` on both sides is how the client knows which request this response belongs to — important since stdio has no separate "connection" per call, just one shared stream.

---

### Q6: What did we actually build in this project?

A Python MCP server (`server.py`) using `FastMCP` from the official `mcp` SDK. It exposes 5 read-only tools — `list_employees`, `get_employee`, `search_employees`, `get_salary_history`, `department_salary_summary` — that query a Postgres DB (`employee`/`salary` tables).

Each tool is just a normal Python function with `@mcp.tool()` on top. The docstring becomes the tool's description and the type hints become its input schema — both shown to the LLM client automatically, no separate config needed.

---

### Q7: What's the standard flow of an MCP interaction?

1. Client launches/connects to the server.
2. **initialize** — client and server handshake (versions/capabilities).
3. **list_tools** — client asks "what tools do you have?"; server returns names, descriptions, and input schemas.
4. The LLM (inside the client) reads the user's question and decides which tool to call, with what arguments.
5. **call_tool** — client sends the tool name + arguments; server runs it (our `run_query` hits Postgres) and returns the result.
6. The client feeds that result back to the LLM, which turns it into a natural-language answer.

**Example:** user asks "who's on the Engineering team?" → client calls `list_employees(department="Engineering")` → server returns rows → LLM turns the rows into a sentence.

---

### Q8: How does `mcp dev` work, and when do we use it?

`mcp dev server.py` (from `mcp[cli]`) does two things at once: (1) launches `server.py` as a subprocess over stdio, exactly like a real client would, and (2) starts a local web app — the **Inspector** — that acts as a stand-in MCP client with a UI, so you can click "List Tools" / "Call Tool" and see the raw JSON-RPC requests/responses.

Use it while actively building/debugging tools — it's the fastest feedback loop, since you don't need Claude Desktop or Postman set up just to check a tool works.

---

### Q9: How can we access/test our server from different clients?

- **MCP Inspector** (`mcp dev server.py`) — browser UI, best for development, shows raw protocol traffic.
- **Postman** — create an "MCP Request", transport = `STDIO`, give it the command (`python.exe`) and args (`server.py`). Postman spawns the process the same way Inspector does and calls tools from a GUI form.
- **Claude Desktop** — add an entry under `mcpServers` in `claude_desktop_config.json` pointing to the same command/args. Then you just talk to it in natural language and the LLM decides which tool to call.

All three are different **clients** speaking the same protocol to the same unchanged `server.py` — that's the whole point of a standard.
