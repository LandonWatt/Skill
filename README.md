# Skills

Version-controlled copies of Landon Watts' Claude skills, so a skill reinstall or sync can
never silently lose them.

## rest

Two modes, one skill, chosen by the argument you type.

| Invoked as | Runs | Result |
|---|---|---|
| `/rest` | Mode A, then Mode B | Dashboard refreshed **and** `Rest<M-D>.docx` |
| `/rest A` | Mode A only | Dashboard refreshed. No documents, no prompts. |
| `/rest B` | Mode B only | `Rest<M-D>.docx` only. Supabase untouched. |

**Mode A — data refresh.** Scrapes rest. (NoiseAware) and overwrites `public.rest_monthly` in
Supabase, which is what the hosted dashboard reads. Data refreshes need no redeploy — the page
reads Supabase live.

**Mode B — weekly report.** Produces `Rest<M-D>.docx` only.

Neither mode invokes the other; a bare `/rest` runs both because the caller asked for both. It
refreshes first, so a broken session fails before any document work is wasted and the dashboard
still ends up current if the document build later goes wrong. Mode A always uses **as-of = today**
even when the report itself is back-dated, so a back-dated report can never rewind the live
dashboard.

Every run opens with a health check reporting how stale the data is, any hotel the next load would
skip, and any attribute edit that has not reached the dashboard yet. Nothing runs on a schedule —
that health check is the only place problems surface.

### Where the pieces live

| Piece | Location |
|---|---|
| Dashboard page | `rest-reporting.html` in **bozhangnoble/noble-extranet** (that copy is the source of truth) |
| Live URL | https://noble-extranet.vercel.app/rest-reporting.html |
| Data | Supabase project `gfsusmsstpjqwrvcxjzt`, tables `rest_monthly` + `rest_hotels` |
| This skill, installed | `%APPDATA%\Roaming\Claude\local-agent-mode-sessions\skills-plugin\<ids>\skills\rest\` |

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
- The skill folder must be named `rest`, lowercase: the packager rejects anything that is not
  kebab-case. Typing `/Rest` still finds it.

### Installing / updating

`rest.skill` is the packaged form. Its file card offers a **Save skill** button when the account
allows skill creation; the unpacked folder is here as the fallback and as the readable copy.
