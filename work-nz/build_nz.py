"""Build NZ section for ANZSCO-Viewer (offline, file://).

Reads INZ pages saved in work-nz/*.html, emits:
  master-nz.csv, sources-nz.csv,
  nz-index.html, nz-occupation-viewer.html,
  nz-green-t1-view.html, nz-green-t2-view.html, nz-aewv-nol-view.html

Re-run after Green List / median-wage updates; record dates in sources-nz.csv.
Sources (fetched Oct 2026):
  Appendix 13 Green List (eff. 09/03/2026) — opsmanual/89117.htm
  NOL occupations for AEWV — Tables 1-6 (eff. 03/11/2025 + 09/03/2026)
"""
import csv
import json
import re
import html as ihtml
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SNAP = "Oct 2026"
GREEN_EFF = "09/03/2026"
MEDIAN_WAGE = "$35.00/hr (from 9 Mar 2026, SR5.15.1)"


class Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self._cur = None
        self._row = None
        self._cell = None
        self._rs = 1

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._cur = []
        elif tag == "tr" and self._cur is not None:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
            self._rs = 1
            for k, v in attrs:
                if k == "rowspan":
                    try:
                        self._rs = max(1, int(v))
                    except ValueError:
                        pass
        elif tag == "br" and self._cell is not None:
            self._cell.append("\n")

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None:
            self._row.append(("".join(self._cell).strip(), self._rs))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if any(t.strip() for t, _ in self._row):
                self._cur.append(self._row)
            self._row = None
        elif tag == "table" and self._cur is not None:
            if self._cur:
                self.tables.append(self._cur)
            self._cur = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def expand(rows, ncols=4):
    """Expand rowspan-fragmented INZ table rows into full n-col logical rows."""
    pending = {}
    out = []
    for cells in rows:
        r = [None] * ncols
        for col in range(ncols):
            if pending.get(col, [0])[0] > 0:
                r[col] = pending[col][1]
                pending[col][0] -= 1
        ci = 0
        for text, rs in cells:
            while ci < ncols and r[ci] is not None:
                ci += 1
            if ci >= ncols:
                break
            r[ci] = text
            if rs > 1:
                pending[ci] = [rs - 1, text]
            ci += 1
        out.append([c or "" for c in r])
    return out


def parse_tables(path):
    p = Tables()
    p.feed(Path(path).read_text(encoding="utf-8", errors="replace"))
    return p.tables


def clean(s):
    return re.sub(r"\s+", " ", (s or "")).strip()


def split_occupations(cell):
    """Split an INZ occupation cell into (title, code) via 6-digit ANZSCO codes.

    Parenthesised codes take the preceding text as title
    ("Chemical Engineer (233111)"); bare codes take the following text
    ("221213 External Auditor 221214 Internal Auditor").
    """
    out = []
    matches = list(re.finditer(r"\b(\d{6})\b", cell))
    for i, m in enumerate(matches):
        nxt = matches[i + 1].start() if i + 1 < len(matches) else len(cell)
        if m.start() > 0 and cell[m.start() - 1] == "(":
            start = matches[i - 1].end() if out else 0
            pre = clean(cell[start:m.start()])
            title = re.sub(r"[(\s,;·•\-–—|/]+$", "", pre).strip()
        else:
            title = clean(cell[m.end():nxt])
            title = re.sub(r"^[)\s,;·•\-–—|/]+", "", title).strip()
        out.append((title, m.group(1)))
    return out


def parse_green(path):
    tables = parse_tables(path)
    # Tier 1 = largest 4-col table, Tier 2 = next 4-col table
    cands = [t for t in tables if t and len(t[0]) == 4 and "ccupation" in t[0][1][0]]
    assert len(cands) >= 2, f"expected Tier1+Tier2 tables, got {len(cands)}"
    tiers = {}
    for tier, table in zip(("Tier 1", "Tier 2"), cands[:2]):
        recs = {}
        for row in expand(table[1:]):
            group, occ_cell, req, reg = (clean(c) for c in row[:4])
            for title, code in split_occupations(occ_cell):
                if code in recs:
                    # same code listed twice (e.g. 251211) — merge titles
                    if title and title not in recs[code]["title"]:
                        recs[code]["title"] += " / " + title
                    continue
                recs[code] = {
                    "code": code, "title": title, "group": group,
                    "tier": tier, "requirements": req, "registration": reg,
                }
        tiers[tier] = recs
    return tiers


