# My MCP Learning Notes

Simple Q&A log as I learn MCP. Revise top to bottom.

---

### Q1: What is MCP?

MCP (Model Context Protocol) is a standard way for an AI assistant (the **client**, e.g. Claude Desktop) to discover and call tools exposed by a separate program (the **server**) — using one common protocol instead of every AI app inventing its own plugin format.

**Simple analogy:** it's like USB-C for AI tools. One standard connector — any compliant client can plug into any compliant server, no custom wiring needed.

**Example:** our `server_stdio.py` exposes a `get_employee` tool. Any MCP client — Claude Desktop, Postman, the Inspector — can discover it and call it without us writing any client-specific integration code.

---

### Q2: What are the 3 main components (primitives) an MCP server can expose?

**Tools** — actions the LLM can *call* to do something (run code, query a DB, hit an API) and get a result back. Has side-effect potential. This is the only one we've used so far — `get_employee`, `list_employees`, etc., all defined with `@mcp.tool()`.

**Resources** — data the client can *read* and hand to the LLM as context, addressed by a URI (like `employees://all`). More like "fetch a document" than "call a function" — no arguments to reason about, just data. We added `employees://all` (a CSV dump, static — no `{param}`) and `employees://{employee_id}` (a *resource template* — the `{employee_id}` becomes a function argument, filled in per-request).

**Prompts** — reusable, parameterized prompt templates the server offers, which the client can surface to the user as a shortcut (like a slash-command), e.g. "summarize this employee's salary history." We added `salary_review_prompt(employee_id)`, defined with `@mcp.prompt()`.

**Simple analogy:** Tools = functions you call, Resources = files you read, Prompts = canned message templates you insert.

---

### Q3: How is an MCP server different from a normal backend/REST server?

A REST API is built for a developer who already knows the exact endpoints (e.g. `/employees/1`) and reads docs to call it correctly. An MCP server is built to be **discovered and driven by an LLM at runtime**: it advertises its tools (name, description, input schema), and the LLM itself decides which tool to call and with what arguments based on a plain-English question.

**Example:** we never call `get_employee(1)` ourselves. We ask "what's employee 1's info?" — the LLM reads the tool's description/schema and decides to call `get_employee(employee_id=1)` on our behalf.

---

### Q4: What's the difference between stdio and HTTP transport?

**stdio** — the client starts your server as a local subprocess and they talk by writing JSON-RPC messages directly to its stdin/stdout. No network, no port. Only works when client and server are on the *same machine*. This is what our `server_stdio.py` uses (`mcp.run()` defaults to stdio) — that's why running it alone just hangs with no output: it's waiting for a client to spawn it and start writing to its stdin.

**HTTP** (the modern "Streamable HTTP" transport) — the server runs on its own, listening on a network port/URL (e.g. `http://localhost:8500/mcp`, our own `server_http.py` from Q14). Any client can connect to it, even from a different machine, and multiple clients can connect to the same running server at once.

**Simple analogy:** stdio is like whispering to someone standing right next to you — only works in the same room (same machine). HTTP is like calling a phone number — the server has an address, and anyone, anywhere, can dial in.

**Example:** Claude Desktop's config gives a `command` + `args` (`python.exe server_stdio.py`) and launches the process itself — that's stdio. Our own `server_http.py` (Q14) is the HTTP side — a hosted server anyone with the URL can connect to.

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

A Python MCP server using `FastMCP` from the official `mcp` SDK, exposing 5 read-only tools — `list_employees`, `get_employee`, `search_employees`, `get_salary_history`, `department_salary_summary` — that query a Postgres DB (`employee`/`salary` tables), plus 3 resources and 1 prompt (see Q2).

Each tool is just a normal Python function with `@mcp.tool()` on top. The docstring becomes the tool's description and the type hints become its input schema — both shown to the LLM client automatically, no separate config needed.

It later became **two** files, `server_stdio.py` and `server_http.py` — same tools, but each fully independent with its own `FastMCP` instance, one per transport (Q14).

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

`mcp dev server_stdio.py` (from `mcp[cli]`) does two things at once: (1) launches `server_stdio.py` as a subprocess over stdio, exactly like a real client would, and (2) starts a local web app — the **Inspector** — that acts as a stand-in MCP client with a UI, so you can click "List Tools" / "Call Tool" and see the raw JSON-RPC requests/responses.

