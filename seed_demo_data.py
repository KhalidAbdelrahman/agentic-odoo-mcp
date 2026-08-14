"""
Meridian Fleet Technologies — Agentic CRM demo data seeder
============================================================

Fictional company premise: Meridian Fleet Technologies sells fleet
telematics, cold-chain monitoring, and supply-chain SaaS/hardware to
logistics, retail-distribution, and manufacturing customers. Every
account, product, opportunity, case, and task below is written to be
plausible *within that business*, and six "hero" accounts are
import os
import dotenv

  1. Stalled opportunity      -> Northbridge Freight Systems
  2. Risky customer           -> Cascade Cold Chain Inc.
  3. VIP escalation           -> Titan Retail Distribution
  4. Healthy / clean account  -> Harborline Manufacturing
  5. Meeting-prep subject     -> Summit Grocery Supply
  6. Slipping-deal subject    -> Ridgeline Auto Parts Distribution

Everything else (the remaining ~44 accounts, ~150 contacts, ~100
opportunities, ~200 activities, ~30 cases, ~100 tasks) is generated
programmatically from the same thematic word lists, so the bulk data
reads as part of the same fictional world instead of generic filler.

Note on Cases: Odoo's Helpdesk app is Enterprise-only and isn't
available on a self-hosted Community install. Cases are modeled
instead as project.task records in a dedicated "Support Cases"
project — priority via project.tags, status via task stages
(New / In Progress / Escalated / Resolved). This keeps the whole
stack on Community with full, unrestricted External API access.

Usage:
    pip install nothing — stdlib only.
    Edit the CONFIG block below, then:
        python3 seed_demo_data.py

Idempotency: this script does NOT check for existing records. Run it
once against a fresh database (see Step 10 snapshot/restore in the
setup guide) rather than re-running it against a populated one.
"""

import random
import xmlrpc.client
from datetime import date, timedelta
import os
import dotenv

# ---------------------------------------------------------------------------
# CONFIG — edit these for your instance
# ---------------------------------------------------------------------------
dotenv.load_dotenv()  # load .env values into os.environ

URL = os.getenv("ODOO_URL")  # e.g. "http://localhost:8000"
DB = os.getenv("ODOO_DB")  # e.g. "odoo_demo"
USERNAME = os.getenv("ODOO_USERNAME")
PASSWORD = os.getenv("ODOO_PASSWORD")

random.seed(42)  # reproducible dataset across runs

common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common")
uid = common.authenticate(DB, USERNAME, PASSWORD, {})
models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object")

def create(model, vals):
    return models.execute_kw(DB, uid, PASSWORD, model, "create", [vals])

def search_read(model, domain, fields, limit=None):
    kwargs = {"fields": fields}
    if limit:
        kwargs["limit"] = limit
    return models.execute_kw(DB, uid, PASSWORD, model, "search_read", [domain], kwargs)

def get_or_create_stage(name, sequence):
    found = search_read("crm.stage", [["name", "=", name]], ["id"])
    if found:
        return found[0]["id"]
    return create("crm.stage", {"name": name, "sequence": sequence})

def get_or_create_tag(model, name):
    found = search_read(model, [["name", "=", name]], ["id"])
    if found:
        return found[0]["id"]
    return create(model, {"name": name})

def get_or_create_project(name):
    found = search_read("project.project", [["name", "=", name]], ["id"])
    if found:
        return found[0]["id"]
    return create("project.project", {"name": name})

def get_or_create_case_stage(name, project_id, sequence):
    found = search_read("project.task.type", [["name", "=", name],
                                                ["project_ids", "in", [project_id]]], ["id"])
    if found:
        return found[0]["id"]
    return create("project.task.type", {
        "name": name, "sequence": sequence, "project_ids": [(6, 0, [project_id])],
    })

def get_or_create_case_priority_tag(name):
    return get_or_create_tag("project.tags", f"Priority: {name}")

def create_case(name, partner_id, priority, project_id, stage_ids, stage="New"):
    return create("project.task", {
        "name": name, "partner_id": partner_id, "project_id": project_id,
        "stage_id": stage_ids[stage],
        "tag_ids": [(6, 0, [get_or_create_case_priority_tag(priority)])],
    })

def get_model_id(model_name):
    found = search_read("ir.model", [["model", "=", model_name]], ["id"])
    if not found:
        raise RuntimeError(f"Could not resolve ir.model id for '{model_name}'")
    return found[0]["id"]

