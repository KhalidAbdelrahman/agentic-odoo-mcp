"""
Odoo MCP Server — Meridian Fleet Technologies Agentic CRM Demo
================================================================

Wraps the Odoo XML-RPC connection from Phase 1 as MCP tools a Foundry
hosted agent can call. Tools map directly to the four agent scenarios
from the demo plan:

  Sales Pipeline Agent    -> find_stalled_opportunities, create_followup_task
  Customer Risk Agent     -> list_accounts_needing_attention,
                              explain_account_risk, escalate_case
  Meeting Prep Agent      -> prepare_meeting_brief
  Executive Reporting Agent -> get_weekly_executive_summary

Design notes:
  - Authenticates as the least-privilege "Foundry Agent (Demo)" user
    (Setup Guide Step 6), not admin — this is the credential boundary
    the Governance checklist calls for.
  - Read-only tools (risk lists, briefs, stalled-deal search, exec
    summary) are unguarded. The two write tools (create_followup_task,
    escalate_case) are the "low-risk demo actions" the plan scoped for
    Phase 2 — task/case creation only, no destructive or financial writes.
  - Cases live in a "Support Cases" Project (Community-compatible
    substitute for the Enterprise-only Helpdesk app — see Phase 1 notes).

Install:
    pip install "mcp[cli]<2.0" 
    (pinned to the legacy SDK line for current client interoperability —
    see the 2026-07-28 protocol rename before switching to mcp>=2.0)

Run locally for testing:
    npx @modelcontextprotocol/inspector python odoo_mcp_server.py

Run for Foundry (Streamable HTTP):
    python odoo_mcp_server.py --http
"""

import os
import sys
import xmlrpc.client
from datetime import date, datetime, timedelta

from mcp.server.fastmcp import FastMCP
import dotenv
dotenv.load_dotenv()
# ---------------------------------------------------------------------------
# CONFIG — set via environment variables; do not hardcode credentials
# ---------------------------------------------------------------------------
ODOO_URL = os.environ.get("ODOO_URL")
ODOO_DB = os.environ.get("ODOO_DB")
ODOO_USERNAME = os.environ.get("ODOO_USERNAME")
ODOO_PASSWORD = os.environ.get("ODOO_PASSWORD")

if not ODOO_PASSWORD:
    print("ERROR: set ODOO_PASSWORD as an environment variable before running.",
          file=sys.stderr)
    sys.exit(1)

_common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
_uid = _common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})
if not _uid:
    print(f"ERROR: Odoo authentication failed for {ODOO_USERNAME} on {ODOO_DB}.",
          file=sys.stderr)
    sys.exit(1)

_models = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")


def _execute(model, method, *args, **kwargs):
    return _models.execute_kw(ODOO_DB, _uid, ODOO_PASSWORD, model, method, list(args), kwargs)


def _search_read(model, domain, fields, limit=None, order=None):
    kwargs = {"fields": fields}
    if limit:
        kwargs["limit"] = limit
    if order:
        kwargs["order"] = order
    return _execute(model, "search_read", domain, **kwargs)


def _days_since(date_str):
    """date_str like '2026-06-01 09:00:00' or '2026-06-01' -> integer days ago."""
    if not date_str:
        return None
    d = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    return (date.today() - d).days


def _find_account(name_fragment):
    """Fuzzy-match an account by partial name. Returns the first match or None."""
    matches = _search_read(
        "res.partner",
        [["is_company", "=", True], ["name", "ilike", name_fragment]],
        ["id", "name"], limit=1,
    )
    return matches[0] if matches else None


# ---------------------------------------------------------------------------
# MCP SERVER
# ---------------------------------------------------------------------------
mcp = FastMCP("odoo-crm")


