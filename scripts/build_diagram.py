"""Regenerate the README architecture diagram.

GitHub renders neither inline SVG nor `currentColor` in a README, so the diagram
ships as two standalone files behind a <picture> element. Both come from the one
layout below, so the light and dark copies cannot drift apart.

Every colour is explicit rather than an `opacity` on an inherited fill: SVG served
as an <img> is rendered by whatever the host uses, and opacity is the first thing a
weaker rasteriser drops.

Run:  python scripts/build_diagram.py
"""

from __future__ import annotations

import sys
from pathlib import Path

W, H = 1080, 980
COL_X, COL_W = 280, 320          # main column
COL_R = COL_X + COL_W            # 600
COL_C = COL_X + COL_W // 2       # 440
RAIL_X = 210                     # feedback rail, left margin
LANE_X, LANE_W = 700, 340        # provider lane
LANE_R = LANE_X + LANE_W         # 1040
LANE_RAIL = 650                  # where the provider arrows turn

ALT = (
    "Blindspot pipeline. A seed corpus feeds a mutator, the mutant runs against the "
    "target agent, and the run is hashed into a behaviour signature; a novel signature "
    "sends the input back to the corpus as a new seed. The run then passes through four "
    "oracles: crash, schema, metamorphic and judge. Findings are clustered and ranked, "
    "shrunk by delta debugging, and emitted as a pytest file and as one Agent Orchestrator "
    "worker per failure class. An optional LLM provider lane touches only two points, "
    "semantic mutation and the judge oracle."
)

THEMES = {
    "light": dict(ground="#ffffff", ink="#131820", muted="#5a6472",
                  line="#2c343f", row="#f1f3f6", accent="#a8620c"),
    "dark": dict(ground="#161b24", ink="#e5e9ef", muted="#99a3b1",
                 line="#c3cad4", row="#1f2632", accent="#e0a343"),
}

MONO = "IBM Plex Mono, ui-monospace, SFMono-Regular, Menlo, monospace"

# y, height, title, subtitle
STEPS = [
    (76, 58, "Seed corpus", "round-robin, dedup by signature"),
    (174, 58, "Mutator", "7 answer-preserving ops, 2 destructive"),
    (272, 58, "Target agent", "spec.entrypoint, SIGALRM hang guard"),
    (370, 58, "Behaviour signature", "SHA-1 of tool shapes, terminal, retries"),
]
TAIL = [
    (676, 58, "Cluster and rank", "group by (oracle, signature), score"),
    (774, 58, "Delta debugger", "ddmin, transform replayed each round"),
]
ORACLES = [
    (510, "crash", "error, timeout, retry loop", False),
    (537, "schema", "contract(output) is False", False),
    (564, "metamorphic", "GL 1100 to 6000 on a rename", False),
    (591, "judge", "budgeted, last resort", True),
]
# y of the label, text
EDGES = [(134, 170, "seed"), (232, 268, "mutant"), (330, 366, "AgentRun"),
         (428, 472, "run plus cached baseline"), (642, 672, "findings"),
         (734, 770, "ranked classes")]


