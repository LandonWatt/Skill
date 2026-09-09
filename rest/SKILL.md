---
name: rest
description: >
  Rest (NoiseAware) smoking-sensor reporting for Noble Investment Group's Asset Management Team.
  Refreshes the hosted extranet dashboard's data in Supabase and/or builds the weekly "Rest Results"
  Word document (email body: greeting, Chosen model Capex/Financed lists, per-property charged
  summary with exceptions, Best Practices, Portfolio Statistics, embedded table picture, and Landon
  Watts' signature). Pulls live data from the rest. dashboard through the user's logged-in Chrome
  session. Trigger on "/rest" (refresh AND document), "/rest A" (refresh only), "/rest B" (document
  only), or when the user asks to "run the rest report", "weekly rest email", "smoking sensor
  update", "refresh the rest data", "refresh the rest dashboard", "update the rest site", or names a
  report date like "rest as of 7/6".
---

# Rest

Data always comes live from the rest. dashboard through the user's logged-in Chrome session.

## Read the argument FIRST

The invocation decides what runs. Settle this BEFORE doing anything else.

| Invoked as | Runs | Result |
|---|---|---|
| **`/rest`** (no argument) | Mode A, **then** Mode B | Dashboard refreshed **and** `Rest<M-D>.docx` |
| **`/rest A`** | Mode A only | Dashboard refreshed. **No documents, no prompts.** |
| **`/rest B`** | Mode B only | `Rest<M-D>.docx` only. **Supabase untouched.** |

Read the argument case-insensitively - `a`, `A`, `mode a` all mean Mode A. If the user asked in
words instead of with a flag, work out which they meant and say which you picked before starting.
When it is genuinely ambiguous, do the full `/rest`. There is **no scheduled run**; this skill is
always invoked by hand.

### The two modes

| | **Mode A - data refresh** | **Mode B - weekly report** |
|---|---|---|
| Purpose | Keep the hosted extranet dashboard current | Produce the paste-ready email |
| Steps to run | Step 1, health check, then **Step 6b only** | Step 1, health check, Steps 2-6, Step 7 |
| Touches Supabase | **Yes** (overwrites `rest_monthly`) | **No** |
| Produces files | **None** | **`Rest<M-D>.docx` only** |
| Prompts the user | **No** (see Mode A rules) | Yes (see the input list below) |

**Neither mode invokes the other.** A bare `/rest` runs both because the caller asked for both, in
the order Mode A then Mode B - refresh first, so a broken session fails before any document work is
wasted, and so the dashboard still ends up current even if the document build later goes wrong.

**`/rest B` deliberately does not refresh Supabase.** If it did, it would be identical to a bare
`/rest`. Say in the closing message how stale the dashboard is, so an outstanding refresh is never
a surprise.

**Mode B produces the Word document only** - `Email.xlsx` is still built, but purely as an
intermediate needed to render the table picture embedded in the Word doc. Do not present it.

### Mode A rules
1. **Dates:** as-of = **today**, BEFORE = **tomorrow**. The dashboard is a MONTHLY view: it caps
   each month's room-night denominator at the as-of date, so an in-progress month is measured only
   against the days elapsed so far. Completed months are always exact, and a daily run simply
   recomputes the current month's row - it never adds history or a new period.
   **The later in the day it runs, the truer the current month reads.** Today counts as a full day
   in the denominator whatever time the run happens, so a morning run measures a nearly eventless
   day against a whole day of room nights and understates the CURRENT month's incident rate - badly
   in the first days of a month (roughly a third on the 3rd, ~8% by the 10th, ~3% by month end). It
   never affects any completed month, so a morning run is fine; just do not read the current
   month's rate as final.
2. **Never prompt.** Hotel attributes come from `public.rest_hotels` in Supabase; use them as-is.
3. **Report skipped hotels loudly.** Any hotel rest. returns that is missing from
   `public.rest_hotels` is skipped by the loader, which would quietly drop it from the dashboard.
   `load_supabase.py` prints a `*** HOTEL(S) SKIPPED ***` block naming them. Repeat that list in
   your closing message and do NOT call the run a clean success.
4. **If auth fails, stop and report.** Do not partially load. A failed token means no refresh
   happened; say so rather than reporting success.

### Order of operations for a bare `/rest`

1. **Step 1** - connect and verify auth.
2. **Health check** (below) - report what it surfaces before asking for anything.
3. **Step 6b** - the Mode A refresh.
4. **Steps 2-6** - the report pulls, the Excel intermediate, the table picture, the Word doc.
5. **Step 7** - deliver the Word doc and report the refresh result.

`/rest A` stops after step 3. `/rest B` skips step 3.

**Mode A always uses as-of = TODAY, regardless of the report date the user gave.** This matters:
someone running a back-dated report ("rest as of 9/6") must not rewind the live dashboard to an
older as-of and throw away newer data. The report and the dashboard are allowed to sit on different
dates. If the report's as-of is not today, say so plainly in the closing message so nobody reads
the difference as a bug.

### Every run opens with a HEALTH CHECK (before prompting for anything)
Nothing runs on a schedule any more, so this is the only moment problems surface - do not skip it,
in either mode. Run these three through the Supabase MCP and report what they surface, in plain
language, BEFORE asking for any report inputs.

```sql
-- 1. Is the dashboard current? (how long since the last refresh?)
select max(as_of)::text as data_as_of, (current_date - max(as_of)) as days_old,
       count(*) as rows, sum(billable) as billable, sum(charged) as charged,
       round(sum(net_charges)::numeric,2) as collected
from public.rest_monthly;

-- 2. Hotels the next load will refuse or silently skip
select r.rest_name,
       case when d.hotel_id is null           then 'no dim_hotel match'
            when d.num_keys is null           then 'dim_hotel has no key count'
            when d.management_company is null then 'dim_hotel has no management company'
            when r.model is null              then 'Capex/Financed not set'
       end as problem
from public.rest_hotels r
left join public.dim_hotel d on d.hotel_id = r.hotel_id
where d.hotel_id is null or d.num_keys is null
   or d.management_company is null or r.model is null;

-- 3. Attribute edits that have NOT reached the dashboard yet
select m.rest_name, m.model as showing_model, r.model as should_be_model,
       m.mgmt_company as showing_mgmt, d.management_company as should_be_mgmt,
       m.asset_manager as showing_am, d.asset_manager as should_be_am,
       m.num_keys as showing_keys, d.num_keys as should_be_keys
from (select distinct hotel_id, rest_name, num_keys, go_live, mgmt_company, asset_manager, model
        from public.rest_monthly) m
join public.rest_hotels r on r.hotel_id = m.hotel_id
join public.dim_hotel  d on d.hotel_id = m.hotel_id
where m.model is distinct from r.model
   or m.mgmt_company is distinct from d.management_company
   or m.asset_manager is distinct from d.asset_manager
   or m.num_keys is distinct from d.num_keys
   or m.rest_name is distinct from r.rest_name;
```

Say plainly: how old the data is (call it out above 2 days - it means nobody has run `/rest` or
`/rest A` lately), every hotel from query 2, and every row from query 3. After the pull, also name
any hotel rest. returned that is missing from `public.rest_hotels`. Do not bury these at the end.

### Changing a model, or adding a hotel
`public.rest_hotels` is the source of truth, but the dashboard reads hotel attributes
**denormalised onto `rest_monthly`**. Editing `rest_hotels` alone does NOT change the page -
the change only appears when a Mode A refresh rewrites those rows. After ANY attribute edit,
push it through immediately with this (attribute columns only, never the measures):

```sql
update public.rest_monthly m
set rest_name=r.rest_name, num_keys=d.num_keys, go_live=r.go_live,
    mgmt_company=d.management_company, asset_manager=d.asset_manager, model=r.model
from public.rest_hotels r
join public.dim_hotel d on d.hotel_id = r.hotel_id
where m.hotel_id = r.hotel_id
  and (m.rest_name is distinct from r.rest_name
    or m.num_keys is distinct from d.num_keys
    or m.go_live is distinct from r.go_live
    or m.mgmt_company is distinct from d.management_company
    or m.asset_manager is distinct from d.asset_manager
    or m.model is distinct from r.model);
```

A brand-new hotel has no `rest_monthly` rows yet, so adding it to `rest_hotels` makes it appear
only after the next Mode A refresh. Say so rather than implying it is already on the dashboard.

## Prompt the user for these inputs first (Mode B only - Mode A never prompts)
1. **As-of date** (report date). Default = today.
2. **Look-back window ("since" date)** for the per-property narrative. Ask each run (typically the prior report date, so this week picks up where the last left off).
3. **Capex / Financed lists** — these live in `public.rest_hotels.model` in Supabase. Show the user the current lists and ask only: "Any changes to the Capex or Financed lists?" If the user names additions/removals/moves, apply them with an `update public.rest_hotels set model=... where rest_name=...` through the Supabase MCP, then re-run `sync_reference.py`. If no changes, use them as-is.
4. **New hotels?** If rest. now returns a hotel not in `public.rest_hotels`, ask the user for its **key count**, **go-live date** and **Capex/Financed**, look up its `hotel_id` in `public.dim_hotel` (match on name; rest.'s names differ from dim_hotel's, so confirm the match with the user if it is not obvious), `insert` the row into `public.rest_hotels`, and re-run `sync_reference.py` before building.

## Prerequisites
- Chrome connected (Claude in Chrome) and the user **logged into** https://app.resteasy.noiseaware.com.
- Sandbox has `openpyxl` (pip install --break-system-packages) and node `docx` (npm i docx), plus LibreOffice + poppler for rendering.
- Optional: a connected output folder, so files land where the user wants.

## Step 1 — Connect & verify auth
Open a tab to https://app.resteasy.noiseaware.com/properties/ , wait ~6s, then verify the token:
```js
const t=localStorage.getItem('auth_token'); const tok=JSON.parse(t);
const H={Authorization:'Bearer '+tok.access,'X-Org':String(tok.organization)};
const r=await fetch('https://api.resteasy.noiseaware.com/client/properties/?pageSize=2&ordering=name',{headers:H});
JSON.stringify({status:r.status, today:new Date().toISOString().slice(0,10)});
```
If status !=200, reload the page (the app refreshes the token) and retry.

## Step 2 — Pull SINCE-GO-LIVE data (for Excel). Set BEFORE = as-of date.
Run in the browser (javascript_tool), dump via a `<pre>` and read with get_page_text (avoids output truncation). Fields per property: billable, charged (=billable events with netCharge>0), gross (sum chargeAmount), net (sum netChargeAmount), rest_cost (metrics), reasons (adjustmentReason counts).
```js
const tok=JSON.parse(localStorage.getItem('auth_token'));const H={Authorization:'Bearer '+tok.access,'X-Org':String(tok.organization)};const HJ={...H,'Content-Type':'application/json'};
let props=[],pg=1;while(true){const j=await(await fetch('https://api.resteasy.noiseaware.com/client/properties/?pageSize=200&page='+pg+'&ordering=name',{headers:H})).json();(j.results||[]).forEach(p=>props.push({id:p.id,name:p.name}));if(j.next)pg++;else break;}
const BEFORE='<ASOF>';const out=[];
for(const p of props){let page=1,all=[];while(true){const u='https://api.resteasy.noiseaware.com/client/events/?eventClass=SMOKE&includeInternalEvents=false&localCreatedOnDateAfter=2026-01-01&localCreatedOnDateBefore='+BEFORE+'&ordering=-createdOn&pageSize=300&page='+page+'&property='+p.id;const j=await(await fetch(u,{headers:H})).json();(j.results||[]).forEach(e=>all.push(e));if(j.next)page++;else break;}
let bil=0,chg=0,gross=0,net=0;const R={};for(const e of all){const fb=e.smokeFeedback||{};const nc=parseFloat(fb.netChargeAmount||0)||0;gross+=parseFloat(fb.chargeAmount||0)||0;net+=nc;if(e.billable){bil++;if(nc>0)chg++;}const rs=(fb.adjustmentReason||'').trim();if(rs)R[rs]=(R[rs]||0)+1;}
const body={items:[{start:'2026-02-01',end:BEFORE,intervalType:'days',interval:230,metrics:['rest_costs'],grouping:'property',summarize:true,properties:[p.id]}]};let rcst=0;try{const mj=await(await fetch('https://api.resteasy.noiseaware.com/client/reports/chart/',{method:'POST',headers:HJ,body:JSON.stringify(body)})).json();const g=(mj.items&&mj.items[0]&&mj.items[0].graphs)||[];const gr=g.find(x=>x.key==='rest_costs');if(gr)rcst=gr.data.reduce((s,d)=>s+(d.rawValue||0),0);}catch(e){}
out.push(p.name+'|'+bil+'|'+chg+'|'+(+gross.toFixed(2))+'|'+(+net.toFixed(2))+'|'+(+rcst.toFixed(2))+'|'+Object.entries(R).map(x=>x[0]+':'+x[1]).join(','));}
document.body.replaceChildren();const pre=document.createElement('pre');pre.textContent='@@SGL@@\n'+out.join('\n')+'\n@@E@@';document.body.appendChild(pre);'ok';
```
**Sanity check:** if any hotel's rest_cost is 0 (or wildly different from last week), the metrics endpoint may have glitched — re-pull that property once and flag it to the user; don't silently use 0.

## Step 3 — Pull WINDOWED data (for the narrative). AFTER = since date, BEFORE = as-of date.
Same dump technique; capture every billable event with date, net, charge, reason, comment.
```js
const tok=JSON.parse(localStorage.getItem('auth_token'));const H={Authorization:'Bearer '+tok.access,'X-Org':String(tok.organization)};
let props=[],pg=1;while(true){const j=await(await fetch('https://api.resteasy.noiseaware.com/client/properties/?pageSize=200&page='+pg+'&ordering=name',{headers:H})).json();(j.results||[]).forEach(p=>props.push({id:p.id,name:p.name}));if(j.next)pg++;else break;}
const AFTER='<SINCE>',BEFORE='<ASOF>';const out=[];
for(const p of props){let page=1,all=[];while(true){const u='https://api.resteasy.noiseaware.com/client/events/?eventClass=SMOKE&includeInternalEvents=false&localCreatedOnDateAfter='+AFTER+'&localCreatedOnDateBefore='+BEFORE+'&ordering=-createdOn&pageSize=300&page='+page+'&property='+p.id;const j=await(await fetch(u,{headers:H})).json();(j.results||[]).forEach(e=>all.push(e));if(j.next)page++;else break;}
let Y=0,X=0;const rows=[];for(const e of all){const fb=e.smokeFeedback||{};const net=parseFloat(fb.netChargeAmount||0)||0;const ca=parseFloat(fb.chargeAmount||0)||0;const rs=(fb.adjustmentReason||'').trim();if(e.billable){Y++;if(net>0)X++;rows.push('EV|'+e.createdOn.slice(0,10)+'|'+net+'|'+ca+'|'+rs+'|'+(fb.comments||'').replace(/\n/g,' ').replace(/\|/g,'/').slice(0,160));}}
out.push('PROP|'+p.name+'|'+X+'|'+Y);rows.forEach(r=>out.push(r));}
document.body.replaceChildren();const pre=document.createElement('pre');pre.textContent='@@W@@\n'+out.join('\n')+'\n@@E@@';document.body.appendChild(pre);'ok';
```

## Step 4 — Assemble data.json
Write `data.json` in the working dir:
```
{
  "asof":"YYYY-MM-DD", "since":"YYYY-MM-DD", "greeting":"Good afternoon,",
  "chargeRate":"69.9", "incRate":"0.44",
  "capex":[...names...], "financed":[...names...],
  "sgl":[ {"name","billable","charged","gross","net","rest","reasons":{CODE:n}} ... alphabetical ],
  "windowed":[ {"name","X","Y","events":[[date,net,charge,reason,comment],...]} ... alphabetical ]
}
```
- **chargeRate** = round( sum(charged)/sum(billable) * 100 , 1).
- **incRate** = round( sum(billable) / sum(keys*days_since_golive as of ASOF) * 100 , 2), using reference/keys_golive.json and days = (ASOF - golive) + 1.
- Keep property order alphabetical (matches the pull order).

## Step 5 — Build Excel + render the table picture
```
python3 scripts/build_xlsx.py data.json Email.xlsx
python3 scripts/render_table.py Email.xlsx <ASOF-YYYY-MM-DD> table.png
```
`render_table.py` is self-contained: it freezes Days-Since-Go-Live to the report date
(the picture is a point-in-time snapshot), fills in static values (no LibreOffice recalc
needed), aliases "Aptos Narrow" to an installed narrow font so the size-16 Total row never
overflows to `###`, renders one landscape page, and autocrops to `table.png`.
Do NOT hand-render with soffice/pdftoppm — always use render_table.py.
Note: `Email.xlsx` itself keeps its live `=TODAY()-GoLive+1` day formulas and all other
formulas intact — only the rendered picture is frozen to the report date.

## Step 6 — Build the Word doc
```
node scripts/gen_doc.js data.json table.png "Rest<M-D>.docx"
```
Validate with the docx skill's validate.py.

## Step 6b — Refresh the live dashboard data (Supabase)  <== THIS IS MODE A
The dashboard is a hosted page on the Noble extranet (`dashboard.html`) that reads its data live from Supabase; each run OVERWRITES that data. Two extra browser pulls feed it (Monthly Indicators heatmap, Trends charts, Portfolio Dashboard financials). Both dump to a `<pre>` read via get_page_text (like Steps 2–3). Set BEFORE = day AFTER the as-of date (exclusive), e.g. as-of 2026-08-31 → `2026-09-01`.

**Pull A — monthly billable/charged/net/rest per hotel** (rest cost via cumulative month-ends, diffed):
```js
const tok=JSON.parse(localStorage.getItem('auth_token'));const H={Authorization:'Bearer '+tok.access,'X-Org':String(tok.organization)};const HJ={...H,'Content-Type':'application/json'};
let props=[],pg=1;while(true){const j=await(await fetch('https://api.resteasy.noiseaware.com/client/properties/?pageSize=200&page='+pg+'&ordering=name',{headers:H})).json();(j.results||[]).forEach(p=>props.push({id:p.id,name:p.name}));if(j.next)pg++;else break;}
const BEFORE='<BEFORE>';   // as-of + 1 day (exclusive upper bound)
// MONTHS/ENDS are DERIVED from BEFORE, never hand-maintained: a hardcoded month list silently
// drops the newest month the moment the calendar rolls into it, silently and with no error.
// Series starts 2026-02 (first month with program data).
const ASOF=new Date(new Date(BEFORE+'T00:00:00Z').getTime()-86400000).toISOString().slice(0,10);
const MONTHS=[];{let y=2026,m=2;const ey=+ASOF.slice(0,4),em=+ASOF.slice(5,7);
 while(y<ey||(y===ey&&m<=em)){MONTHS.push(y+'-'+String(m).padStart(2,'0'));m++;if(m>12){m=1;y++;}}}
const ENDS=MONTHS.map((ym,i)=>{if(i===MONTHS.length-1)return BEFORE;const q=ym.split('-').map(Number);return new Date(Date.UTC(q[0],q[1],1)).toISOString().slice(0,10);});
async function cum(pid,end){const body={items:[{start:'2026-01-01',end:end,intervalType:'days',interval:400,metrics:['rest_costs'],grouping:'property',summarize:true,properties:[pid]}]};const mj=await(await fetch('https://api.resteasy.noiseaware.com/client/reports/chart/',{method:'POST',headers:HJ,body:JSON.stringify(body)})).json();const g=(mj.items&&mj.items[0]&&mj.items[0].graphs)||[];const gr=g.find(x=>x.key==='rest_costs');return gr?gr.data.reduce((s,d)=>s+(d.rawValue||0),0):0;}
const out=[];for(const p of props){if(!/[A-Za-z]/.test(p.name))continue;
 let page=1,all=[];while(true){const u='https://api.resteasy.noiseaware.com/client/events/?eventClass=SMOKE&includeInternalEvents=false&localCreatedOnDateAfter=2026-01-01&localCreatedOnDateBefore=<BEFORE>&ordering=-createdOn&pageSize=300&page='+page+'&property='+p.id;const j=await(await fetch(u,{headers:H})).json();(j.results||[]).forEach(e=>all.push(e));if(j.next)page++;else break;}
 const MB={};for(const e of all){const fb=e.smokeFeedback||{};const nc=parseFloat(fb.netChargeAmount||0)||0;const m=e.createdOn.slice(0,7);if(!MB[m])MB[m]=[0,0,0];if(e.billable){MB[m][0]++;if(nc>0)MB[m][1]++;}MB[m][2]+=nc;}
 const cums=await Promise.all(ENDS.map(en=>cum(p.id,en)));let prev=0;const rM={};MONTHS.forEach((m,i)=>{rM[m]=+(cums[i]-prev).toFixed(2);prev=cums[i];});
 out.push(p.name+'|'+MONTHS.map(m=>{const b=MB[m]||[0,0,0];return m+':'+b[0]+','+b[1]+','+(+b[2].toFixed(2))+','+rM[m];}).join('|'));}
document.body.replaceChildren();const pre=document.createElement('pre');pre.textContent='@@F@@\n'+out.join('\n')+'\n@@E@@';document.body.appendChild(pre);'ok';
```
Save the lines between `@@F@@`/`@@E@@` to `monthly.txt`.

**Pull B — daily billable/charged/net per hotel** (exact date filtering). Uses `pageSize=500` and bails on any non-200 page (a dropped page silently under-counts). The dump header carries running totals `TB`/`TC`:
```js
const tok=JSON.parse(localStorage.getItem('auth_token'));const H={Authorization:'Bearer '+tok.access,'X-Org':String(tok.organization)};
let props=[],pg=1;while(true){const j=await(await fetch('https://api.resteasy.noiseaware.com/client/properties/?pageSize=200&page='+pg+'&ordering=name',{headers:H})).json();(j.results||[]).forEach(p=>props.push({id:p.id,name:p.name}));if(j.next)pg++;else break;}
const out=[];let TB=0,TC=0;
for(const p of props){let page=1,all=[],ok=true;while(true){const u='https://api.resteasy.noiseaware.com/client/events/?eventClass=SMOKE&includeInternalEvents=false&localCreatedOnDateAfter=2026-01-01&localCreatedOnDateBefore=<BEFORE>&ordering=-createdOn&pageSize=500&page='+page+'&property='+p.id;const r=await fetch(u,{headers:H});if(!r.ok){ok=false;break;}const j=await r.json();(j.results||[]).forEach(e=>all.push(e));if(j.next)page++;else break;}
 if(!ok){out.push('ERR '+p.name);continue;} if(all.length===0)continue;
 const Dm={};for(const e of all){const fb=e.smokeFeedback||{};const nc=parseFloat(fb.netChargeAmount||0)||0;const d=e.createdOn.slice(0,10);if(!Dm[d])Dm[d]=[0,0,0];if(e.billable){Dm[d][0]++;TB++;if(nc>0){Dm[d][1]++;TC++;}}Dm[d][2]+=nc;}
 out.push(p.name+'|'+Object.keys(Dm).sort().map(d=>d+':'+Dm[d][0]+','+Dm[d][1]+','+(+Dm[d][2].toFixed(2))).join('|'));}
document.body.replaceChildren();const pre=document.createElement('pre');pre.textContent='@@DLY@@ TB='+TB+' TC='+TC+'\n'+out.join('\n')+'\n@@E@@';document.body.appendChild(pre);'ok';
```
Save the lines between `@@DLY@@`/`@@E@@` to `daily.txt`. **Verify:** `TB` (billable) and `TC` (charged) must equal Pull A's totals AND the Metrics tab's "Billable Events" / "Billable Events Charged" totals. If a line starts with `ERR` or the totals don't match, re-run — a page 503'd and the pull is short. (The authoritative billable count is the rest. Metrics endpoint; counting raw events must reconcile to it.)

**First, export the hotel reference from Supabase.** Two sources, joined at LOAD time only:
`public.rest_hotels` holds the Rest-specific facts (`rest_name`, `go_live`, `model`) and
`public.dim_hotel` supplies the shared ones (`num_keys`, `management_company`, `asset_manager`)
so they are never duplicated and can never drift. Run this through the Supabase MCP `execute_sql` (project
`gfsusmsstpjqwrvcxjzt`) and save the JSON array it returns to `rest_hotels.json`:
```sql
select r.hotel_id, r.rest_name, d.num_keys, r.go_live,
       d.management_company as mgmt_company, d.asset_manager, r.model
from public.rest_hotels r
left join public.dim_hotel d on d.hotel_id = r.hotel_id
order by r.rest_name;
```
**If any row comes back with a null `num_keys` or `mgmt_company`, stop.** That means a Rest hotel is
missing from `dim_hotel` (or was archived out of it). `load_supabase.py` refuses to run in that case
rather than loading a hotel with no denominator. Fix `dim_hotel` (via the Master Hotel List) first.

Note this is a load-time join only: the values get denormalized onto every `rest_monthly` row, so the
dashboard still reads one table and joins to nothing.

**Then check whether any key count moved.** Keys are the denominator of Incident Rate and RevPAR, so a
Hotel Master edit silently changes those figures. This reports any hotel whose key count differs from
the last load - if it returns rows, mention them in your closing message:
```sql
select r.rest_name, m.num_keys as loaded_keys, d.num_keys as dim_keys
from public.rest_hotels r
join (select distinct hotel_id, num_keys from public.rest_monthly) m on m.hotel_id = r.hotel_id
left join public.dim_hotel d on d.hotel_id = r.hotel_id
where d.num_keys is distinct from m.num_keys;
```
Then refresh the local caches that the weekly Excel still reads (they are DERIVED - never hand-edit
them, and never treat them as the source of truth):
```
python3 scripts/sync_reference.py rest_hotels.json
```

Then build the overwrite SQL:
```
python3 scripts/load_supabase.py monthly.txt daily.txt <ASOF-YYYY-MM-DD> ./sql rest_hotels.json
```
This writes exactly **one** file, `./sql/rest_load_00.sql`: `delete from public.rest_monthly` followed
by the full monthly insert. Run that single file through the Supabase MCP `execute_sql`.

**One file is deliberate.** One `execute_sql` call is one transaction, so the delete and the insert
commit together and a reader can never catch the table empty or half-loaded. If the call fails,
nothing changed - just re-run it.

`load_supabase.py` also prints `TB`/`TC` (billable / charged derived from the daily pull) and a
`*** HOTEL(S) SKIPPED ***` block for any hotel in the pull that is missing from `public.rest_hotels`.
It refuses to write a delete with no insert.

This is an **overwrite** — no history is kept; each run replaces the full current series.
**Refresh frequency does not change the data's shape.** `rest_monthly` holds one row per hotel per
calendar month, so running it daily instead of weekly does NOT accumulate snapshots or versions — the
3 Sep run simply replaces what the 2 Sep run wrote, and September still has exactly one row per hotel.
Row totals do still grow with time, by roughly 25 rows per calendar month. Monthly
billable/charged/net are derived from the daily pull (kept exactly consistent); `rest_cost` comes from
the metrics endpoint. Hotel attributes + the as-of date are denormalized onto every `rest_monthly` row,
so the dashboard never joins to anything. (rest_cost is flaky — several hotels report $0 in recent
months; the dashboard notes Expense is month-based.)

**There is no `rest_daily` table** — retired in migration 124, because the dashboard's date range is
whole calendar months only and monthly tied to the daily rows exactly (verified: 150/150 hotel-months
identical, plus 2 zero-event months only monthly carried; and 135 hotel/month-range combinations
agreed exactly). `daily.txt` is still pulled and read: monthly is derived from it, and its TB/TC
totals are the reconciliation check. It is simply no longer stored.

**Verify after loading** — confirm the loaded totals tie to the Metrics endpoint's
Billable / Billable-Charged totals, and that the as-of date is the one you just loaded:
```sql
select max(as_of)::text as as_of, count(*) as rows,
       sum(billable) as billable, sum(charged) as charged,
       round(sum(net_charges)::numeric,2) as collected
from public.rest_monthly;
```

### Publishing
`rest-reporting.html` is the hosted page, and the copy in the **noble-extranet repo is the source of truth** (this skill does not keep its own copy). It is named `rest-reporting.html` and NOT `dashboard.html` because `dashboard.html` is already the extranet's own home page and must never be overwritten. It lives in the **noble-extranet GitHub repo** (Vercel-deployed at `https://noble-extranet.vercel.app/rest-reporting.html`) and holds NO data — it reads `rest_monthly` from Supabase using the project's publishable key and the viewer's existing extranet login (RLS restricts reads to internal users). Commit the page to the repo only ONCE (or when the page's code changes); routine data refreshes need no redeploy — the Supabase overwrite above is enough for the live page to show new numbers on reload.