@mcp.tool()
def list_accounts_needing_attention(limit: int = 10) -> str:
    """Rank accounts by combined risk: open case count/urgency, days since
    last activity, and open opportunity value. Use this to answer
    'which customers need attention today?' with reasons per account."""
    accounts = _search_read("res.partner", [["is_company", "=", True]], ["id", "name"])
    scored = []

    for acc in accounts:
        aid = acc["id"]
        cases = _search_read(
            "project.task",
            [["partner_id", "=", aid], ["project_id.name", "=", "Support Cases"],
             ["stage_id.name", "!=", "Resolved"]],
            ["id", "tag_ids"],
        )
        urgent_cases = sum(1 for c in cases if any("Urgent" in str(t) for t in
                            _execute("project.tags", "read", c["tag_ids"], fields=["name"]))) if cases else 0

        opps = _search_read(
            "crm.lead",
            [["partner_id", "=", aid], ["type", "=", "opportunity"],
             ["stage_id.name", "not in", ["Won"]]],
            ["id", "expected_revenue"],
        )
        open_value = sum(o["expected_revenue"] for o in opps)

        activities = _search_read(
            "mail.activity", [["res_model", "=", "res.partner"], ["res_id", "=", aid]],
            ["date_deadline"], order="date_deadline desc", limit=1,
        )
        last_activity_days = _days_since(activities[0]["date_deadline"]) if activities else 999

        score = (len(cases) * 2) + (urgent_cases * 3) + (10 if open_value > 50000 else 0) \
            + (5 if last_activity_days and last_activity_days > 30 else 0)

        if score > 0:
            scored.append({
                "name": acc["name"], "score": score, "open_cases": len(cases),
                "urgent_cases": urgent_cases, "open_opportunity_value": open_value,
                "days_since_last_activity": last_activity_days,
            })

    scored.sort(key=lambda x: -x["score"])
    top = scored[:limit]
    if not top:
        return "No accounts currently show risk signals."

    lines = []
    for a in top:
        reasons = []
        if a["urgent_cases"]:
            reasons.append(f"{a['urgent_cases']} urgent open case(s)")
        elif a["open_cases"]:
            reasons.append(f"{a['open_cases']} open case(s)")
        if a["open_opportunity_value"] > 50000:
            reasons.append(f"${a['open_opportunity_value']:,.0f} open opportunity value")
        if a["days_since_last_activity"] and a["days_since_last_activity"] > 30:
            reasons.append(f"no activity in {a['days_since_last_activity']} days")
        lines.append(f"- {a['name']}: {'; '.join(reasons) if reasons else 'moderate signals'}")

    return "Accounts needing attention today, ranked:\n" + "\n".join(lines)


@mcp.tool()
def explain_account_risk(account_name: str) -> str:
    """Multi-factor risk explanation for one account: open cases, open
    opportunities, and recent activity history. Use this to answer
    'why is this account risky?'"""
    acc = _find_account(account_name)
    if not acc:
        return f"No account found matching '{account_name}'."
    aid = acc["id"]

    cases = _search_read(
        "project.task",
        [["partner_id", "=", aid], ["project_id.name", "=", "Support Cases"]],
        ["name", "stage_id", "tag_ids"],
    )
    opps = _search_read(
        "crm.lead", [["partner_id", "=", aid], ["type", "=", "opportunity"]],
        ["name", "stage_id", "expected_revenue", "probability"],
    )
    activities = _search_read(
        "mail.activity", [["res_model", "=", "res.partner"], ["res_id", "=", aid]],
        ["summary", "date_deadline"], order="date_deadline desc", limit=3,
    )

    parts = [f"Risk summary for {acc['name']}:"]
    if cases:
        parts.append("Open/recent cases:")
        for c in cases:
            parts.append(f"  - {c['name']} (stage: {c['stage_id'][1] if c['stage_id'] else 'n/a'})")
    else:
        parts.append("No cases on record.")

    if opps:
        parts.append("Opportunities:")
        for o in opps:
            parts.append(f"  - {o['name']}: ${o['expected_revenue']:,.0f} "
                         f"at {o['probability']}% (stage: {o['stage_id'][1] if o['stage_id'] else 'n/a'})")

    if activities:
        parts.append("Recent activity:")
        for a in activities:
            parts.append(f"  - {a['summary']} ({a['date_deadline']})")
    else:
        parts.append("No recent activity logged — a stale-engagement signal.")

    return "\n".join(parts)


