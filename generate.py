#!/usr/bin/env python3
"""Builds assets/hello.svg, the animated terminal shown on the GitHub profile.

Edit the settings below, then run:  python3 generate.py
No dependencies. The SVG loops forever using SMIL animation, which GitHub
plays when the file is embedded in a README with <img>.
"""

import random
from pathlib import Path

# --- Settings -------------------------------------------------------------

USER = "mateusz"
HOST = "github"
COLS = 56        # terminal width in characters
REPOS = ["cosmic-clocks", "gym-tracker-pokemon-game",
         "odoo-process-xray", "shopify-odoo-connector"]


def plain(*lines):
    return [[(line, "text")] for line in lines]


def ls(names):
    """Column-major layout like `ls`, using the fewest rows that fit."""
    for nrows in range(1, len(names) + 1):
        cols = [names[i:i + nrows] for i in range(0, len(names), nrows)]
        widths = [max(map(len, c)) + 2 for c in cols]
        if sum(widths) - 2 <= COLS:
            return [[(c[r].ljust(w), "dir") for c, w in zip(cols, widths)
                     if r < len(c)] for r in range(nrows)]


# (command, output lines); each line is a list of (text, colour) pieces.
SESSION = [
    ("whoami", plain(USER)),
    ("cat hello.txt", plain("hey. not much going on here.",
                            "go check out my repos instead ↓")),
    ("ls ~/repos", ls(REPOS)),
]
# How long the finished screen stays up before `clear` restarts the loop.
READ_TIME = 7.0

COLORS = {
    "bg": "#0d1117", "border": "#30363d", "muted": "#7d8590",
    "text": "#c9d1d9", "user": "#7ee787", "path": "#79c0ff",
    "dir": "#79c0ff", "cursor": "#c9d1d9",
}

# --- Layout ---------------------------------------------------------------

FONT = ("SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',"
        "'Liberation Mono',monospace")
FS = 15          # font size
CW = 9           # width of one character cell
LH = 25          # line height
GAP = 16         # extra space between one command's output and the next prompt
PAD = 28
WIDTH = PAD * 2 + COLS * CW

rng = random.Random(7)


def keystroke():
    return rng.uniform(0.06, 0.13)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def cx(col):
    return PAD + col * CW


def text(y, col, s, fill, bold=False):
    # One x per character keeps every glyph on the grid whatever font the
    # viewer ends up with.
    xs = " ".join(f"{cx(col + i):g}" for i in range(len(s)))
    weight = ' font-weight="600"' if bold else ""
    return (f'<text x="{xs}" y="{y:g}" fill="{fill}"{weight} '
            f'xml:space="preserve">{esc(s)}</text>')


def discrete(attr, events, dur):
    """[(time, value)] -> an <animate> that steps through the values and
    repeats every `dur` seconds, so everything in the scene stays in sync."""
    points = {}
    for t, v in sorted(events, key=lambda e: e[0]):
        points[round(t / dur, 5)] = v
    keys = sorted(points)
    assert keys[0] == 0, "events must start at t=0"
    if keys[-1] != 1:
        points[1] = points[keys[-1]]
        keys.append(1)
    return (f'<animate attributeName="{attr}" dur="{dur:.3f}s" '
            f'repeatCount="indefinite" calcMode="discrete" '
            f'keyTimes="{";".join(f"{k:g}" for k in keys)}" '
            f'values="{";".join(str(points[k]) for k in keys)}"/>')


class Scene:
    def __init__(self):
        self.items = []     # (appear_time, svg)
        self.cursors = []

    def add(self, t, svg):
        self.items.append((t, svg))

    def command(self, y, cmd, appear, idle):
        """A prompt that sits for `idle` seconds, then types `cmd`.
        Returns the moment Enter is pressed."""
        col, parts = 0, []
        for s, color, bold in [(f"{USER}@{HOST}", "user", True),
                               (":", "muted", False), ("~", "path", False),
                               ("$ ", "muted", False)]:
            parts.append(text(y, col, s, COLORS[color], bold))
            col += len(s)
        self.add(appear, "".join(parts))
        t = start = appear + idle
        moves = []
        for i, ch in enumerate(cmd):
            self.add(t, text(y, col + i, ch, COLORS["text"]))
            moves.append((t, col + i + 1))
            t += keystroke()
        enter = t + 0.35
        self.cursors.append(dict(y=y, col=col, appear=appear, start=start,
                                 moves=moves, enter=enter))
        return enter


def cursor(c, dur):
    """Blinks while the prompt is idle, then stays solid and follows the
    typing. Hidden once Enter is pressed."""
    shown = [(0, 0)]
    t, on = c["appear"], 1
    while t < c["start"] - 1e-6:
        shown.append((t, on))
        t, on = t + 0.5, 1 - on
    shown.append((c["start"], 1))
    if c["enter"] < dur - 1e-6:
        shown.append((c["enter"], 0))
    moves = [(0, c["col"])] + c["moves"]
    return (f'<rect x="{cx(c["col"])}" y="{c["y"] - 13:g}" width="{CW - 0.5:g}" '
            f'height="17" fill="{COLORS["cursor"]}" opacity="0">'
            f'{discrete("opacity", shown, dur)}'
            f'{discrete("x", [(t, cx(col)) for t, col in moves], dur)}</rect>')


def build():
    s = Scene()
    y = PAD + 16
    t = 0.0
    idle = 1.0
    for cmd, output in SESSION:
        t = s.command(y, cmd, t, idle)
        for line in output:
            y += LH
            col, parts = 0, []
            for piece, color in line:
                parts.append(text(y, col, piece.rstrip(), COLORS[color],
                                  bold=color == "dir"))
                col += len(piece)
            s.add(t + 0.05, "".join(parts))
        y += LH + GAP
        t += 0.1
        idle = 0.6

    # an idle prompt, then `clear`: Enter restarts the loop
    dur = s.command(y, "clear", t, READ_TIME)

    body = []
    for appear, svg in s.items:
        if appear <= 0:
            body.append(svg)
        else:
            anim = discrete("opacity", [(0, 0), (appear, 1)], dur)
            body.append(f'<g opacity="0">{anim}{svg}</g>')
    body += [cursor(c, dur) for c in s.cursors]
    return render(body, y + PAD - 2)


def render(body, h):
    w = WIDTH
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h:g}" width="{w}" height="{h:g}" font-family="{FONT}" font-size="{FS}">
<title>hey, i'm {esc(USER)}. not much going on here, go check out my repos instead.</title>
<rect x=".5" y=".5" width="{w - 1}" height="{h - 1:g}" rx="8" fill="{COLORS["bg"]}" stroke="{COLORS["border"]}"/>
{chr(10).join(body)}
</svg>
"""


if __name__ == "__main__":
    out = Path(__file__).with_name("assets") / "hello.svg"
    out.parent.mkdir(exist_ok=True)
    out.write_text(build(), encoding="utf-8")
    print(f"wrote {out}")
