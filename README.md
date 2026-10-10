# ANZSCO Occupation Viewer (private, internal reference)

Single-view reference for Australian skilled-migration occupations: visa pathways,
Commonwealth lists, 2025 Occupation Shortage List ratings, and 8-state nomination
flags with criteria. Snapshot **October 2026** — verify before advising.

## Use

Open `index.html` in a browser (works from `file://`, no server, no network calls on load).
Type an ANZSCO code or occupation name, e.g. `261311`.

`authorities-index.html` links the 38 per-assessing-authority consolidated views
(e.g. `acs-view.html`, `tra-view.html`, `vetassess-view.html`).

## Files

| File | Contents |
|---|---|
| `index.html` | Occupation viewer (623 occupations, self-contained) |
| `*-view.html` | Per-authority consolidated views + `authorities-index.html` hub |
| `master.csv` | Full matrix, 623 rows × 68 cols |
| `sources-used.csv` | Provenance: source + fetch date per column group |

## Data & caveats

* Occupation text/lists/OSL: offline mirror of anzscosearch.com, 10 Oct 2026.
* State flags/criteria: live state lists fetched Oct 2026 (QLD QSOL, NT offshore list,
  ACT Oct-2025 list, NSW Skills Lists, TAS rule, VIC/SA program-closed status,
  WA via third-party WASMOL mirror — **verify on migration.wa.gov.au**).
* Baseline visa flags use Dec-2024 settings (189/494 from MLTSSL+ROL; 482-SID/186
  from CSOL; 190/491 state-dependent). 60 newer CSOL codes outside the v1.3 set
  have no occupation pages.
* Invitation counts/points unavailable (Home Affairs rounds page is JS-only).

## Refresh

State lists change quarterly. Re-run the fetch/parse/merge scripts, then rebuild
`index.html` from `master.csv`; record fetch dates in `sources-used.csv`.