Use it while actively building/debugging tools — it's the fastest feedback loop, since you don't need Claude Desktop or Postman set up just to check a tool works.

---

### Q9: How can we access/test our server from different clients?

- **MCP Inspector** (`mcp dev server_stdio.py`) — browser UI, best for development, shows raw protocol traffic.
- **Postman** — create an "MCP Request", transport = `STDIO`, give it the command (`python.exe`) and args (`server_stdio.py`). Postman spawns the process the same way Inspector does and calls tools from a GUI form.
- **Claude Desktop** — add an entry under `mcpServers` in `claude_desktop_config.json` pointing to the same command/args. Then you just talk to it in natural language and the LLM decides which tool to call.

All three are different **clients** speaking the same protocol to the same unchanged `server_stdio.py` — that's the whole point of a standard.

---

### Q10: How do I connect this server to Postman?

1. New → **MCP Request**.
2. Transport: `STDIO`.
3. One single command field — interpreter + script together, not separate fields:
   ```
   D:\Aslase\Practice\MCP\venv\Scripts\python.exe D:\Aslase\Practice\MCP\server_stdio.py
   ```
4. Click **Connect** — Postman spawns `server_stdio.py` as a subprocess and does the `initialize` handshake for you.
5. Click **Load capabilities** — sends `tools/list`, `resources/list`, `prompts/list` and populates the sidebar.
6. Pick one (e.g. `get_employee`), fill in `employee_id`, hit **Run** — see the JSON result.

**Gotcha:** a *resource template* (URI with `{param}`, like `employees://{employee_id}`) is a different protocol call (`resources/templates/list`) than a plain resource (`resources/list`). If you only register templates, Postman's "Resources" tab can show "No resources found" even though everything is working — check for a separate templates section before assuming it's broken.

No extra config needed for `.env` — `server_stdio.py` loads it itself via `load_dotenv()` from its own folder, regardless of who launched it.

---

### Q11: How do I connect this with Claude Desktop?

**Actual working method (not the `%APPDATA%\Claude` path I originally guessed):** Claude Desktop → **Settings → Developer tab → Edit Config**. That button opens `claude_desktop_config.json` directly — no need to hunt for the folder yourself. (On this machine it turned out to live under a Microsoft Store app-container path, `...\AppData\Local\Packages\Claude_<id>\LocalCache\Roaming\Claude\`, since this install came from the Store — "Edit Config" sidesteps needing to know that.)

Add (merge into any existing `mcpServers` entries — don't overwrite them):
```json
{
  "mcpServers": {
    "employee-salary-server": {
      "command": "D:\\Aslase\\Practice\\MCP\\venv\\Scripts\\python.exe",
      "args": ["D:\\Aslase\\Practice\\MCP\\server_stdio.py"]
    }
  }
}
```
Restart Claude Desktop, then look for the tool/plug icon near the chat box — click it, `employee-salary-server` should be listed as connected with its tools/resources/prompts. Ask a plain-English question (e.g. "list employees in Engineering") and Claude's LLM reads the tool schemas and decides which one to call.

---

### Q12: What's the major difference between a Tool and a Resource?

A **Tool** is an *action* the LLM decides to invoke, reasoning out its own arguments, potentially doing real work. A **Resource** is data at a *fixed address* that gets fetched as-is — no reasoning, just "get what's at this URI."

**Example from our server:** `get_employee(employee_id=3)` (Tool) requires the LLM to *decide* to call it and *figure out* `employee_id` should be `3` from your question — that decision-making is the whole point of a tool. `employees://all` (Resource) has no decision involved — it's more like a document already sitting on the table that the client attaches as background context; the model just reads it.

**Simple analogy:** Tool = calling someone and asking a specific question tailored to the situation. Resource = a document already in the room that anyone can pick up and read.

---

### Q13: Is resource content always available to the LLM? What's available all the time?

Only **metadata** is available all the time — the list of tool names/schemas, resource names/URIs/descriptions, prompt names/args (fetched once via `list_tools` / `list_resources` / `list_prompts`). That's a menu, not the food — actual content requires an extra step, and who triggers that step differs:

- **Tools** — fully LLM-driven. The model decides mid-conversation to call one, and the result comes back into that same turn automatically.
- **Resources** — not automatic. The client (e.g. Claude Desktop) surfaces resources as attachable items, like attaching a file. A **user** has to pick "attach `employees://all`" before its content enters the LLM's context — the model can't silently pull it in on its own in most clients.
- **Prompts** — also user-triggered, like picking a slash-command from a menu.

**Example:** right after connecting, Claude "knows" `employees://all` exists the same way you know a name exists in a phone directory — it hasn't read the CSV. Ask "who's in Engineering?" and Claude calls the `list_employees` **tool**, getting the answer in that same turn. But the `employees://all` **resource**'s actual content only shows up if it's explicitly attached — same idea as attaching a PDF to a chat.

---

### Q14: How do we expose the same tools/resources/prompts over HTTP, with some form of identification?

Same server, same tools — just a different transport. `mcp.streamable_http_app()` turns our `FastMCP` instance into a normal Starlette ASGI app listening at `/mcp`, instead of talking over stdin/stdout. We run that with `uvicorn` (a real web server), so it opens an actual network port — this is the "phone number" side of Q4, where before we only had the "whisper next to you" side.

**Identification = a shared secret (Bearer token).** Since anyone who can reach the port can now call our tools, we wrap the app in a small `BearerAuthMiddleware` that checks every request's `Authorization` header against `MCP_API_KEY` (stored in `.env`, same pattern as our DB credentials) and rejects it with `401` if it doesn't match.

**Two fully independent files, on purpose:** `server_stdio.py` and `server_http.py` share **no imports at all** — each defines its own `FastMCP` instance, its own `get_connection`/`run_query`, and its own copies of every tool/resource/prompt. That's a deliberate choice for learning: connecting to one has zero chance of accidentally affecting the other, at the cost of duplicated code (in a real project you'd factor the shared logic into a common module both files import). `server_http.py` additionally wraps its app in the auth middleware and runs it via `uvicorn.run(app, host="127.0.0.1", port=8500)`.