_model_id_cache = {}
def log_activity(res_model, res_id, summary, deadline, activity_type_id=1):
    if not res_id:
        raise ValueError(f"log_activity got an empty res_id for {res_model}: {res_id!r}")
    if res_model not in _model_id_cache:
        _model_id_cache[res_model] = get_model_id(res_model)
    return create("mail.activity", {
        "res_model": res_model,
        "res_model_id": _model_id_cache[res_model],
        "res_id": int(res_id),
        "activity_type_id": activity_type_id,
        "summary": summary,
        "date_deadline": deadline,
        "user_id": uid,
    })

def days_ago(n):
    return (date.today() - timedelta(days=n)).strftime("%Y-%m-%d %H:%M:%S")

def days_from_now(n):
    return (date.today() + timedelta(days=n)).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# PRODUCT CATALOG — 20 items, all plausible fleet/supply-chain offerings
# ---------------------------------------------------------------------------
PRODUCTS = [
    ("Fleet Telematics Pro", 4800, "Subscription — per-vehicle annual"),
    ("Route Optimization Suite", 3600, "Subscription — per-fleet annual"),
    ("Cold Chain Monitor", 2200, "Hardware sensor kit, per unit"),
    ("Driver Safety Analytics", 2900, "Subscription — per-driver annual"),
    ("Predictive Maintenance Add-on", 1800, "Add-on subscription"),
    ("Warehouse IoT Sensor Pack", 3100, "Hardware, per-site pack"),
    ("Compliance Reporting Module", 1500, "Add-on subscription"),
    ("Fuel Management Dashboard", 2000, "Add-on subscription"),
    ("Asset Tracking Tags (50-pack)", 1200, "Hardware"),
    ("Dispatch Automation Suite", 5200, "Subscription — per-fleet annual"),
    ("Driver Mobile App License", 900, "Subscription — per-driver annual"),
    ("Real-Time ETA API", 2600, "API subscription"),
    ("Carbon Emissions Tracker", 1700, "Add-on subscription"),
    ("Yard Management System", 4400, "Subscription — per-site annual"),
    ("24/7 Priority Support Plan", 3000, "Support plan, annual"),
    ("Standard Support Plan", 1200, "Support plan, annual"),
    ("Onboarding & Training Package", 2500, "One-time service"),
    ("Custom Integration Services", 6000, "One-time service"),
    ("Extended Data Retention (12mo)", 800, "Add-on subscription"),
    ("Multi-Site Rollout Package", 9500, "One-time service"),
]

# ---------------------------------------------------------------------------
# THEMATIC NAME POOLS — for the ~44 generated (non-hero) accounts
# ---------------------------------------------------------------------------
PREFIXES = ["Northstar", "Vantage", "Ironwood", "Bluepeak", "Redwood", "Fairwind",
            "Continental", "Lakeside", "Prairie", "Coastal", "Highland", "Silverline",
            "Brightpath", "Anchor", "Crestview", "Falcon", "Granite", "Meadowbrook",
            "Pinnacle", "Stonegate", "Timberline", "Westfield", "Amberlake", "Copperline"]
SUFFIXES = ["Freight", "Logistics", "Distribution", "Supply Co.", "Transport",
            "Cold Storage", "Warehousing", "Trucking", "Cargo Systems", "Fleet Services",
            "Retail Group", "Manufacturing", "Foods", "Auto Parts", "Grocery Supply",
            "Building Materials", "Beverage Distribution", "Parcel Services", "Industries"]
INDUSTRIES = ["Transportation & Logistics", "Retail Distribution", "Manufacturing",
              "Cold Chain / Food Distribution", "Wholesale Trade"]

FIRST_NAMES = ["Maria", "James", "Aisha", "Daniel", "Priya", "Marcus", "Elena", "Tom",
               "Fatima", "Chris", "Nina", "Robert", "Sofia", "Kevin", "Layla", "Brian",
               "Grace", "Omar", "Julia", "Sam"]
LAST_NAMES = ["Alvarez", "Chen", "Novak", "Bennett", "Kapoor", "Reyes", "Fischer", "Boone",
              "Hassan", "Larsen", "Petrov", "Okafor", "Sato", "Murphy", "Delgado", "Iversen"]
ROLES = ["Fleet Manager", "Operations Director", "Procurement Lead", "IT Manager",
         "VP Supply Chain", "Warehouse Supervisor", "Compliance Officer", "CFO",
         "Logistics Coordinator", "VP Operations"]