def render(t: dict) -> str:
    o: list[str] = []
    add = o.append

    def text(x, y, s, size=11, fill=None, weight=None, anchor=None, spacing=None):
        a = f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill or t["ink"]}"'
        if weight:
            a += f' font-weight="{weight}"'
        if anchor:
            a += f' text-anchor="{anchor}"'
        if spacing:
            a += f' letter-spacing="{spacing}"'
        add(a + f">{s}</text>")

    def box(x, y, w, h, stroke=None, fill="none", dash=None):
        a = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="2" fill="{fill}" '
             f'stroke="{stroke or t["line"]}" stroke-width="1.2"')
        if dash:
            a += f' stroke-dasharray="{dash}"'
        add(a + "/>")

    def path(d, stroke=None, dash=None, arrow=True):
        a = (f'<path d="{d}" fill="none" stroke="{stroke or t["line"]}" '
             f'stroke-width="1.4"')
        if dash:
            a += f' stroke-dasharray="{dash}"'
        if arrow:
            a += f' marker-end="url(#{"ah-a" if stroke == t["accent"] else "ah"})"'
        add(a + "/>")

    add(f'<rect width="{W}" height="{H}" fill="{t["ground"]}"/>')
    add('<g font-family="' + MONO + '">')

    text(COL_X, 62, "DETERMINISTIC CRITICAL PATH", 11, t["muted"], spacing="1.4")
    text(LANE_X, 286, "OPTIONAL LLM LANE", 11, t["accent"], spacing="1.4")

    # feedback: signature back into the corpus, down the left margin
    path(f"M {COL_X} 399 L {RAIL_X} 399 L {RAIL_X} 105 L {COL_X - 4} 105",
         t["muted"], dash="5 4")
    for i, line in enumerate(("novel signature,", "keep this input", "as a new seed")):
        text(RAIL_X - 14, 236 + i * 16, line, 11, t["muted"], anchor="end")

    for y, h, title, sub in STEPS + TAIL:
        box(COL_X, y, COL_W, h)
        text(COL_X + 22, y + 25, title, 14.5, weight="600")
        text(COL_X + 22, y + 44, sub, 11, t["muted"])

    # oracle stack
    box(COL_X, 476, COL_W, 166)
    text(COL_X + 22, 501, "Oracle stack", 14.5, weight="600")
    for y, name, detail, is_judge in ORACLES:
        if is_judge:
            box(COL_X + 14, y, COL_W - 28, 24, t["accent"], dash="4 3")
        else:
            box(COL_X + 14, y, COL_W - 28, 24, t["row"], fill=t["row"])
        text(COL_X + 22, y + 16, name, 11.5, weight="600")
        text(COL_R - 22, y + 16, detail, 11.5, t["muted"], anchor="end")
    text(COL_X + 22, 630, "a deterministic oracle fires, the judge is skipped",
         10.5, t["muted"])

    # outputs
    for x, title, l1, l2 in ((COL_X, "pytest file", "one test per", "failure class"),
                             (COL_X + 168, "AO workers", "one fix PR per", "failure class")):
        box(x, 872, 152, 64)
        text(x + 14, 897, title, 13, weight="600")
        text(x + 14, 915, l1, 10.5, t["muted"])
        text(x + 14, 928, l2, 10.5, t["muted"])

    for y1, y2, label in EDGES:
        path(f"M {COL_C} {y1} L {COL_C} {y2}")
        text(COL_C + 12, (y1 + y2) // 2 + 4, label, 11.5, t["muted"])
    path(f"M {COL_C} 832 L {COL_C} 852 L {COL_X + 76} 852 L {COL_X + 76} 868")
    path(f"M {COL_C} 832 L {COL_C} 852 L {COL_X + 244} 852 L {COL_X + 244} 868")
    text(COL_C + 12, 846, "minimal repro", 11.5, t["muted"])

    # provider lane
    box(LANE_X, 300, LANE_W, 170, t["accent"], dash="5 4")
    text(LANE_X + 20, 330, "Provider table", 14.5, weight="600")
    text(LANE_X + 20, 349, "blindspot/llm.py, one row per API", 11, t["muted"])
    for y, name, model, note in (
        (382, "groq", "gpt-oss-20b / 120b", "priced, reports dollars"),
        (432, "tensormux", "glm-4-7-flash", "no published price, reports call count"),
    ):
        text(LANE_X + 20, y, name, 11.5, weight="600")
        text(LANE_R - 20, y, model, 11.5, t["muted"], anchor="end")
        text(LANE_X + 20, y + 22, note, 10.5, t["muted"])

    path(f"M {LANE_X} 340 L {LANE_RAIL} 340 L {LANE_RAIL} 203 L {COL_R + 4} 203",
         t["accent"], dash="5 4")
    text(LANE_RAIL, 195, "semantic mutation", 10, t["accent"], anchor="middle")
    path(f"M {LANE_X} 440 L {LANE_RAIL} 440 L {LANE_RAIL} 603 L {COL_R + 4} 603",
         t["accent"], dash="5 4")
    text(LANE_RAIL, 617, "judge verdict", 10, t["accent"], anchor="middle")

    text(LANE_X, 500, "Delete this lane and the loop still proves", 11.5, t["muted"])
    text(LANE_X, 518, "every crash, schema and metamorphic class.", 11.5, t["muted"])

    add("</g>")

    marker = ('<marker id="{i}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
              'markerHeight="7" orient="auto-start-reverse">'
              '<path d="M 0 0 L 10 5 L 0 10 z" fill="{f}"/></marker>')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}" height="{H}" role="img" aria-label="{ALT}">'
        f"<title>{ALT}</title>"
        f'<defs>{marker.format(i="ah", f=t["line"])}'
        f'{marker.format(i="ah-a", f=t["accent"])}</defs>'
        + "".join(o) + "</svg>\n"
    )


def main() -> int:
    if "--inline" in sys.argv:
        print(render(dict(THEMES["light"], ground="none", ink="currentColor",
                          muted="currentColor", line="currentColor")))
        return 0
    out = Path("docs")
    out.mkdir(exist_ok=True)
    for name, theme in THEMES.items():
        path = out / f"architecture-{name}.svg"
        path.write_text(render(theme))
        print(f"wrote {path}  ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
