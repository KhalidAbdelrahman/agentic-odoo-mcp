# Cheat Sheet — Odoo, MCP Server, and Tunnel Commands

A reference for every command used to get Foundry talking to Odoo, and what each one actually does.

---

## The three things that must be running at once

| Process | What it is | Where it listens |
|---|---|---|
| Odoo | The CRM app + Postgres, via Docker Compose | `localhost:8069` |
| MCP server | Your Python script, translating MCP calls into Odoo XML-RPC calls | `localhost:8000` |
| Tunnel (cloudflared/ngrok) | Relays a public HTTPS URL to `localhost:8000` | Public internet |

If any one stops, the chain from Foundry to Odoo breaks. Three separate terminal tabs, all left running.

---

## Odoo (Docker)

```bash
docker compose up -d
```
Starts Odoo + Postgres containers in the background (`-d` = detached, keeps running after you close the terminal).

```bash
docker compose logs -f odoo
```
Streams Odoo's live log output — `-f` follows new lines as they appear. Use this to watch for startup errors.

```bash
docker compose exec db pg_dump -U odoo -Fc agentic-crm-demo > backup.dump
```
Takes a full database snapshot you can restore later — run this once your demo data looks correct.

---

## Testing the Odoo XML-RPC connection directly

```python
import xmlrpc.client
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, username, password, {})
```
Confirms Odoo will accept your credentials over its external API, before building anything on top of it. Returns an integer user ID on success, `False` on failure.

```python
db_service = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/db")
db_service.list()
```
Lists every database Odoo knows about — use this if you're not 100% sure of the exact database name (it's case-sensitive).

**Why visiting `http://localhost:8069/xmlrpc/2/common` in a browser fails:** that endpoint only accepts `POST` requests carrying an XML-RPC payload. A browser sends a plain `GET`, so you correctly get "Method Not Allowed" — that error actually confirms the endpoint exists.

---

## Python environment (MCP server)

```bash
pip install "mcp[cli]<2.0"
```
Installs the MCP Python SDK. Pinned below version 2.0 deliberately — the SDK renamed its main class (`FastMCP` → `MCPServer`) in a 2026-07-28 protocol update, and client-side support (including Foundry's) for that new revision is still rolling out. `<2.0` keeps you on the interoperable line.

```bash
uv run python odoo_mcp_server.py
```
Runs the script inside its project's managed virtual environment (`uv` handles dependency resolution automatically) — equivalent to activating a venv and running `python odoo_mcp_server.py` yourself.

---

## Running the MCP server — two very different modes

```bash
npx @modelcontextprotocol/inspector uv run python odoo_mcp_server.py
```
**For interactive testing only.** The Inspector spawns your script as a subprocess and talks to it over **stdio** (stdin/stdout) — nothing is listening on any network port in this mode. Opens a local web UI (with a security token in the URL) where you can click through and manually call each tool. Good for debugging; useless for a tunnel, since there's no port for the tunnel to point at.

```bash
uv run python odoo_mcp_server.py --http
```
**For the real, persistent server.** Starts the same script listening on an actual TCP port (`0.0.0.0:8000` by default, via `MCP_HOST`/`MCP_PORT`), using Streamable HTTP transport. This is the process a tunnel needs to be pointed at.

---

## Finding and killing a stuck process on a port

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
```
Lists whatever process is currently bound to port 8000 — useful when you get `address already in use`. Shows the PID in the output.

```bash
kill -9 <PID>
```
Force-kills that process by its ID, freeing the port.

---

## Testing the server's HTTP endpoint

```bash
curl -i http://localhost:8000/mcp
```
Sends a plain request to the MCP endpoint. A `406 Not Acceptable` / `"Client must accept text/event-stream"` response is actually **success** — it confirms the server is up and correctly enforcing the Streamable HTTP protocol, which requires the client to declare it accepts a streaming response. `curl -i` shows response headers (`-i`) alongside the body, which is how you can see the status code.

**Why visiting the URL in a browser shows a blank page:** same reason as the XML-RPC endpoint above — a browser `GET` isn't the request shape MCP expects. This doesn't mean anything is broken.

---

## Tunnels — exposing localhost to the internet

### ngrok

```bash
ngrok config add-authtoken YOUR_TOKEN
```
One-time step linking the `ngrok` CLI to your account.

```bash
ngrok http 8000
```
Opens a tunnel from a public `https://*.ngrok-free.app` URL to `localhost:8000`. Prints the forwarding URL and starts a local dashboard at `localhost:4040` (ngrok's own traffic inspector — unrelated to your server's port).

```bash
which ngrok
ngrok version
```
Diagnostic commands — confirm which `ngrok` binary is actually first in your `PATH`, and what version it reports. Useful when an upgrade doesn't seem to take effect (usually an old binary elsewhere in `PATH` is shadowing the new one).

### Cloudflare Tunnel (the one that ended up working)

```bash
brew install cloudflared
```
Installs Cloudflare's tunnel client via Homebrew.

```bash
cloudflared tunnel --url http://localhost:8000
```
Opens a "quick tunnel" — no account needed — from a random `https://*.trycloudflare.com` URL to `localhost:8000`. Prints a connectivity pre-check (DNS, UDP/QUIC, TCP, API reachability) before confirming the tunnel is healthy. This URL is temporary: it dies when you `Ctrl+C` the process, and a fresh run gives you a new random URL.

```bash
curl -i https://your-tunnel-url.trycloudflare.com/mcp
```
Same test as the local `curl`, but through the tunnel — confirms the full path (internet → Cloudflare → your Mac → MCP server) is working. Should return the same `406` response as the local test.

---

## Environment variables the MCP server reads

| Variable | Purpose | Example |
|---|---|---|
| `ODOO_URL` | Where Odoo is running | `http://localhost:8069` |
| `ODOO_DB` | Exact database name (case-sensitive) | `agentic-crm-demo` |
| `ODOO_USERNAME` | Login for the least-privilege demo user | `agent@demo.local` |
| `ODOO_PASSWORD` | That user's password | *(required — server exits if unset)* |
| `MCP_HOST` | Interface the MCP server binds to | `0.0.0.0` (needed for tunnels to reach it) |
| `MCP_PORT` | Port the MCP server listens on | `8000` |

Set these with `export VAR="value"` before running the server, in the same terminal tab (they only persist for that shell session unless added to a shell profile).

---

## The full startup sequence, in order

```bash
# Terminal 1 — Odoo
docker compose up -d

# Terminal 2 — MCP server
export ODOO_URL="http://localhost:8069"
export ODOO_DB="agentic-crm-demo"
export ODOO_USERNAME="agent@demo.local"
export ODOO_PASSWORD="your_agent_password"
export MCP_HOST="0.0.0.0"
export MCP_PORT="8000"
uv run python odoo_mcp_server.py --http

# Terminal 3 — tunnel
cloudflared tunnel --url http://localhost:8000

# Terminal 4 (or reuse any tab) — verify
curl -i http://localhost:8000/mcp
curl -i https://your-tunnel-url.trycloudflare.com/mcp
```

Once both `curl` checks return the same `406` response, the tunnel URL + `/mcp` is ready to paste into a Foundry Toolbox.