@mcp.tool()
def prepare_meeting_brief(account_name: str) -> str:
    """Account background, key contacts, open cases, and active
    opportunities, for prepping a customer call."""
    acc = _find_account(account_name)
    if not acc:
        return f"No account found matching '{account_name}'."
    aid = acc["id"]

    contacts = _search_read(
        "res.partner", [["parent_id", "=", aid], ["is_company", "=", False]],
        ["name", "function", "email"],
    )
    opps = _search_read(
        "crm.lead", [["partner_id", "=", aid], ["type", "=", "opportunity"],
                     ["stage_id.name", "!=", "Won"]],
        ["name", "expected_revenue", "stage_id"],
    )
    cases = _search_read(
        "project.task",
        [["partner_id", "=", aid], ["project_id.name", "=", "Support Cases"],
         ["stage_id.name", "!=", "Resolved"]],
        ["name", "stage_id"],
    )

    parts = [f"Meeting brief — {acc['name']}", ""]
    parts.append("Key contacts:")
    for c in contacts:
        parts.append(f"  - {c['name']}, {c.get('function') or 'role not set'} ({c.get('email', 'no email')})")

    parts.append("\nActive opportunities:")
    if opps:
        for o in opps:
            parts.append(f"  - {o['name']}: ${o['expected_revenue']:,.0f} (stage: {o['stage_id'][1]})")
    else:
        parts.append("  None currently open.")

    parts.append("\nOpen issues:")
    if cases:
        for c in cases:
            parts.append(f"  - {c['name']} (stage: {c['stage_id'][1]})")
    else:
        parts.append("  None currently open.")

    return "\n".join(parts)


@mcp.tool()
def find_stalled_opportunities(days_threshold: int = 30) -> str:
    """Opportunities with no logged activity in the last N days that
    aren't already Won or Lost. Use this to answer 'which deals are
    likely to slip this month?'"""
    opps = _search_read(
        "crm.lead",
        [["type", "=", "opportunity"], ["active", "=", True],
         ["stage_id.name", "not in", ["Won"]]],
        ["id", "name", "partner_id", "expected_revenue", "stage_id", "date_deadline"],
    )

    stalled = []
    for o in opps:
        activities = _search_read(
            "mail.activity", [["res_model", "=", "crm.lead"], ["res_id", "=", o["id"]]],
            ["date_deadline"], order="date_deadline desc", limit=1,
        )
        last_days = _days_since(activities[0]["date_deadline"]) if activities else 999
        deadline_passed = o["date_deadline"] and o["date_deadline"] < str(date.today())

        if (last_days and last_days > days_threshold) or deadline_passed:
            stalled.append({
                "name": o["name"], "account": o["partner_id"][1] if o["partner_id"] else "n/a",
                "value": o["expected_revenue"], "stage": o["stage_id"][1] if o["stage_id"] else "n/a",
                "last_activity_days": last_days, "deadline_passed": deadline_passed,
            })

    if not stalled:
        return f"No opportunities appear stalled (no activity in {days_threshold}+ days)."

    stalled.sort(key=lambda x: -x["value"])
    lines = [f"Opportunities likely to slip (no activity in {days_threshold}+ days or past deadline):"]
    for s in stalled:
        flag = "deadline already passed" if s["deadline_passed"] else f"{s['last_activity_days']} days since last activity"
        lines.append(f"  - {s['name']} (${s['value']:,.0f}, stage: {s['stage']}) — {flag}")
    return "\n".join(lines)


