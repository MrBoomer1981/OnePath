"""Draw Тропыч, OnePath's mascot, as a graffiti piece: static/mascot/hello.svg and sleep.svg.

    uv run dev/mascot.py    # after a change here; app.css animates the classes the drawings carry (w-*)

Тропыч is the walker of the picture OnePath's colors come from (a man in a hat stepping out of a lit door into a
storm), painted the way a wall piece is: the parts filled flat, a dark outline around and between them, a 3D block
to the lower right in the storm's slate, and a light outer line around it all; then fades with bubbles, shines,
drips and overspray. No face, only glasses glowing with the doorway's light and a handlebar moustache.

The outline layers repeat the silhouette with <use>: a part's shape is written once, in <defs>. Its ids carry the
pose (w-hello-…, w-sleep-…), so both poses can share a page; the same pose twice draws the same shapes.
"""

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "static" / "mascot"

NIGHT, PAPER, WHITE = "#111B20", "#E6ECEF", "#FFFFFF"  # app.css: --night, --paper, --graffiti
WINE, WINE_D, WINE_L = "#6E3F46", "#4D2B31", "#8A525B"  # --bordo, --bordo-dark, a lit bordo
LAMP, STEEL, STEEL_L, SLATE = "#F4DE90", "#8FA3B3", "#B2C1CE", "#4B6673"  # --amber; the icon's door and storm
VOID, LEG = "#0B1316", "#22343C"


def star(x, y, r, fill=WHITE, cls=""):
    """A four-point shine."""
    k = r * .28
    c = f' class="{cls}"' if cls else ""
    return (f'<path{c} d="M{x} {y - r} Q{x + k} {y - k} {x + r} {y} Q{x + k} {y + k} {x} {y + r} '
            f'Q{x - k} {y + k} {x - r} {y} Q{x - k} {y - k} {x} {y - r} Z" fill="{fill}"/>')


def dots(spec, fill, cls=""):
    c = f' class="{cls}"' if cls else ""
    return f'<g{c} fill="{fill}">' + "".join(f'<circle cx="{x}" cy="{y}" r="{r}"/>' for x, y, r in spec) + "</g>"


def ellipse(cx, cy, rx, ry):
    return f"M{cx - rx} {cy} a{rx} {ry} 0 1 0 {2 * rx} 0 a{rx} {ry} 0 1 0 {-2 * rx} 0 Z"


def _lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def split(c, t):
    """A cubic Bézier (four points) split at t into two."""
    p0, p1, p2, p3 = c
    q0, q1, q2 = _lerp(p0, p1, t), _lerp(p1, p2, t), _lerp(p2, p3, t)
    r0, r1 = _lerp(q0, q1, t), _lerp(q1, q2, t)
    mid = _lerp(r0, r1, t)
    return (p0, q0, r0, mid), (mid, r1, q2, p3)


def at_y(c, y):
    """The t where a cubic that only goes up or only goes down reaches y."""
    lo, hi = 0.0, 1.0
    y_of = lambda t: split(c, t)[0][3][1]
    down = y_of(1) > y_of(0)
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if (y_of(mid) < y) == down else (lo, mid)
    return (lo + hi) / 2


def fade(left, bottom, right, y, wave, fill):
    """A graffiti fill's second color: the part of a shape below y, under a wavy line. left and right are the
    shape's side curves, top to bottom; bottom the curve between their lower ends, left to right."""
    _, low_l = split(left, at_y(left, y))
    _, low_r = split(right, at_y(right, y))
    a, b = low_l[0], low_r[0]
    w = (b[0] - a[0]) / 4
    pts = lambda c: " ".join(f"{x:.1f} {y:.1f}" for x, y in c[1:])
    d = (f"M{a[0]:.1f} {a[1]:.1f} C{pts(low_l)} C{pts(bottom)} C{pts(low_r[::-1])} "
         f"C{b[0] - w:.1f} {b[1] - wave:.1f} {b[0] - w:.1f} {b[1] + wave:.1f} {(a[0] + b[0]) / 2:.1f} {(a[1] + b[1]) / 2:.1f} "
         f"C{a[0] + w:.1f} {a[1] - wave:.1f} {a[0] + w:.1f} {a[1] + wave:.1f} {a[0]:.1f} {a[1]:.1f} Z")
    return f'<path d="{d}" fill="{fill}"/>'


