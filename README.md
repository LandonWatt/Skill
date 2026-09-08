# Skills

Version-controlled copies of Landon Watts' Claude skills, so a skill reinstall or sync can
never silently lose them.

## rest-weekly-report

Two modes, one skill.

**Mode A — daily data refresh.** Scrapes rest. (NoiseAware) and overwrites `public.rest_monthly`
in Supabase, which is what the hosted dashboard reads. No documents, never prompts. Runs on a
9:02am scheduled task. Data refreshes need no redeploy — the page reads Supabase live.

**Mode B — weekly report.** Produces `Rest<M-D>.docx` only. Opens with a health check that
reports how stale the data is, any hotel the next load would skip, and any attribute edit that
has not reached the dashboard yet.

### Where the pieces live

| Piece | Location |
|---|---|
| Dashboard page | `rest-reporting.html` in **bozhangnoble/noble-extranet** (that copy is the source of truth) |
| Live URL | https://noble-extranet.vercel.app/rest-reporting.html |
| Data | Supabase project `gfsusmsstpjqwrvcxjzt`, tables `rest_monthly` + `rest_hotels` |
| This skill, installed | `%APPDATA%\Roaming\Claude\local-agent-mode-sessions\skills-plugin\<ids>\skills\rest-weekly-report\` |

### Things that are easy to get wrong

- The page is **`rest-reporting.html`, never `dashboard.html`** — `dashboard.html` is the
  extranet's own home page and overwriting it takes the site's front door down.
- `public.rest_hotels` holds only Rest-specific facts: `rest_name`, `go_live`, `model`. Keys and
  management company come from `dim_hotel` at load time and must not be duplicated.
- The dashboard reads hotel attributes **denormalised onto `rest_monthly`**, so editing
  `rest_hotels` alone changes nothing on the page until those rows are re-stamped. The skill has
  the UPDATE that pushes it through.
- There is no `rest_daily` table. The date range is whole calendar months only.
- Month lists in the pull are **derived from the run date**, never hand-maintained — a hardcoded
  list silently drops the newest month when the calendar rolls.

### Installing / updating

`rest-weekly-report.skill` is the packaged form. Its file card offers a **Save skill** button
when the account allows skill creation; the unpacked folder is here as the fallback and as the
readable copy.