@mcp.tool()
def get_weekly_executive_summary() -> str:
    """Aggregate customer and pipeline health: open pipeline value,
    counts of at-risk accounts and urgent cases, and top risks. Use
    this to answer 'give me this week's customer and pipeline health.'"""
    all_opps = _search_read(
        "crm.lead", [["type", "=", "opportunity"], ["stage_id.name", "!=", "Won"]],
        ["expected_revenue"],
    )
    total_pipeline = sum(o["expected_revenue"] for o in all_opps)

    urgent_cases = _search_read(
        "project.task",
        [["project_id.name", "=", "Support Cases"], ["stage_id.name", "!=", "Resolved"]],
        ["tag_ids"],
    )
    urgent_count = 0
    for c in urgent_cases:
        tags = _execute("project.tags", "read", c["tag_ids"], fields=["name"]) if c["tag_ids"] else []
        if any("Urgent" in t["name"] for t in tags):
            urgent_count += 1

    top_risk_summary = list_accounts_needing_attention(limit=3)

    return (
        f"Weekly Customer & Pipeline Health Summary\n"
        f"------------------------------------------\n"
        f"Open pipeline value: ${total_pipeline:,.0f} across {len(all_opps)} opportunities\n"
        f"Open support cases: {len(urgent_cases)} total, {urgent_count} urgent\n\n"
        f"Top risks this week:\n{top_risk_summary}\n\n"
        f"Recommended focus: address urgent cases first, then review "
        f"opportunities with passed deadlines before month close."
    )


# ---------------------------------------------------------------------------
# WRITE TOOLS — guarded, low-risk actions only (per Governance checklist)
# ---------------------------------------------------------------------------

@mcp.tool()
def create_followup_task(account_name: str, title: str, due_in_days: int = 3,
                          notes: str = "") -> str:
    """Create a follow-up task for an account owner. This is a write
    action — call only after the user has approved the action."""
    acc = _find_account(account_name)
    if not acc:
        return f"No account found matching '{account_name}'. No task created."

    projects = _search_read("project.project", [["name", "=", "Customer Success"]], ["id"])
    project_id = projects[0]["id"] if projects else _execute(
        "project.project", "create", {"name": "Customer Success"})

    deadline = (date.today() + timedelta(days=due_in_days)).strftime("%Y-%m-%d")
    task_id = _execute("project.task", "create", {
        "name": f"{title} — {acc['name']}",
        "project_id": project_id,
        "partner_id": acc["id"],
        "date_deadline": deadline,
        "description": notes,
    })
    return f"Created task '{title}' for {acc['name']}, due {deadline} (task id {task_id})."


@mcp.tool()
def escalate_case(account_name: str, issue: str, priority: str = "Urgent") -> str:
    """Create an escalated case for an account in the Support Cases
    project. This is a write action — call only after the user has
    approved the escalation."""
    acc = _find_account(account_name)
    if not acc:
        return f"No account found matching '{account_name}'. No case created."

    projects = _search_read("project.project", [["name", "=", "Support Cases"]], ["id"])
    if not projects:
        return "Support Cases project not found — has Phase 1 data been seeded?"
    project_id = projects[0]["id"]

    stages = _search_read(
        "project.task.type",
        [["name", "=", "Escalated"], ["project_ids", "in", [project_id]]], ["id"])
    stage_id = stages[0]["id"] if stages else False

    tag_name = f"Priority: {priority}"
    tags = _search_read("project.tags", [["name", "=", tag_name]], ["id"])
    tag_id = tags[0]["id"] if tags else _execute("project.tags", "create", {"name": tag_name})

    case_id = _execute("project.task", "create", {
        "name": issue, "partner_id": acc["id"], "project_id": project_id,
        "stage_id": stage_id, "tag_ids": [(6, 0, [tag_id])],
    })
    return f"Escalated case '{issue}' for {acc['name']} (case id {case_id}, priority {priority})."


# ---------------------------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http")
    else:
        mcp.run()  # stdio — for local testing with MCP Inspector