def bubble_z(x, y, size, cls=""):
    """A bubble-letter Z: the light outer line, the dark outline, the fill, as three strokes of one line."""
    d = f"M{x} {y} L{x + size} {y} L{x} {y + size} L{x + size} {y + size}"
    k = size / 16
    return (f'<g class="{cls}" fill="none" stroke-linecap="round" stroke-linejoin="round">'
            + "".join(f'<path d="{d}" stroke="{color}" stroke-width="{w * k:.2f}"/>'
                      for color, w in ((PAPER, 11), (NIGHT, 7.5), (LAMP, 3.6))) + "</g>")


def piece(prefix, parts, depth=5):
    """Parts (name, path, fill, attributes[, what is painted over it]) as a graffiti piece: (defs, painting)."""
    parts = [p if len(p) == 5 else (*p, "") for p in parts]
    sil = f"#{prefix}-sil"
    defs = f'<g id="{prefix}-sil">' + "".join(f'<path id="{prefix}-{n}" d="{d}"{a}/>' for n, d, _, a, _ in parts) + "</g>"
    layers = (  # the light outer line, the dark outline of the figure and of its 3D block, the block
        (PAPER, 13, (0, depth / 2, depth)), (NIGHT, 7, (0, depth / 2, depth)), (SLATE, 1.5, (depth * .4, depth * .7, depth)))
    out = "".join(f'<g fill="{color}" stroke="{color}" stroke-width="{width}" stroke-linejoin="round">'
                  + "".join(f'<use href="{sil}" x="{s}" y="{s}"/>' for s in steps) + "</g>"
                  for color, width, steps in layers)
    outline = f'stroke="{NIGHT}" stroke-width="3" stroke-linejoin="round"'
    for n, _, fill, _, over in parts:
        out += f'<use href="#{prefix}-{n}" fill="{fill}" {outline}/>'
        if over:  # a fade or bubbles inside the part, then its outline again on top
            out += over + f'<use href="#{prefix}-{n}" fill="none" {outline}/>'
    return defs, out


