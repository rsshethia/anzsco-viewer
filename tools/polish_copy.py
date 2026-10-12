"""One-off polish fixes across built pages (convergent, safe to re-run).

- "1 occupations" -> "1 occupation" in authority-view headers.
- Mismatched <h2 class="sec">...</h3> closers -> </h2> (AT outline fix).
- "(none)-assessed ..." title/H1 -> "No assessing authority ..." (matches hub label).

Skips third-party raw snapshots under work-nz/ (nol-aewv.html, appendix13.html).
NZ viewer JS templates are fixed at the source in work-nz/build_nz.py;
this script also repairs the already-generated nz-occupation-viewer.html.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FILES = [p for p in sorted(ROOT.glob("*.html")) if p.name != "redesign.html"]

TOTAL = {"plural": 0, "h3": 0, "none": 0}

for path in FILES:
    raw = path.read_text(encoding="utf-8")
    orig = raw
    n = raw.count(">1 occupations &bull;")
    raw = raw.replace(">1 occupations &bull;", ">1 occupation &bull;")
    TOTAL["plural"] += n
    n = raw.count("</h3>")
    raw = raw.replace("</h3>", "</h2>")
    TOTAL["h3"] += n
    # full-phrase replacement: "(none)-assessed occupations — ..." is ungrammatical;
    # title keeps its " (internal)" suffix via stem match
    n = raw.count("(none)-assessed occupations")
    raw = raw.replace(
        "(none)-assessed occupations", "Occupations with no assessing authority"
    )
    TOTAL["none"] += n
    if raw != orig:
        path.write_text(raw, encoding="utf-8")
        print("fixed", path.name)

print(TOTAL)