CASE_ISSUES = [
    ("Cold chain sensor offline - Zone {n}", "Urgent"),
    ("Telematics data not syncing to dashboard", "High"),
    ("Login access issue - new site rollout", "Medium"),
    ("Invoice discrepancy on renewal", "Medium"),
    ("Firmware update request for tracking tags", "Medium"),
    ("Route optimization not reflecting new depot", "High"),
    ("Driver app crashing on shift start", "High"),
    ("SLA breach - support ticket unresolved 5 days", "Urgent"),
]
# Cases are modeled as project.task records in a dedicated "Support Cases"
# project (Community-compatible substitute for the Enterprise-only Helpdesk
# app). Priority is a project.tags entry; status is the task's stage_id.

ACTIVITY_TYPES = ["Call", "Meeting", "Email", "To-Do"]
ACTIVITY_SUMMARIES = [
    "Quarterly check-in call", "Renewal pricing discussion", "Onboarding follow-up",
    "Escalation review with account lead", "Product roadmap walkthrough",
    "Contract redline review", "Site rollout planning call", "Support ticket follow-up",
]
TASK_TEMPLATES = [
    "Send renewal quote to {contact}",
    "Schedule onboarding call with {contact}",
    "Escalate open ticket to engineering",
    "Prepare QBR deck for {account}",
    "Follow up on unpaid invoice",
    "Coordinate hardware shipment for {account}",
    "Draft expansion proposal for {account}",
]

deal_names = ["New Deployment", "Renewal", "Expansion", "Upsell — Add-on Bundle",
              "Multi-Site Rollout", "Hardware Refresh"]


# ---------------------------------------------------------------------------
# SETUP: stages, tags, team, products
# ---------------------------------------------------------------------------
print("Setting up stages, tags, and product catalog...")
stage_new = get_or_create_stage("New", 1)
stage_qualified = get_or_create_stage("Qualified", 2)
stage_proposition = get_or_create_stage("Proposition", 3)
stage_won = get_or_create_stage("Won", 4)

vip_tag = get_or_create_tag("res.partner.category", "VIP Account")

cases_project = get_or_create_project("Support Cases")
case_stage_ids = {
    "New": get_or_create_case_stage("New", cases_project, 1),
    "In Progress": get_or_create_case_stage("In Progress", cases_project, 2),
    "Escalated": get_or_create_case_stage("Escalated", cases_project, 3),
    "Resolved": get_or_create_case_stage("Resolved", cases_project, 4),
}

product_ids = {}
for name, price, note in PRODUCTS:
    pid = create("product.template", {"name": name, "list_price": price, "sale_ok": True})
    product_ids[name] = pid
print(f"  {len(product_ids)} products created.")


# ---------------------------------------------------------------------------
# HERO ACCOUNTS — hand-crafted to hit each demo narrative exactly
# ---------------------------------------------------------------------------
hero_refs = {}

def make_contacts(account_id, account_name, n=3):
    ids = []
    used_roles = random.sample(ROLES, n)
    for role in used_roles:
        fn, ln = random.choice(FIRST_NAMES), random.choice(LAST_NAMES)
        cid = create("res.partner", {
            "name": f"{fn} {ln}",
            "is_company": False,
            "parent_id": account_id,
            "function": role,
            "email": f"{fn.lower()}.{ln.lower()}@{account_name.lower().replace(' ', '').replace('.', '')}.com",
        })
        ids.append((cid, f"{fn} {ln}"))
    return ids

print("\nCreating hero accounts (one per demo narrative)...")

# 1. STALLED OPPORTUNITY
acc = create("res.partner", {"name": "Northbridge Freight Systems", "is_company": True,
                              "industry_id": False})
contacts = make_contacts(acc, "Northbridge Freight Systems")
opp = create("crm.lead", {
    "name": "Northbridge Freight Systems — Fleet Telematics Pro Expansion",
    "partner_id": acc, "type": "opportunity", "stage_id": stage_proposition,
    "expected_revenue": 58000, "probability": 45,
    "date_deadline": days_from_now(-5),  # deadline already passed -> visibly stalled
})
# Last activity logged 65 days ago, nothing since — the "stall" signal
log_activity("crm.lead", opp, "Contract redline review", days_ago(65)[:10])
hero_refs["stalled_opportunity"] = {"account_id": acc, "opportunity_id": opp}
print(f"  Northbridge Freight Systems -> account {acc}, opportunity {opp} (stalled)")