def hello():
    """On the sign-in screen: Тропыч tips his hat, a spray can in the other hand; the path he painted underfoot."""
    hat = ' transform="translate(0 -3) rotate(8 84 58)"'
    coat = (((58, 98), (50, 114), (46, 134), (44, 152)), ((44, 152), (62, 158), (106, 158), (124, 152)),
            ((110, 98), (118, 114), (122, 134), (124, 152)))
    crown = (((66, 19), (57, 23), (53, 38), (56, 54)), ((56, 54), (74.7, 53.3), (93.3, 52.7), (112, 52)),
             ((106, 16), (113, 19), (115, 36), (112, 52)))
    parts = [
        ("leg-l", "M64 150 L64 168 L77 168 L77 150 Z", LEG, ""),
        ("leg-r", "M92 150 L92 168 L105 168 L105 150 Z", LEG, ""),
        ("shoe-l", "M44 177 C42 169 50 163 61 163 L77 164 C80 168 80 174 79 179 L48 181 C45 181 44 179 44 177 Z", PAPER, ""),
        ("shoe-r", "M91 164 L106 163 C118 162 126 167 127 174 C128 179 124 181 120 181 L92 181 C89 177 89 169 91 164 Z", PAPER, ""),
        ("drip-1", "M46 152 L46 159 C46 163 52 163 52 159 L52 152 Z", WINE, ""),
        ("drip-2", "M81 154 L81 163 C81 167 87 167 87 163 L87 154 Z", WINE, ""),
        ("drip-3", "M113 153 L113 159 C113 162.5 119 162.5 119 159 L119 153 Z", WINE, ""),
        ("coat", "M58 98 C50 114 46 134 44 152 C62 158 106 158 124 152 C122 134 118 114 110 98 C98 94 70 94 58 98 Z", WINE, "",
         fade(*coat, 130, 4, WINE_D)
         + dots([(58, 137, 2.3), (66, 141, 1.4), (101, 138, 2), (110, 142, 1.3), (80, 146, 1)], WINE)
         + dots([(64, 123, 1.7), (99, 122, 1.4), (110, 120, 1)], WINE_D)),
        ("can", "M133 86 L133 118 Q133 122 137 122 L145 122 Q149 122 149 118 L149 86 Z", LAMP, ""),
        ("cap", "M134 86 C134 78 148 78 148 86 Z", WINE, ""),
        ("nozzle", "M146 77.5 L153 75.5 L153 80.5 L146 81.5 Z", NIGHT, ""),
        ("arm-r", "M106 100 C118 103 128 108 136 110 L134 124 C124 122 114 118 104 114 Z", WINE, ""),
        ("glove-r", "M132 114 C132 108 137 106 141 107 C146 108 149 112 148 117 C147 121 142 123 138 122 "
                    "C134 121 132 118 132 114 Z", PAPER, ""),
        ("arm-l-up", "M62 98 C52 100 40 104 33 108 C28 111 29 119 36 118 C44 117 54 114 62 112 Z", WINE, ""),
        ("arm-l", "M28 112 C26 96 28 78 32 62 L45 64 C41 80 40 96 41 112 Z", WINE, ""),
        ("face", "M59 52 C58 84 70 101 84 101 C98 101 110 84 109 52 Z", VOID, ""),
        ("collar", "M54 110 C53 100 55 91 59 83 L78 101 L84 104 L90 101 L109 83 C113 91 115 100 114 110 Z", WINE_L, ""),
        ("crown", "M56 54 C53 38 57 23 66 19 C74 16 80 24 86 23 C92 22 98 14 106 16 C113 19 115 36 112 52 Z", STEEL_L, hat,
         f"<g{hat}>" + fade(*crown, 34, 3, STEEL) + dots([(70, 37, 1.6), (99, 38, 1.3)], STEEL_L)
         + dots([(76, 29, 1.3)], STEEL) + "</g>"),
        ("band", "M56 44 C74 47 94 46 112 42 L112 51 C94 55 74 56 56 53 Z", WINE, hat),
        ("brim", "M30 58 C40 49 60 51 84 51 C108 51 128 46 138 53 C130 63 106 63 84 63 C62 63 40 66 30 58 Z", STEEL, hat),
        ("brim-drip-1", "M116 60 L116 72 C116 76.5 122.5 76.5 122.5 72 L122.5 60 Z", STEEL, hat),
        ("brim-drip-2", "M127 57 L127 64 C127 67.5 132 67.5 132 64 L132 57 Z", STEEL, hat),
        ("glove-l", "M30 56 C29 50 34 46 39 46 C45 46 48 50 47 56 C46 61 42 63 37 63 C33 62 30 60 30 56 Z", PAPER, ""),
    ]
    defs, body = piece("w-hello", parts)
    details = (
        # the coat's seam and buttons, a shine on its lit side
        f'<path d="M86 96 L88 155" stroke="{NIGHT}" stroke-width="2" fill="none"/>'
        f'<g fill="{LAMP}" stroke="{NIGHT}" stroke-width="1.5"><circle cx="93" cy="113" r="2.6"/><circle cx="95" cy="141" r="2.6"/></g>'
        f'<path d="M53 124 C51 132 49 140 48 148" stroke="{WHITE}" stroke-width="2.2" stroke-linecap="round" fill="none"/>'
        f'<circle cx="55" cy="119" r="1.6" fill="{WHITE}"/>'
        # the hat: its crease, a shine on the crown, a lit edge on the brim
        f'<g{hat}><path d="M84 24 C84 30 85 36 86 42" stroke="{NIGHT}" stroke-width="1.6" fill="none"/>'
        f'<path d="M63 29 C61 35 61 41 62 47" stroke="{WHITE}" stroke-width="2.2" stroke-linecap="round" fill="none"/>'
        f'<path d="M48 55 C58 52.5 70 52.5 80 52.5" stroke="{STEEL_L}" stroke-width="1.8" stroke-linecap="round" fill="none"/></g>'
        # the glasses glowing in the void, the moustache
        f'<g fill="{LAMP}" opacity=".18"><circle cx="74" cy="71" r="12.5"/><circle cx="95" cy="71" r="12.5"/></g>'
        f'<g fill="{LAMP}" stroke="{NIGHT}" stroke-width="2.6"><circle cx="74" cy="71" r="8.5"/><circle cx="95" cy="71" r="8.5"/></g>'
        f'<path d="M82.5 70 Q84.5 67.5 86.5 70" stroke="{NIGHT}" stroke-width="2.2" fill="none"/>'
        f'<g class="w-glint" stroke="{WHITE}" stroke-width="1.8" stroke-linecap="round" fill="none">'
        f'<path d="M69 68 A5.5 5.5 0 0 1 73 65.2"/><path d="M90 68 A5.5 5.5 0 0 1 94 65.2"/></g>'
        f'<path d="M84.5 84 C80 79.5 72 79.5 68 84.5 C66 87.5 62 88 60 85 C61 90.5 68 91.5 73 88.5 C77 86.5 81 86.5 84.5 87.5 '
        f'C88 86.5 92 86.5 96 88.5 C101 91.5 108 90.5 109 85 C107 88 103 87.5 101 84.5 C97 79.5 89 79.5 84.5 84 Z" '
        f'fill="{PAPER}" stroke="{NIGHT}" stroke-width="1.8" stroke-linejoin="round"/>'
        # the sneakers: soles, swooshes, laces
        f'<g stroke-linecap="round" fill="none"><path d="M47 177.5 L78 176.2" stroke="{STEEL}" stroke-width="2.6"/>'
        f'<path d="M93 177.5 L125 176.5" stroke="{STEEL}" stroke-width="2.6"/>'
        f'<path d="M55 171 C62 174 70 172 75 168" stroke="{WINE}" stroke-width="2.2"/>'
        f'<path d="M97 171 C104 174 113 173 121 169" stroke="{WINE}" stroke-width="2.2"/>'
        f'<path d="M66 165.5 L70 168.5 M70 164.5 L74 167.5 M96 165.5 L100 168.5 M100 164.5 L104 167.5" '
        f'stroke="{NIGHT}" stroke-width="1.4"/></g>'
        # the can's label and shine
        f'<path d="M133.8 97 L148.2 97 L148.2 104 L133.8 104 Z" fill="{WINE}"/>'
        f'<path d="M137 89 L137 112" stroke="{WHITE}" stroke-width="2" stroke-linecap="round"/>'
        + star(105, 13, 5.5, cls="w-star") + star(57, 128, 3.2)
        + dots([(22, 64, .9), (19, 92, .7), (24, 120, 1.1), (130, 40, .8), (142, 46, .6), (118, 8, .8), (44, 20, .7),
                (36, 150, .8), (132, 150, 1), (139, 138, .6), (28, 172, .7)], PAPER)
    )
    spray = (dots([(158, 75, 2.2), (163, 72, 1.8), (160, 81, 1.6), (168, 69, 1.4), (167, 78, 1.3), (173, 74, 1.1),
                   (175, 66, .9), (178, 82, .8), (182, 71, .7), (172, 85, .7), (185, 77, .6)], LAMP, "w-spray")
             + dots([(165, 75, .8), (171, 79, .6), (179, 68, .6), (184, 84, .5)], WHITE, "w-spray"))
    line, head = "M6 190 C40 182 72 194 106 188 S156 181 176 186", "M171 175.5 L195 187 L171 198.5 Z"
    path = (  # the arrow he sprayed: three strokes of one line, as the Zs; app.css draws it anew in a loop
        '<g class="w-path" fill="none" stroke-linecap="round" stroke-linejoin="round">'
        + "".join(f'<path class="w-stroke" d="{line}" stroke="{c}" stroke-width="{w}"/>'
                  for c, w in ((PAPER, 15), (NIGHT, 10), (LAMP, 5.5)))
        + f'<path class="w-stroke" d="M24 186.6 C40 183.4 52 184.6 62 186.2" stroke="{WHITE}" stroke-width="1.6"/>'
        + '<g class="w-head">'
        + "".join(f'<path d="{head}" fill="{c}" stroke="{c}" stroke-width="{w}"/>' for c, w in ((PAPER, 9), (NIGHT, 4.5)))
        + f'<path d="M174.5 182 L187.5 187 L174.5 192.5 Z" fill="{LAMP}"/></g></g>'
    )
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200" role="img" '
            f'aria-label="Тропыч приподнимает шляпу" class="walker walker--hello">'
            f'<defs>{defs}</defs>{path}<g class="w-body">{body}{details}</g>{spray}</svg>')