**To test:** run `python server_http.py`, then in Postman create an MCP Request with transport = **Streamable HTTP**, URL = `http://127.0.0.1:8500/mcp`, and a header `Authorization: Bearer learn-mcp-http-key`. Remove that header and reconnect — you should get a `401` instead of the tool list, which is the "identification" actually doing its job.

**Note:** a Bearer token is the simplest possible form of identification — good for learning, not for production. Real-world MCP HTTP servers typically use full OAuth (the `mcp` SDK has `auth_server_provider`/`token_verifier` support for that), which is a much deeper topic than what we needed here.

---

### Q15: How do I connect `server_http.py` to Claude Desktop?

**First attempt failed:** a `url`/`headers` entry got rejected — "Some MCP servers could not be loaded... employee-salary-server-http" — because this build's `mcpServers` JSON only validates `command`/`args` (stdio) entries. There's no native way to tell Claude Desktop "connect to a remote HTTP URL with this header."

**Working fix: `mcp-remote`, a stdio↔HTTP bridge.** It's a small npm package whose whole job is to look like a normal stdio server to Claude Desktop, while internally opening an HTTP connection (with custom headers) to the real remote server:

```json
"employee-salary-server-http": {
  "command": "npx",
  "args": [
    "-y",
    "mcp-remote@latest",
    "http://127.0.0.1:8500/mcp",
    "--allow-http",
    "--transport",
    "http-only",
    "--header",
    "Authorization:${AUTH_HEADER}"
  ],
  "env": {
    "AUTH_HEADER": "Bearer learn-mcp-http-key"
  }
}
```

What each piece does:
- `npx -y mcp-remote@latest <url> ...` — downloads/runs `mcp-remote` on the fly; from Claude Desktop's point of view this is just another `command`/`args` stdio process, identical in shape to `server_stdio.py`'s entry.
- `--transport http-only` / `--allow-http` — force plain Streamable HTTP (our server isn't HTTPS, which `mcp-remote` otherwise refuses by default).
- `--header "Authorization:${AUTH_HEADER}"` — the header `mcp-remote` forwards to our server on every request; `${AUTH_HEADER}` is filled in from the sibling `env` block rather than hardcoded directly in `args`, so the token isn't sitting in plaintext in the visible process argument list.

**The real lesson here:** stdio is the *universal adapter*. Even to reach a remote HTTP server, Claude Desktop still only ever spawns local stdio processes — it never speaks HTTP itself. `mcp-remote` is a generic translator standing in between: stdio on the Claude Desktop side, HTTP (with headers) on our server's side. Same idea as Postman using two different transport modes for the same server, just automated into one bridge process instead of a UI toggle.