# 2. RISKY CUSTOMER
acc = create("res.partner", {"name": "Cascade Cold Chain Inc.", "is_company": True})
contacts = make_contacts(acc, "Cascade Cold Chain Inc.")
opp = create("crm.lead", {
    "name": "Cascade Cold Chain Inc. — Cold Chain Monitor Renewal",
    "partner_id": acc, "type": "opportunity", "stage_id": stage_qualified,
    "expected_revenue": 85000, "probability": 55,
})
case_ids = []
for issue, priority in [("Cold chain sensor offline - Zone 3", "Urgent"),
                         ("SLA breach - support ticket unresolved 5 days", "Urgent")]:
    cid = create_case(issue, acc, priority, cases_project, case_stage_ids, stage="New")
    case_ids.append(cid)
hero_refs["risky_customer"] = {"account_id": acc, "opportunity_id": opp, "case_ids": case_ids}
print(f"  Cascade Cold Chain Inc. -> account {acc}, opportunity {opp}, {len(case_ids)} open high-priority cases")

# 3. VIP ESCALATION
acc = create("res.partner", {"name": "Titan Retail Distribution", "is_company": True,
                              "category_id": [(6, 0, [vip_tag])]})
contacts = make_contacts(acc, "Titan Retail Distribution")
case = create_case("Warehouse system outage during peak season", acc, "Urgent",
                    cases_project, case_stage_ids, stage="Escalated")
hero_refs["vip_escalation"] = {"account_id": acc, "case_id": case}
print(f"  Titan Retail Distribution -> account {acc} (VIP-tagged), urgent case {case}")

# 4. HEALTHY / CLEAN ACCOUNT (balances the executive summary)
acc = create("res.partner", {"name": "Harborline Manufacturing", "is_company": True})
contacts = make_contacts(acc, "Harborline Manufacturing")
opp = create("crm.lead", {
    "name": "Harborline Manufacturing — Yard Management System",
    "partner_id": acc, "type": "opportunity", "stage_id": stage_won,
    "expected_revenue": 44000, "probability": 100,
})
log_activity("res.partner", acc, "Quarterly check-in call", days_ago(3)[:10])
hero_refs["healthy_account"] = {"account_id": acc, "opportunity_id": opp}
print(f"  Harborline Manufacturing -> account {acc}, closed-won opportunity {opp}")

# 5. MEETING-PREP SUBJECT
acc = create("res.partner", {"name": "Summit Grocery Supply", "is_company": True})
contacts = make_contacts(acc, "Summit Grocery Supply", n=4)
opp = create("crm.lead", {
    "name": "Summit Grocery Supply — Multi-Site Rollout Package",
    "partner_id": acc, "type": "opportunity", "stage_id": stage_proposition,
    "expected_revenue": 96000, "probability": 60,
})
case = create_case("Firmware update request for tracking tags", acc, "Medium",
                    cases_project, case_stage_ids, stage="In Progress")
hero_refs["meeting_prep"] = {"account_id": acc, "opportunity_id": opp, "case_id": case,
                             "contacts": contacts}
print(f"  Summit Grocery Supply -> account {acc}, opportunity {opp}, {len(contacts)} contacts")

# 6. SLIPPING-DEAL SUBJECT (for the Sales Pipeline Agent scenario)
acc = create("res.partner", {"name": "Ridgeline Auto Parts Distribution", "is_company": True})
contacts = make_contacts(acc, "Ridgeline Auto Parts Distribution")
opp_slip = create("crm.lead", {
    "name": "Ridgeline Auto Parts Distribution — Driver Safety Analytics",
    "partner_id": acc, "type": "opportunity", "stage_id": stage_qualified,
    "expected_revenue": 31000, "probability": 30,
    "date_deadline": days_from_now(-10),
})
opp_healthy = create("crm.lead", {
    "name": "Ridgeline Auto Parts Distribution — Standard Support Plan",
    "partner_id": acc, "type": "opportunity", "stage_id": stage_proposition,
    "expected_revenue": 8000, "probability": 70,
})
hero_refs["slipping_deal"] = {"account_id": acc, "slipping_opportunity_id": opp_slip,
                              "on_track_opportunity_id": opp_healthy}
print(f"  Ridgeline Auto Parts Distribution -> account {acc}, slipping opp {opp_slip}")


# ---------------------------------------------------------------------------
# BULK GENERATION — remaining accounts/contacts/opportunities/activities/
# cases/tasks, same thematic pools, target volumes from the demo plan
# ---------------------------------------------------------------------------
print("\nGenerating remaining accounts and related records...")

used_names = set()
def unique_company_name():
    while True:
        name = f"{random.choice(PREFIXES)} {random.choice(SUFFIXES)}"
        if name not in used_names:
            used_names.add(name)
            return name