def sleep():
    """In an empty list: Тропыч asleep on the ground till the morning's update, his hat over his glasses."""
    hat = ' transform="rotate(5 88 76)"'
    coat = (((58, 104), (48, 120), (44, 140), (44, 156)), ((44, 156), (64, 162), (112, 162), (132, 156)),
            ((118, 104), (128, 120), (132, 140), (132, 156)))
    crown = (((70, 39), (61, 43), (57, 58), (60, 74)), ((60, 74), (78.7, 73.3), (97.3, 72.7), (116, 72)),
             ((110, 36), (117, 39), (119, 56), (116, 72)))
    sole = lambda cx, a: f' transform="rotate({a} {cx} 160)"'
    parts = [
        ("leg-l", "M60 144 L52 160 L74 164 L80 150 Z", LEG, ""),
        ("leg-r", "M98 150 L104 164 L126 160 L118 144 Z", LEG, ""),
        ("coat", "M58 104 C48 120 44 140 44 156 C64 162 112 162 132 156 C132 140 128 120 118 104 C106 100 70 100 58 104 Z",
         WINE, "", fade(*coat, 134, 4, WINE_D) + dots([(56, 141, 2.2), (66, 145, 1.3), (110, 142, 2), (120, 146, 1.2)], WINE)
         + dots([(64, 128, 1.5), (114, 128, 1.3)], WINE_D)),
        ("face", "M63 64 C62 92 74 108 88 108 C102 108 114 92 113 64 Z", VOID, ""),
        ("collar", "M58 114 C57 104 59 96 63 90 L82 108 L88 111 L94 108 L113 90 C117 96 119 104 118 114 Z", WINE_L, ""),
        ("arms", "M50 120 C50 113 58 110 68 112 L108 112 C118 110 126 113 126 120 C126 127 118 131 108 129 L68 129 "
                 "C58 131 50 127 50 120 Z", WINE, ""),
        ("glove-l", ellipse(56, 121, 6.5, 6), PAPER, ""),
        ("glove-r", ellipse(120, 121, 6.5, 6), PAPER, ""),
        ("crown", "M60 74 C57 58 61 43 70 39 C78 36 84 44 90 43 C96 42 102 34 110 36 C117 39 119 56 116 72 Z", STEEL_L, hat,
         f"<g{hat}>" + fade(*crown, 55, 3, STEEL) + dots([(74, 56, 1.5), (104, 57, 1.3)], STEEL_L)
         + dots([(80, 50, 1.2)], STEEL) + "</g>"),
        ("band", "M60 64 C78 67 98 66 116 62 L116 71 C98 75 78 76 60 73 Z", WINE, hat),
        ("brim", "M30 78 C42 70 64 72 88 72 C112 72 134 67 146 74 C140 86 114 88 88 88 C62 88 38 90 30 78 Z", STEEL, hat),
        ("brim-drip", "M126 82 L126 92 C126 96.5 132.5 96.5 132.5 92 L132.5 82 Z", STEEL, hat),
        ("sole-l", ellipse(60, 160, 15, 19), PAPER, sole(60, -14)),
        ("sole-r", ellipse(118, 160, 15, 19), PAPER, sole(118, 14)),
        ("can", "M80 168 L100 168 Q103 168 103 171 L103 175 Q103 178 100 178 L80 178 Q77 178 77 175 L77 171 Q77 168 80 168 Z",
         LAMP, ""),
        ("cap", "M103 169 C109.5 169 109.5 177 103 177 Z", WINE, ""),
    ]
    defs, body = piece("w-sleep", parts)
    tread = lambda cx, a: (f'<g{sole(cx, a)}><path d="{ellipse(cx, 160, 10, 14)}" fill="{STEEL}"/>'
                           f'<path d="M{cx - 8} 153 L{cx + 8} 153 M{cx - 9.5} 159 L{cx + 9.5} 159 M{cx - 9} 165 L{cx + 9} 165 '
                           f'M{cx - 6} 170.5 L{cx + 6} 170.5" stroke="{NIGHT}" stroke-width="1.6" stroke-linecap="round"/>'
                           f'<circle cx="{cx}" cy="147.5" r="1.8" fill="{WINE}"/></g>')
    details = (
        f'<path d="M88 108 L89 112 M89 129 L90 158" stroke="{NIGHT}" stroke-width="2" fill="none"/>'
        f'<circle cx="95" cy="140" r="2.4" fill="{LAMP}" stroke="{NIGHT}" stroke-width="1.5"/>'
        f'<path d="M50 134 C48 140 47 146 47 151" stroke="{WHITE}" stroke-width="2.2" stroke-linecap="round" fill="none"/>'
        f'<path d="M60 116 C70 114 90 114.5 106 114.5" stroke="{WINE_L}" stroke-width="2" stroke-linecap="round" fill="none"/>'
        f'<g{hat}><path d="M88 44 C88 50 89 56 90 62" stroke="{NIGHT}" stroke-width="1.6" fill="none"/>'
        f'<path d="M67 49 C65 54 65 60 66 66" stroke="{WHITE}" stroke-width="2.2" stroke-linecap="round" fill="none"/>'
        f'<path d="M50 77 C62 74.5 74 74.5 84 74.5" stroke="{STEEL_L}" stroke-width="1.8" stroke-linecap="round" fill="none"/></g>'
        # asleep behind the glasses: closed eyes in the lit lenses
        f'<g fill="{LAMP}" stroke="{NIGHT}" stroke-width="2.6"><circle cx="78" cy="88" r="8"/><circle cx="98" cy="88" r="8"/></g>'
        f'<g fill="none" stroke="{NIGHT}" stroke-width="1.7" stroke-linecap="round"><path d="M73.5 90.5 Q78 93.5 82.5 90.5"/>'
        f'<path d="M93.5 90.5 Q98 93.5 102.5 90.5"/><path d="M86.5 88 Q88 86.5 89.5 88"/></g>'
        f'<g transform="translate(3.5 15.5)"><path class="w-stache" d="M84.5 84 C80 79.5 72 79.5 68 84.5 C66 87.5 62 89 60 87 '
        f'C61 92.5 68 92.5 73 89 C77 86.5 81 86.5 84.5 87.5 C88 86.5 92 86.5 96 89 C101 92.5 108 92.5 109 87 C107 89 103 87.5 '
        f'101 84.5 C97 79.5 89 79.5 84.5 84 Z" fill="{PAPER}" stroke="{NIGHT}" stroke-width="1.8" stroke-linejoin="round"/></g>'
        + tread(60, -14) + tread(118, 14)
        + f'<path d="M84 168.8 L89 168.8 L89 177.2 L84 177.2 Z" fill="{WINE}"/>'
        f'<path d="M80 170.6 L99 170.6" stroke="{WHITE}" stroke-width="1.6" stroke-linecap="round"/>'
        + star(112, 34, 5, cls="w-star") + star(42, 132, 3)
        + dots([(24, 84, .9), (20, 112, .7), (28, 146, 1), (150, 96, .8), (142, 84, .6), (36, 52, .8), (156, 132, .7)], PAPER)
    )
    zzz = bubble_z(130, 46, 15, "w-z") + bubble_z(152, 26, 11, "w-z w-z2") + bubble_z(170, 10, 8, "w-z w-z3")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 190" width="200" height="190" role="img" '
            f'aria-label="Тропыч спит" class="walker walker--sleep">'
            f'<defs>{defs}</defs><g class="w-body">{body}{details}</g>{zzz}</svg>')


if __name__ == "__main__":
    for name, draw in (("hello", hello), ("sleep", sleep)):
        (OUT / f"{name}.svg").write_text(draw() + "\n", "utf-8")
        print(f"static/mascot/{name}.svg")
