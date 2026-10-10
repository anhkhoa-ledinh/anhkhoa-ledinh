#!/usr/bin/env python3
"""Fetch a GitHub contribution calendar and write the files the profile uses.

    docs/contributions.json      data for the star-sea page (GitHub Pages)
    profile/contrib-light.svg    README graph, light theme
    profile/contrib-dark.svg     README graph, dark theme

Usage:
    GH_TOKEN=... python3 scripts/contributions.py <login>
    python3 scripts/contributions.py --render-only      # redraw the SVGs from docs/contributions.json

Standard library only, so it runs on a plain GitHub Actions runner.
"""
import datetime as dt
import json
import os
import sys
import urllib.request
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(ROOT, "docs", "contributions.json")
SVG_DIR = os.path.join(ROOT, "profile")

LEVEL = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date weekday contributionCount contributionLevel } }
      }
    }
  }
}
"""

THEMES = {
    "light": {"fg": "#1f2328", "muted": "#59636e", "border": "#d1d9e0", "ring": "#1f23280f",
              "c": ["#eff2f5", "#aceebb", "#4ac26b", "#2da44e", "#116329"]},
    "dark": {"fg": "#f0f6fc", "muted": "#9198a1", "border": "#3d444d", "ring": "#f0f6fc0d",
             "c": ["#151b23", "#033a16", "#196c2e", "#2ea043", "#56d364"]},
}
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
FONT = "-apple-system, BlinkMacSystemFont, &apos;Segoe UI&apos;, &apos;Noto Sans&apos;, Helvetica, Arial, sans-serif"


def fetch(login, token):
    body = json.dumps({"query": QUERY, "variables": {"login": login}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": f"{login}-profile"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    if data.get("errors"):
        raise RuntimeError(data["errors"])
    cal = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = [
        [{"date": d["date"], "count": d["contributionCount"], "level": LEVEL.get(d["contributionLevel"], 0), "weekday": d["weekday"]}
         for d in w["contributionDays"]]
        for w in cal["weeks"]
    ]
    return {"login": login, "total": cal["totalContributions"], "updated": dt.date.today().isoformat(), "weeks": weeks}


def star(cx, cy, r):
    t = r * 0.28
    pts = [(cx, cy - r), (cx + t, cy - t), (cx + r, cy), (cx + t, cy + t), (cx, cy + r), (cx - t, cy + t), (cx - r, cy), (cx - t, cy - t)]
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + " Z"


def render(data, theme):
    t = THEMES[theme]
    weeks, total = data["weeks"], int(data["total"])
    pitch, cell = 13, 10
    left, top = 46, 56
    gw = len(weeks) * pitch - 3
    width = left + gw + 16
    box_y = 30
    box_h = (top - box_y) + 7 * pitch - 3 + 40
    height = box_y + box_h + 1
    heading = f"{total:,} contribution{'' if total == 1 else 's'} in the last year"
    o = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(heading)}">',
        f'<g font-family="{FONT}">',
        f'<text x="1" y="18" font-size="16" fill="{t["fg"]}">{escape(heading)}</text>',
        f'<rect x="0.5" y="{box_y + 0.5}" width="{width - 1}" height="{box_h - 1}" rx="6" fill="none" stroke="{t["border"]}"/>',
    ]
    last = -9
    for wi, w in enumerate(weeks):
        label = None
        if wi == 0:
            d0 = dt.date.fromisoformat(w[0]["date"])
            if d0.day <= 14:
                label = d0.month
        else:
            for d in w:
                dd = dt.date.fromisoformat(d["date"])
                if dd.day == 1:
                    label = dd.month
        if label and wi - last >= 3 and wi < len(weeks) - 1:
            o.append(f'<text x="{left + wi * pitch}" y="{top - 8}" font-size="12" fill="{t["fg"]}">{MONTHS[label - 1]}</text>')
            last = wi
    for row, name in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        o.append(f'<text x="{left - 32}" y="{top + row * pitch + 9}" font-size="12" fill="{t["fg"]}">{name}</text>')
    for wi, w in enumerate(weeks):
        for d in w:
            x, y = left + wi * pitch, top + int(d["weekday"]) * pitch
            o.append(f'<rect x="{x + 0.5}" y="{y + 0.5}" width="{cell - 1}" height="{cell - 1}" rx="2" '
                     f'fill="{t["c"][int(d["level"])]}" stroke="{t["ring"]}"/>')
    fy = top + 7 * pitch - 3 + 22
    o.append(f'<path d="{star(left - 28, fy - 4, 5)}" fill="{t["muted"]}"/>')
    o.append(f'<text x="{left - 19}" y="{fy}" font-size="12" fill="{t["muted"]}">Click the graph to fall into the star sea</text>')
    lx = width - 16 - 30
    o.append(f'<text x="{width - 16}" y="{fy}" font-size="12" fill="{t["muted"]}" text-anchor="end">More</text>')
    for k in range(4, -1, -1):
        x = lx - 6 - (4 - k) * 13 - cell
        o.append(f'<rect x="{x + 0.5}" y="{fy - 9.5}" width="{cell - 1}" height="{cell - 1}" rx="2" fill="{t["c"][k]}" stroke="{t["ring"]}"/>')
    o.append(f'<text x="{lx - 6 - 5 * 13 - 4}" y="{fy}" font-size="12" fill="{t["muted"]}" text-anchor="end">Less</text>')
    o.append("</g></svg>")
    return "\n".join(o)


def write_svgs(data):
    os.makedirs(SVG_DIR, exist_ok=True)
    for theme in THEMES:
        with open(os.path.join(SVG_DIR, f"contrib-{theme}.svg"), "w", encoding="utf-8") as fh:
            fh.write(render(data, theme))


def main():
    if "--render-only" in sys.argv:
        with open(JSON_PATH, encoding="utf-8") as fh:
            write_svgs(json.load(fh))
        print("redrew SVGs from", JSON_PATH)
        return
    if len(sys.argv) < 2:
        sys.exit("usage: contributions.py <login> | --render-only")
    login, token = sys.argv[1], os.environ.get("GH_TOKEN", "")
    try:
        data = fetch(login, token)
    except Exception as e:  # keep yesterday's files rather than failing the whole workflow
        print(f"::warning::could not fetch contributions: {e}")
        return
    os.makedirs(os.path.dirname(JSON_PATH), exist_ok=True)
    with open(JSON_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, separators=(",", ":"))
    write_svgs(data)
    print(f"{data['total']} contributions, {len(data['weeks'])} weeks")


if __name__ == "__main__":
    main()
