#!/usr/bin/env python3
"""Regenerate the local reference caches from public.rest_hotels.

Usage: python sync_reference.py <rest_hotels.json> [reference_dir]

public.rest_hotels in Supabase is the SINGLE SOURCE OF TRUTH for hotel attributes.
reference/keys_golive.json and reference/model_lists.json are now derived caches, kept
only because build_xlsx.py and the weekly narrative still read them. Run this at the start
of every run, after exporting rest_hotels, so the two can never drift.

Never hand-edit the reference files - the next run overwrites them. To change a hotel,
update public.rest_hotels.
"""
import sys
import json
import os

if len(sys.argv) not in (2, 3):
    sys.exit(__doc__)
hotels_path = sys.argv[1]
ref_dir = sys.argv[2] if len(sys.argv) == 3 else os.path.join(os.path.dirname(__file__), "..", "reference")

raw = json.load(open(hotels_path, encoding="utf-8"))
if isinstance(raw, dict):
    raw = raw.get("rows", raw.get("data", list(raw.values())))
if not raw:
    sys.exit("ERROR: no hotels in %s - refusing to overwrite the caches with nothing." % hotels_path)

kg, capex, financed = {}, [], []
for r in sorted(raw, key=lambda x: x["rest_name"]):
    name = r["rest_name"]
    kg[name] = {
        "hotel_id": int(r["hotel_id"]),
        "keys": int(r["num_keys"]),
        "golive": str(r["go_live"])[:10],
        "mgmt": r.get("mgmt_company") or "",
    }
    md = (r.get("model") or "").strip()
    if md == "Capex":
        capex.append(name)
    elif md == "Financed":
        financed.append(name)

os.makedirs(ref_dir, exist_ok=True)
with open(os.path.join(ref_dir, "keys_golive.json"), "w", encoding="utf-8", newline="") as f:
    json.dump(kg, f, indent=2)
    f.write("\n")
with open(os.path.join(ref_dir, "model_lists.json"), "w", encoding="utf-8", newline="") as f:
    json.dump({"capex": capex, "financed": financed}, f, indent=2)
    f.write("\n")

no_model = [n for n in kg if n not in capex and n not in financed]
print("synced %d hotels from rest_hotels -> keys_golive.json (%d Capex / %d Financed)"
      % (len(kg), len(capex), len(financed)))
if no_model:
    print("WARNING: %d hotel(s) have no Capex/Financed model set in rest_hotels:" % len(no_model))
    for n in no_model:
        print("    - %s" % n)