def parse_nol(path):
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    # "Table N: ... skill level X ..." headings precede each table
    heads = list(re.finditer(
        r"Table\s+(\d)\s*:[^<>]*?skill levels?\s*(\d)", raw, re.IGNORECASE))
    eff = {"1": "2026-03-09", "2": "2026-03-09", "3": "2026-03-09",
           "4": "2025-11-03", "5": "2025-11-03", "6": "2025-11-03"}
    recs = {}
    blocks = [(m.start(), m.group(0))
              for m in re.finditer(r"<table.*?</table>", raw, re.DOTALL | re.IGNORECASE)]
    for h in heads:
        n, skill = h.group(1), h.group(2)
        enclosing = [b for pos, b in blocks if pos < h.start() < pos + len(b)]
        assert enclosing, f"no enclosing table for Table {n} heading"
        p = Tables()
        p.feed(enclosing[-1])
        for row in p.tables[0]:
            cells = [clean(t) for t, _ in row]
            if cells and re.fullmatch(r"\d{6}", cells[0]):
                code = cells[0]
                recs[code] = {"code": code, "title": cells[1] if len(cells) > 1 else "",
                              "nol_skill": skill, "nol_effective": eff[n],
                              "nol_table": n}
    return recs


def main():
    tiers = parse_green(HERE / "appendix13.html")
    t1, t2 = tiers["Tier 1"], tiers["Tier 2"]
    print(f"Green Tier 1 occupations: {len(t1)} (INZ: 146)")
    print(f"Green Tier 2 occupations: {len(t2)} (INZ: 37)")
    nol = parse_nol(HERE / "nol-aewv.html")
    print(f"NOL AEWV occupations: {len(nol)}")

    au = {o["code"]: o for o in
          json.loads((ROOT / "work" / "occupations.json").read_text(encoding="utf-8"))}

    rows = []
    for tier_name, tier in (("Tier 1", t1), ("Tier 2", t2)):
        for code, g in tier.items():
            a = au.get(code, {})
            n = nol.get(code)
            rows.append({
                "code": code, "title": g["title"] or a.get("title", ""),
                "skill_anzsco": a.get("skill_level", ""),
                "description": a.get("description", ""),
                "nz_group": g["group"], "green_tier": tier_name,
                "requirements": g["requirements"], "registration": g["registration"],
                "nol_skill": n["nol_skill"] if n else "",
                "nol_effective": n["nol_effective"] if n else "",
                "in_au_viewer": "YES" if a else "NO — NZ Green List code outside AU v1.3 set",
            })
    green_codes = set(t1) | set(t2)
    for code, n in sorted(nol.items()):
        if code in green_codes:
            continue
        rows.append({
            "code": code, "title": n["title"], "skill_anzsco": "",
            "description": "", "nz_group": "NOL (new, no ANZSCO equivalent)",
            "green_tier": "", "requirements": "", "registration": "",
            "nol_skill": n["nol_skill"], "nol_effective": n["nol_effective"],
            "in_au_viewer": "NO — NOL-only code",
        })
    rows.sort(key=lambda r: (r["green_tier"] == "", r["green_tier"], r["code"]))
    print(f"master-nz rows: {len(rows)}")

    fields = ["code", "title", "skill_anzsco", "description", "nz_group",
              "green_tier", "requirements", "registration",
              "nol_skill", "nol_effective", "in_au_viewer"]
    with open(ROOT / "master-nz.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    with open(ROOT / "sources-nz.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["dataset", "source", "effective", "notes"])
        w.writerow(["green_tier1/2 + requirements + registration",
                    "immigration.govt.nz/opsmanual/89117.htm (Appendix 13)", GREEN_EFF,
                    f"{len(t1)} Tier-1 + {len(t2)} Tier-2 occupations by ANZSCO code"])
        w.writerow(["nol_aewv Tables 1-6",
                    "immigration.govt.nz .../national-occupation-list-occupations-used-for-an-aewv/",
                    "2025-11-03 + 2026-03-09",
                    f"{len(nol)} NOL skill 1-3 occupations recognised for AEWV job check only"])
        w.writerow(["median_wage", "INZ ops manual SR5.15.1", "2026-03-09", MEDIAN_WAGE])
        w.writerow(["descriptions/ANZSCO skill", "ANZSCO-Viewer work/occupations.json (ANZSCO v1.3 mirror)",
                    SNAP, "blank where Green/NOL code has no v1.3 equivalent"])
        w.writerow(["smc_points_summary", "immigration.govt.nz SMC pathway pages (SR3.10-SR3.35)",
                    SNAP, "static guidance in pages; 6 points via qual/income/registration + NZ work exp"])
    (HERE / "master-nz.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")

    build_pages(rows, t1, t2, nol)
    print("pages built")


