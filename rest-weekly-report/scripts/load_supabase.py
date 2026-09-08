#!/usr/bin/env python3
"""Generate the Supabase OVERWRITE SQL for the Rest dashboard.

Usage: python load_supabase.py <monthly.txt> <daily.txt> <ASOF YYYY-MM-DD> <outdir> <rest_hotels.json>

Writes ONE file into <outdir>:
  rest_load_00.sql  -> delete from rest_monthly, then insert the full monthly series

Run it through the Supabase MCP `execute_sql` (project gfsusmsstpjqwrvcxjzt). Because RLS
restricts writes to internal admins, run it via the MCP/service connection, not the browser.

Design notes:
  * ONE statement pair in ONE file, so the whole overwrite lands in a single implicit
    transaction. Readers never see a half-loaded or empty table - this is what makes an
    unattended nightly refresh safe.
  * There is NO history. Each run replaces the full current series; the dashboard is a
    monthly view and one hotel-month is one row, so daily runs do not accumulate anything.
  * There is NO rest_daily table any more (retired in migration 124). The dashboard's date
    range is whole calendar months only, and monthly ties to the old daily rows exactly.
    daily.txt is still READ, because monthly billable/charged/net are derived from it and
    its TB/TC totals are the reconciliation check against the rest. Metrics endpoint.
  * rest_cost comes from monthly.txt (the metrics endpoint).
  * Hotel attributes arrive as a JSON export the caller builds by joining public.rest_hotels
    (rest_name / go_live / model - the Rest-specific facts) to public.dim_hotel (num_keys /
    management_company - the shared ones). Keys and management company are deliberately NOT
    duplicated in rest_hotels; the local copy had already drifted from dim_hotel once.
  * Hotel attributes + the as-of date are denormalized onto every row (no dim/meta join).
"""
import sys
import json
import os
from collections import defaultdict

if len(sys.argv) != 6:
    sys.exit(__doc__)
monthly_path, daily_path, asof, outdir, hotels_path = sys.argv[1:6]

# ---- hotel reference, exported from public.rest_hotels ----
raw = json.load(open(hotels_path, encoding="utf-8"))
if isinstance(raw, dict):  # tolerate {"rows": [...]} or a name-keyed object
    raw = raw.get("rows", raw.get("data", list(raw.values())))
ref = {}
unresolved = []
for r in raw:
    # A null here means the hotel did not resolve in dim_hotel. Loading it would give a hotel
    # with no room-night denominator, quietly corrupting Incident Rate and RevPAR - so refuse.
    if r.get("num_keys") in (None, "") or not str(r.get("mgmt_company") or "").strip():
        unresolved.append(r.get("rest_name") or r.get("hotel_id"))
        continue
    ref[r["rest_name"]] = {
        "hotel_id": int(r["hotel_id"]),
        "keys": int(r["num_keys"]),
        "golive": str(r["go_live"])[:10],
        "mgmt": r.get("mgmt_company") or "",
        "model": r.get("model") or None,
    }
if unresolved:
    sys.exit("ERROR: %d hotel(s) did not resolve in dim_hotel (null keys or management company):\n"
             "  %s\nFix them in the Master Hotel List, re-export, and re-run. Refusing to load."
             % (len(unresolved), "\n  ".join(str(u) for u in unresolved)))
if not ref:
    sys.exit("ERROR: no hotels in %s - export public.rest_hotels first." % hotels_path)


def esc(s):
    return str(s).replace("'", "''")


def attrs(nm):
    r = ref[nm]
    md = r["model"]
    return (r["hotel_id"], esc(nm), r["keys"], r["golive"], esc(r["mgmt"]),
            ("'%s'" % esc(md)) if md else "NULL")


seen_names = set()
skipped = set()

# ---- rest_cost per (name, ym) from monthly.txt ----
restc = {}
for ln in open(monthly_path, encoding="utf-8"):
    ln = ln.rstrip("\n")
    if not ln or "|" not in ln:
        continue
    parts = ln.split("|")
    nm = parts[0]
    seen_names.add(nm)
    if nm not in ref:
        skipped.add(nm)
        continue
    for seg in parts[1:]:
        if not seg:
            continue
        ym, vals = seg.split(":")
        b, c, net, rest = vals.split(",")
        restc[(nm, ym)] = float(rest)

# ---- monthly aggregation derived from the daily pull ----
magg = defaultdict(lambda: [0, 0, 0.0])
monthset = set()
tb = tc = 0
for ln in open(daily_path, encoding="utf-8"):
    ln = ln.rstrip("\n")
    if not ln or "|" not in ln:
        continue
    parts = ln.split("|")
    nm = parts[0]
    seen_names.add(nm)
    if nm not in ref:
        skipped.add(nm)
        continue
    for seg in parts[1:]:
        if not seg:
            continue
        d, vals = seg.split(":")
        b, c, net = vals.split(",")
        b, c, net = int(b), int(c), float(net)
        tb += b
        tc += c
        ym = d[:7]
        monthset.add((nm, ym))
        a = magg[(nm, ym)]
        a[0] += b
        a[1] += c
        a[2] += net

for key in restc:  # keep cost-only months (hotel live, zero events)
    monthset.add(key)

COLS_M = ("(hotel_id,month,billable,charged,net_charges,rest_cost,rest_name,"
          "num_keys,go_live,mgmt_company,model,as_of,refreshed_at)")

mvals = []
for (nm, ym) in sorted(monthset, key=lambda x: (ref[x[0]]["hotel_id"], x[1])):
    hid, name, keys, gl, mg, md = attrs(nm)
    b, c, net = magg.get((nm, ym), [0, 0, 0.0])
    rest = restc.get((nm, ym), 0.0)
    if not (b or c or net or rest):
        continue
    mvals.append("(%d,'%s-01',%d,%d,%s,%s,'%s',%d,'%s','%s',%s,'%s',now())"
                 % (hid, ym, b, c, round(net, 2), round(rest, 2), name, keys, gl, mg, md, asof))

if not mvals:
    sys.exit("ERROR: no monthly rows generated - refusing to write a DELETE with no INSERT.")

os.makedirs(outdir, exist_ok=True)
out = os.path.join(outdir, "rest_load_00.sql")
with open(out, "w", encoding="utf-8", newline="") as f:
    f.write("-- Full overwrite of public.rest_monthly, as of %s.\n" % asof)
    f.write("-- Single file on purpose: one execute_sql call = one transaction, so readers\n")
    f.write("-- never see an empty or half-loaded table.\n")
    f.write("delete from public.rest_monthly;\n")
    f.write("insert into public.rest_monthly " + COLS_M + " values\n")
    f.write(",\n".join(mvals) + ";\n")

print("wrote %s | monthly %d rows | TB=%d TC=%d (must match the Metrics endpoint)"
      % (out, len(mvals), tb, tc))
print("hotels in reference: %d | hotels seen in pull: %d" % (len(ref), len(seen_names)))
if skipped:
    print("\n*** %d HOTEL(S) SKIPPED - NOT IN public.rest_hotels ***" % len(skipped))
    for nm in sorted(skipped):
        print("    - %s" % nm)
    print("    These are MISSING from the dashboard. Add them to public.rest_hotels")
    print("    (hotel_id, rest_name, go_live, model) - keys and mgmt come from dim_hotel -")
    print("    then re-export and re-run.")
    print("    Do NOT report this run as a clean success.")
else:
    print("no skipped hotels - every hotel in the pull is configured")