## Step 7 — Deliver

**Mode B (the report):** surface **`Rest<M-D>.docx`** as a clickable card in the chat via
`present_files`. That is the only deliverable. `Email.xlsx` is an intermediate used to render the
embedded table picture - do NOT present it; the user exports the spreadsheet themselves from the
dashboard's Export to Excel button. Never finish a Mode B run without presenting the Word doc.
On `/rest B`, close by saying the dashboard was NOT refreshed and how stale it is.

**Mode A (the data refresh):** there are no files. Report in one short line: the as-of date loaded,
the billable / charged / collected totals from the verification query, and any skipped hotels. Link
`https://noble-extranet.vercel.app/rest-reporting.html`. If anything failed, say plainly that the
refresh did not happen - never report a partial load as success.

**A bare `/rest` reports both** - the refresh line first, then the Word doc. If the report's as-of
differs from the refresh's as-of, state both so the difference is not read as an error.

## Definitions & rules (must stay consistent)
- **Billable** = events eligible to charge; **Charged** = billable events where net collected > 0.
- **Incident Rate** = Billable / (Keys × Days Since Go-Live); flag red < 0.60%.
- **Charge Rate** = Charged / Billable; flag red < 75%.
- **Profit** = Revenue (Net Collected) − Expense (Rest Cost); flag red < 0.
- **Payback** = Capex / (Proj. Annual Incidents × 140); flag green (00B050) < 1.25 yrs. Capex = Keys × $350. Proj. Annual Incidents = INT(Billable / Days × 365).
- **Days Since Go-Live** is a live `=TODAY()-GoLive+1` formula in Excel (advances daily).
- **Management Company** = per-hotel column N, from `reference/keys_golive.json` (`mgmt` field). A rollup table sits two rows below the Total row, one row per management company (alphabetical), with a "<N> Hotels" count in the Go-Live-Date column and the same metric columns - **Management Company** = per-hotel column N, from `reference/keys_golive.json` (`mgmt` field). A rollup table sits two rows below the Total row, one row per management company (alphabetical), with a "<N> Hotels" count in the Go-Live-Date column and the same metric columns aggregated via SUMIF/SUMPRODUCT over the hotel rows. Same red/green flag rules apply to the rollup rows.
- **Word narrative exceptions** (sub-bullets): show each billable window event NOT fully charged — partial ("Charged $X"), "Not charged" (with reason), or "Not yet charged (pending)". Omit fully-charged events (net==charge) and REPEAT_OFFENSE.
- **Formatting:** gray banding D9D9D9, no gridlines, M/D/YYYY dates, Total-row size 16, Capex-Cost left border, wrapped headers, reason/keys/days columns hidden/grouped. Word doc greeting default "Good afternoon,"; signature = LANDON WATTS bold Segoe UI #4E6A84, contact lines Segoe UI Light, email/site #467886. Embedded table picture is produced by `render_table.py` (portrait letter body + table on its own landscape page).