def esc(s):
    return ihtml.escape(str(s or ""), quote=True)


def style_from(path):
    raw = (ROOT / path).read_text(encoding="utf-8")
    return raw.split("<style>", 1)[1].split("</style>", 1)[0]


NZ_NOTE = ("NZ section &bull; snapshot Oct 2026 &bull; Green List eff. 9 Mar 2026 &bull; "
           "median wage $35.00/hr &bull; verify on immigration.govt.nz before advising")


def hub_nav():
    return ("<a href='master-nz.csv'>master-nz.csv</a> &bull; <a href='sources-nz.csv'>sources</a>")


NAV_CSS = (
    ".sitenav{display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center;"
    "border-top:2px solid #e7e2d6;border-bottom:1px solid #f1eee4;"
    "padding:9px 2px;margin:0 0 16px;font-size:13.5px}"
    ".sitenav a{color:#23206e;font-weight:650;text-underline-offset:3px}"
    ".sitenav a:hover{text-decoration-thickness:2px}"
    ".sitenav .here{color:#1d2030;font-weight:750}"
    ".sitenav .sep{color:#9aa1ad}"
    "@media (max-width:640px){.sitenav{font-size:13px;padding:8px 2px}}"
)

NAV_ITEMS = [
    ("AU hub", "index.html"),
    ("AU viewer", "occupation-viewer.html"),
    ("NZ index", "nz-index.html"),
    ("NZ viewer", "nz-occupation-viewer.html"),
]


def sitenav(page):
    parts = []
    for label, href in NAV_ITEMS:
        if href == page:
            parts.append("<span class='here' aria-current='page'>" + label + "</span>")
        else:
            parts.append("<a href='" + href + "'>" + label + "</a>")
    return "<nav class='sitenav' aria-label='Site'>" + "<span class='sep'>\u2022</span>".join(parts) + "</nav>"


