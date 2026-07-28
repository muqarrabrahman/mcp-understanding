# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A learning project: two independent, intentionally-duplicated MCP (Model Context Protocol) servers exposing the same read-only tools/resources/prompt over a Postgres database (`employee` and `salary` tables) — one per transport, so each can be run/connected to separately:

- `server_stdio.py` — stdio transport. Meant to be spawned as a subprocess by an MCP client (MCP Inspector, Claude Desktop, Postman's STDIO transport) that talks JSON-RPC to it over stdin/stdout — it is not a standalone web server and has no HTTP port.
- `server_http.py` — Streamable HTTP transport. Runs as a real ASGI web server (via `uvicorn`) on `http://127.0.0.1:8500/mcp`, wrapped in a `BearerAuthMiddleware` that requires an `Authorization: Bearer <MCP_API_KEY>` header on every request.

These two files share no imports between them by design (see `MCP_NOTES.md` Q14) — each defines its own `FastMCP` instance, `get_connection`/`run_query` helpers, and the full set of tools/resources/prompt independently, so editing one has zero effect on the other. If you add a new tool, add it in both files.

## Commands

Activate the venv first (PowerShell): `.\venv\Scripts\Activate.ps1`

- Install/update dependencies: `pip install -r requirements.txt`
- (Re)create the DB schema + sample data: `python apply_schema.py` — drops and recreates `employee`/`salary` in the DB pointed to by `.env`, then inserts ~10 sample employees and their salary history
- Run the stdio server for interactive testing (MCP Inspector): `mcp dev server_stdio.py` — prints a local URL with an auth token; open it in a browser to list/call tools and inspect raw JSON-RPC requests/responses
- Run the stdio server directly: `python server_stdio.py` — this is the same thing a client (Claude Desktop, Postman STDIO) launches under the hood; run alone it just blocks waiting for a client to attach via stdin/stdout, with no visible output — that's expected, not a hang
- Run the HTTP server: `python server_http.py` — starts uvicorn on `127.0.0.1:8500`; connect to it with an MCP client using Streamable HTTP transport at `http://127.0.0.1:8500/mcp` and an `Authorization: Bearer <MCP_API_KEY>` header

There are no automated tests in this project.

## Configuration

DB connection is read from `.env` (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`) via `python-dotenv`. Postgres runs locally in a Docker container named `DGE-Local` (`docker inspect DGE-Local` shows the real credentials if `.env` ever needs to be regenerated). `.env` also holds `MCP_API_KEY`, the shared bearer token `server_http.py` checks on every request.

## Architecture

- Each server file builds its own `FastMCP` instance and registers tools with the `@mcp.tool()` decorator — the function's docstring becomes the tool description and its type-hinted signature becomes the auto-generated JSON schema the client sees. Adding a new tool means adding a new decorated function; no separate registration step.
- Every tool goes through `run_query(sql, params)`, which opens a fresh `psycopg2` connection per call (no pooling — deliberately kept simple for a learning project), executes with `RealDictCursor` so rows come back as JSON-friendly dicts, and always closes the connection in a `finally` block.
- All SQL is parameterized (`%s` placeholders passed via the `params` tuple) — never string-interpolate values into a query when adding new tools here.
- Resources: `employees://all` (CSV, from the DB), `company://info` (plain text, read from `company_info.txt` on disk — no DB involved), and `employees://{employee_id}` (a resource *template* — JSON, one employee per URI). Prompt: `salary_review_prompt(employee_id)`.
- `server_http.py` additionally wraps `mcp.streamable_http_app()` (a Starlette ASGI app) in `BearerAuthMiddleware` and serves it with `uvicorn.run(...)` — this is the only thing that differs structurally from `server_stdio.py` beyond the transport itself.
- `schema.sql` is the source of truth for table shape: `employee` (one row per person) and `salary` (one row per salary period, `end_date IS NULL` means currently active) — a one-to-many relationship used to demonstrate salary *history* vs *current* salary in `get_salary_history` vs `department_salary_summary`.
- `apply_schema.py` is a one-off script, not part of either server — it connects with `psycopg2` using the same `.env` and executes `schema.sql` wholesale via `conn.autocommit = True`.
