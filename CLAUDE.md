# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A learning project: a single-file MCP (Model Context Protocol) server (`server.py`) that exposes read-only tools over a Postgres database (`employee` and `salary` tables). It's meant to be run by an MCP client (MCP Inspector, Claude Desktop, Postman's MCP request type) that spawns it as a subprocess and talks JSON-RPC to it over stdio — it is not a standalone web server and has no HTTP port.

## Commands

Activate the venv first (PowerShell): `.\venv\Scripts\Activate.ps1`

- Install/update dependencies: `pip install -r requirements.txt`
- (Re)create the DB schema + sample data: `python apply_schema.py` — drops and recreates `employee`/`salary` in the DB pointed to by `.env`, then inserts ~10 sample employees and their salary history
- Run the server for interactive testing (MCP Inspector): `mcp dev server.py` — prints a local URL with an auth token; open it in a browser to list/call tools and inspect raw JSON-RPC requests/responses
- Run the server directly: `python server.py` — this is the same thing a client (Claude Desktop, Postman) launches under the hood; run alone it just blocks waiting for a client to attach via stdin/stdout, with no visible output — that's expected, not a hang

There are no automated tests in this project.

## Configuration

DB connection is read from `.env` (`DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`) via `python-dotenv`. Postgres runs locally in a Docker container named `DGE-Local` (`docker inspect DGE-Local` shows the real credentials if `.env` ever needs to be regenerated).

## Architecture

- `server.py` builds one `FastMCP` instance and registers tools with the `@mcp.tool()` decorator — the function's docstring becomes the tool description and its type-hinted signature becomes the auto-generated JSON schema the client sees. Adding a new tool means adding a new decorated function; no separate registration step.
- Every tool goes through `run_query(sql, params)`, which opens a fresh `psycopg2` connection per call (no pooling — deliberately kept simple for a learning project), executes with `RealDictCursor` so rows come back as JSON-friendly dicts, and always closes the connection in a `finally` block.
- All SQL is parameterized (`%s` placeholders passed via the `params` tuple) — never string-interpolate values into a query when adding new tools here.
- `schema.sql` is the source of truth for table shape: `employee` (one row per person) and `salary` (one row per salary period, `end_date IS NULL` means currently active) — a one-to-many relationship used to demonstrate salary *history* vs *current* salary in `get_salary_history` vs `department_salary_summary`.
- `apply_schema.py` is a one-off script, not part of the server — it connects with `psycopg2` using the same `.env` and executes `schema.sql` wholesale via `conn.autocommit = True`.