TARGET_ACCOUNTS = 44          # + 6 hero = 50
TARGET_OPPS = 94              # + 6 hero = 100
TARGET_CASES = 28             # + 3 hero = ~31 (close enough to plan's ~30)
TARGET_ACTIVITIES = 198       # + 2 hero = 200
TARGET_TASKS = 100
CONTACTS_PER_ACCOUNT = 3      # ~50 * 3 = 150

all_account_ids = []
all_contact_names = []  # (contact_id, name, account_id, account_name)

for i in range(TARGET_ACCOUNTS):
    name = unique_company_name()
    acc_id = create("res.partner", {
        "name": name, "is_company": True,
        "industry_id": False,
    })
    all_account_ids.append((acc_id, name))
    for cid, cname in make_contacts(acc_id, name, n=CONTACTS_PER_ACCOUNT):
        all_contact_names.append((cid, cname, acc_id, name))

print(f"  {len(all_account_ids)} additional accounts, {len(all_contact_names)} contacts created.")

# Opportunities — spread across stages, tied to real products in the name
stages_pool = [stage_new, stage_qualified, stage_proposition, stage_won]
opp_ids = []
for i in range(TARGET_OPPS):
    acc_id, acc_name = random.choice(all_account_ids)
    product_name = random.choice(list(product_ids.keys()))
    deal = random.choice(deal_names)
    stage = random.choices(stages_pool, weights=[3, 3, 2, 2])[0]
    revenue = random.randint(4000, 60000)
    probability = 100 if stage == stage_won else random.choice([20, 30, 40, 50, 60, 70, 90])
    oid = create("crm.lead", {
        "name": f"{acc_name} — {product_name} {deal}",
        "partner_id": acc_id, "type": "opportunity", "stage_id": stage,
        "expected_revenue": revenue,
        "probability": probability,
    })
    opp_ids.append(oid)
print(f"  {len(opp_ids)} additional opportunities created.")

# Activities — mostly tied to accounts, some to opportunities, recent dates
for i in range(TARGET_ACTIVITIES):
    if random.random() < 0.5 and opp_ids:
        res_model, res_id = "crm.lead", random.choice(opp_ids)
    else:
        res_model, res_id = "res.partner", random.choice(all_account_ids)[0]
    log_activity(res_model, res_id, random.choice(ACTIVITY_SUMMARIES),
                 days_ago(random.randint(0, 45))[:10])
print(f"  {TARGET_ACTIVITIES} additional activities created.")

# Cases — weighted toward New/In Progress, occasional Resolved; priority
# skews low/medium with occasional high/urgent, same as before
stage_weights = {"New": 4, "In Progress": 3, "Escalated": 1, "Resolved": 2}
for i in range(TARGET_CASES):
    acc_id, acc_name = random.choice(all_account_ids)
    issue, priority = random.choice(CASE_ISSUES)
    issue = issue.format(n=random.randint(1, 6))
    stage_choice = random.choices(list(stage_weights.keys()),
                                   weights=list(stage_weights.values()))[0]
    create_case(issue, acc_id, priority, cases_project, case_stage_ids, stage=stage_choice)
print(f"  {TARGET_CASES} additional cases created.")

# Tasks — reference real contact/account names so they read as genuine work items
project_ids = search_read("project.project", [], ["id"], limit=1)
if project_ids:
    project_id = project_ids[0]["id"]
else:
    project_id = create("project.project", {"name": "Customer Success"})

for i in range(TARGET_TASKS):
    template = random.choice(TASK_TEMPLATES)
    if "{contact}" in template and all_contact_names:
        _, cname, _, acc_name = random.choice(all_contact_names)
        title = template.format(contact=cname)
    elif "{account}" in template:
        _, acc_name = random.choice(all_account_ids)
        title = template.format(account=acc_name)
    else:
        title = template
    create("project.task", {
        "name": title, "project_id": project_id,
        "date_deadline": days_from_now(random.randint(1, 21)),
    })
print(f"  {TARGET_TASKS} tasks created.")


# ---------------------------------------------------------------------------
# SAVE HERO REFERENCE — so you can jump straight to each narrative live
# ---------------------------------------------------------------------------
import json
with open("hero_reference.json", "w") as f:
    json.dump(hero_refs, f, indent=2)

print("\nDone. Hero record IDs saved to hero_reference.json — use these to")
print("jump straight to each demo narrative during a live walkthrough")
print("instead of hunting through the generated bulk data.")