def build_pages(rows, t1, t2, nol):
    green = [r for r in rows if r["green_tier"]]
    nol_only = [r for r in rows if not r["green_tier"]]

    # ---- nz-index.html (hub, same narrow style as AU index) ----
    st = style_from("index.html") + NAV_CSS
    groups = {}
    for r in green:
        groups.setdefault((r["green_tier"], r["nz_group"]), []).append(r)
    lis = []
    for (tier, grp), items in sorted(groups.items()):
        lis.append(f"<tr><td>{esc(tier)}</td><td>{esc(grp)}</td><td>{len(items)}</td></tr>")
    (ROOT / "nz-index.html").write_text(
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>\n"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>\n"
        "<title>New Zealand — Green List occupations (internal)</title>\n"
        f"<style>{st}</style></head><body><div class='wrap'>\n"
        "<h1>New Zealand — Green List occupations</h1>\n"
        "<p class='sub'>Pick a pathway — Straight to Residence, Work to Residence, or AEWV — or search a single occupation.</p>\n"
        f"<p class='meta'>Internal reference &bull; {NZ_NOTE} &bull; {hub_nav()}</p>\n"
        f"{sitenav('nz-index.html')}\n"
        "<div class='card'><table><tr><th>Pathway</th><th>What it gives</th><th>Occupations</th><th>View</th></tr>\n"
        f"<tr><td>Green List Tier 1</td><td>Straight to Residence (apply with job offer)</td><td>{len(t1)}</td>"
        "<td><a href='nz-green-t1-view.html'>open</a></td></tr>\n"
        f"<tr><td>Green List Tier 2</td><td>Work to Residence (after 24 months in role)</td><td>{len(t2)}</td>"
        "<td><a href='nz-green-t2-view.html'>open</a></td></tr>\n"
        f"<tr><td>NOL for AEWV</td><td>Job check / AEWV at NOL skill 1–3 (incl. {len(nol_only)} NOL-only codes)</td><td>{len(nol)}</td>"
        "<td><a href='nz-aewv-nol-view.html'>open</a></td></tr>\n"
        "<tr><td>SMC</td><td>6 points via qualification / income / registration + NZ work experience; "
        "Trades & Technician pathway for eligible roles</td><td>points-based, no fixed list</td>"
        "<td><a href='nz-occupation-viewer.html'>check skill level</a></td></tr>\n"
        "</table></div>\n"
        "<div class='card'><table><tr><th>Tier</th><th>Group</th><th>Count</th></tr>\n"
        + "".join(lis) + "</table></div>\n"
        "<div class='card'><p style='font-size:13px;color:#606778'>SMC points (Mar 2026 settings): income 6pts at 3x median "
        "($105/hr), 4pts at 2x ($70/hr), 3pts at 1.5x ($52.50/hr); registration 3–6pts by training years; "
        "top-up 1–3pts from skilled NZ work experience. Both Green tiers need an accredited employer and age ≤55. "
        "NOL codes are valid for AEWV job check only — use ANZSCO for SMC/other visas.</p></div>\n"
        "</div></body></html>", encoding="utf-8")

    # ---- consolidated pathway views (same wide-table style as AU authority views) ----
    wst = style_from("acs-view.html") + NAV_CSS
    for fname, title, recs, blurb in [
        ("nz-green-t1-view.html", "NZ Green List Tier 1 — Straight to Residence", [r for r in rows if r["green_tier"] == "Tier 1"], "146 occupations"),
        ("nz-green-t2-view.html", "NZ Green List Tier 2 — Work to Residence", [r for r in rows if r["green_tier"] == "Tier 2"], "37 occupations"),
        ("nz-aewv-nol-view.html", "NZ NOL occupations recognised for AEWV", [r for r in rows if r["nol_skill"]], "skill 1–3, AEWV job check only"),
    ]:
        data = json.dumps(recs, ensure_ascii=False).replace("</", "<\\/")
        (ROOT / fname).write_text(
            "<!DOCTYPE html>\n<html lang='en'>\n<head>\n<meta charset='utf-8'>\n"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>\n"
            f"<title>{esc(title)} (internal)</title>\n<style>{wst}</style>\n</head>\n<body>\n"
            "<div class='wrap'>\n"
            f"<header class='top'><h1>{esc(title)}</h1><p>{esc(blurb)} &bull; {NZ_NOTE} &bull; "
            f"<a href='nz-index.html'>NZ index</a> &bull; <a href='index.html'>AU hub</a></p></header>\n"
            f"{sitenav(fname)}\n"
            "<div class='card'><div class='sum' id='sum'></div></div>\n"
            "<div class='card' style='overflow-x:auto'><table id='t'>\n"
            "<thead><tr><th>Code / Occupation</th><th>Skill</th><th>Group</th><th>Tier</th><th>NOL</th><th></th></tr></thead>\n"
            "<tbody id='rows'></tbody>\n</table></div>\n"
            "<div class='card foot'>Source: INZ Appendix 13 (Green List, eff. 9 Mar 2026) + NOL AEWV Tables 1–6. "
            "Full requirements stay in master-nz.csv. NOL codes: AEWV job check only.</div>\n</div>\n<script>\n"
            f"const DATA={data};\n"
            "function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}\n"
            "let h='';\nDATA.forEach(function(o,i){\n"
            "  h+='<tr><td><span class=\"code\">'+esc(o.code)+'</span><br><span class=\"title\">'+esc(o.title)+'</span></td><td>'+esc(o.skill_anzsco||'—')+'</td><td>'+esc(o.nz_group)+'</td><td>'+esc(o.green_tier||'—')+'</td><td>'+(o.nol_skill?esc(o.nol_skill)+' <small>from '+esc(o.nol_effective)+'</small>':'—')+'</td><td><a class=\"rowlink\" data-i=\"'+i+'\">details</a></td></tr>';\n"
            "  h+='<tr class=\"detail\" id=\"d'+i+'\" hidden><td colspan=\"6\"><b>'+esc(o.code)+' '+esc(o.title)+'</b> — '+esc(o.description||'No ANZSCO v1.3 description (NZ-only code).')+'<br><b>Requirements:</b> '+esc(o.requirements||'—')+'<br><b>Registration:</b> '+esc(o.registration||'—')+'</td></tr>';\n"
            "});\n"
            "document.getElementById('rows').innerHTML=h;\n"
            "document.getElementById('sum').innerHTML='<span><b>'+DATA.length+'</b> occupations</span><span><b>'+DATA.filter(o=>o.green_tier==='Tier 1').length+'</b> Tier 1</span><span><b>'+DATA.filter(o=>o.green_tier==='Tier 2').length+'</b> Tier 2</span><span><b>'+DATA.filter(o=>o.nol_skill).length+'</b> NOL-recognised</span>';\n"
            "document.querySelectorAll('.rowlink').forEach(function(a){a.addEventListener('click',function(){const r=document.getElementById('d'+a.getAttribute('data-i'));const open=r.hidden;r.hidden=!open;if(open){a.classList.add('open');}else{a.classList.remove('open');}});});\n"
            "</script>\n</body>\n</html>", encoding="utf-8")

    # ---- nz-occupation-viewer.html (single-occupation search, same style as AU viewer) ----
    vst = style_from("occupation-viewer.html") + NAV_CSS
    vdata = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    (ROOT / "nz-occupation-viewer.html").write_text(
        "<!DOCTYPE html>\n<html lang='en'>\n<head>\n<meta charset='utf-8'>\n"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>\n"
        "<title>NZ Occupation Viewer (internal)</title>\n<style>" + vst + "</style>\n</head>\n<body>\n"
        "<div class='wrap'>\n"
        f"<header class='top'><h1>NZ Occupation Viewer</h1><p>Internal reference &bull; {NZ_NOTE}</p></header>\n"
        f"{sitenav('nz-occupation-viewer.html')}\n"
        "<div class='picker'><label for='q'>Occupation (type code or name)</label>\n"
        "<input id='q' list='occs' placeholder='e.g. 233211 or Civil Engineer' autocomplete='off'>\n"
        "<datalist id='occs'></datalist></div>\n"
        "<div id='view'><div class='card'><p class='meta'>Select an occupation above to see its NZ pathways.</p></div></div>\n"
        "<div class='card foot'>Sources: INZ Appendix 13 + NOL AEWV tables. See <b>master-nz.csv</b> and "
        "<b>sources-nz.csv</b>. NOL codes are AEWV-only; SMC points depend on qual/income/registration + NZ work experience.</div>\n"
        "</div>\n<script>\n"
        f"const DATA={vdata};\n"
        "const byCode={};DATA.forEach(o=>byCode[o.code]=o);\n"
        "const dl=document.getElementById('occs');\n"
        "DATA.forEach(o=>{const el=document.createElement('option');el.value=o.code+' — '+o.title;dl.appendChild(el);});\n"
        "function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}\n"
        "function pill(l,v,ok){return '<span class=\"pill '+(ok?'y':'n')+'\">'+esc(l)+' <small>'+esc(v)+'</small></span>';}\n"
        "function render(code){\n"
        "  const o=byCode[code];if(!o)return;\n"
        "  let h='<div class=\"card\"><span class=\"code\">'+esc(o.code)+'</span><h2>'+esc(o.title)+'</h2>';\n"
        "  h+='<p class=\"desc\">'+esc(o.description||'No ANZSCO v1.3 description — NZ-only code.')+'</p>';\n"
        "  h+='<p class=\"meta\">ANZSCO skill <b>'+esc(o.skill_anzsco||'—')+'</b> &nbsp;•&nbsp; '+esc(o.nz_group)+'</p></div>';\n"
        "  h+='<div class=\"card\"><h2 class=\"sec\">NZ pathways</h3><div class=\"badges\">'\n"
        "    +pill('Green',o.green_tier||'not listed',!!o.green_tier)\n"
        "    +pill('NOL-AEWV',o.nol_skill?('skill '+o.nol_skill):'—',!!o.nol_skill)+'</div></div>';\n"
        "  h+='<div class=\"card\"><h2 class=\"sec\">Requirements</h3><p class=\"meta\"><b>INZ requirements:</b> '+esc(o.requirements||'—')+'<br><b>Registration:</b> '+esc(o.registration||'—')+(o.nol_effective?'<br>NOL recognised from '+esc(o.nol_effective)+' (AEWV job check only).':'')+'</p></div>';\n"
        "  document.getElementById('view').innerHTML=h;\n"
        "}\n"
        "document.getElementById('q').addEventListener('change',function(e){\n"
        "  const m=/^(\\d{6})/.exec(e.target.value||'');if(m&&byCode[m[1]])render(m[1]);\n"
        "});\n"
        "</script>\n</body>\n</html>", encoding="utf-8")


if __name__ == "__main__":
    main()
