# DESIGN.md — ANZSCO Viewer visual system (internal)

Minimal, quiet, typography-led reference UI. One shared system across the hub,
occupation viewer, 38 authority views, and the ACS guide. All styling lives in
the Python builder templates (`build_all_auth.py`, `build_viewer.py`,
`build_acs_assess.py`); pages are regenerated, never hand-edited.

## Tokens

* Ground: warm paper `#fafaf7`, cards `#ffffff`, hairlines `#e7e2d6` / `#f1eee4`
* Ink `#1d2030`, secondary `#606778`; accent indigo `#23206e` (continuity kept)
* Semantics (data-carrying, never decorative): green `#0e7a3d`, amber `#8a5a00`,
  red `#a83226`, each with a tinted fill
* Type: system stack only (offline constraint — no webfonts); tabular numerals
  everywhere data appears; display headings 750 weight, −0.02em tracking

## Decisions

* Tables use horizontal rules only (2px header rule); row hover tint; sticky
  solid headers; wide tables swipe-scroll on small screens with a set min-width
* Section titles are true headings (`h2.sec`, 14.5–15px bold with a 2px rule),
  never eyebrow kickers
* Disclosure uses drawn CSS chevrons (`summary::before`, `.rowlink::after`),
  never text glyphs; closed states use strikethrough + tooltip, never ✕ marks
* Browser surfaces themed: indigo `::selection`, visible `:focus-visible` rings,
  16px inputs (no iOS zoom)
* Depth: one soft header shadow + 1px card hairline shadow; no offset blocks,
  no gradients, no glass, no icon-card grids
* Detector status (Oct 2026): zero errors/warnings; one advisory (em-dashes in
  ACS source-faithful criteria text, kept verbatim deliberately)
