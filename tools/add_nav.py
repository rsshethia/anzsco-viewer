"""Add shared AU/NZ site nav to all viewer pages (idempotent).

Inserts one hairline <nav class="sitenav"> bar after </header> (or after the
intro <p> on hub pages without a header), plus its CSS before </style>.
Current page renders as plain text with aria-current="page".
Re-run safely: previous passes are stripped first, output is byte-stable.

Not covered: future NZ rebuilds emit nav natively (work-nz/build_nz.py).
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

ITEMS = [
    ("AU hub", "index.html"),
    ("AU viewer", "occupation-viewer.html"),
    ("NZ index", "nz-index.html"),
    ("NZ viewer", "nz-occupation-viewer.html"),
]

CSS = (
    ".sitenav{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;"
    "border-top:2px solid #e7e2d6;border-bottom:1px solid #f1eee4;"
    "padding:9px 2px;margin:0 0 16px;font-size:13.5px}"
    ".sitenav a{color:#23206e;font-weight:650;text-underline-offset:3px}"
    ".sitenav a:hover{text-decoration-thickness:2px}"
    ".sitenav .here{color:#1d2030;font-weight:750}"
    ".sitenav .sep{color:#9aa1ad}"
    "@media (max-width:640px){.sitenav{font-size:13px;padding:8px 2px}}"
)


def nav_for(page: str, q: str) -> str:
    parts = []
    for label, href in ITEMS:
        if href == page:
            parts.append(
                f"<span class={q}here{q} aria-current={q}page{q}>{label}</span>"
            )
        else:
            parts.append(f"<a href={q}{href}{q}>{label}</a>")
    sep = f"<span class={q}sep{q}>\u2022</span>"
    return f"<nav class={q}sitenav{q} aria-label={q}Site{q}>" + sep.join(parts) + "</nav>"


NAV_RE = re.compile(r"\n<nav[^>]*sitenav[^>]*>.*?</nav>", re.DOTALL)


def process(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    # strip any previous sitenav pass (markup incl. its leading newline + CSS)
    # so re-runs converge to byte-identical output
    raw = NAV_RE.sub("", raw)
    raw = raw.replace(CSS, "")
    q = '"' if 'href="index.html"' in raw or 'href="occupation-viewer.html"' in raw else "'"
    page = path.name
    nav = nav_for(page, q)
    if "</header>" in raw:
        raw = raw.replace("</header>", "</header>\n" + nav, 1)
    else:
        m = re.search(r"<h1>.*?</h1>(?:\s*<p[^>]*>.*?</p>)+", raw, re.DOTALL)
        assert m, f"no hub intro found in {page}"
        raw = raw[: m.end()] + "\n" + nav + raw[m.end():]
    assert "</style>" in raw, f"no style block in {page}"
    raw = raw.replace("</style>", CSS + "</style>", 1)
    # drive-by: drop trailing duplicated "verify before advising" in NZ headers
    # (they already carry "verify on immigration.govt.nz before advising")
    raw = raw.replace(
        ">AU hub</a> &bull; verify before advising</p>",
        ">AU hub</a></p>",
    )
    path.write_text(raw, encoding="utf-8")
    return "updated"


def main():
    changed, skipped = [], []
    for path in sorted(ROOT.glob("*.html")):
        if path.name == "redesign.html":
            continue
        (changed if process(path) == "updated" else skipped).append(path.name)
    print(f"updated ({len(changed)}):", " ".join(changed))
    print(f"skipped ({len(skipped)}):", " ".join(skipped))


if __name__ == "__main__":
    main()
