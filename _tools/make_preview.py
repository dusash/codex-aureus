# -*- coding: utf-8 -*-
"""生成用于无头截图的分段预览副本：直接隐藏目标之前的区块（比滚动更稳）"""
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(BASE, "index.html")
OUT = os.path.join(BASE, "_tools", "preview")
os.makedirs(OUT, exist_ok=True)

html = open(SRC, encoding="utf-8").read()

STEPS = [
    ("top",       []),
    ("prologue",  [".hero"]),
    ("relics",    [".hero", "#prologue"]),
    ("chronicle", [".hero", "#prologue", "#relics"]),
    ("band",      [".hero", "#prologue", "#relics", "#chronicle"]),
    ("colophon",  [".hero", "#prologue", "#relics", "#chronicle", ".band"]),
    ("shelf",     [".hero", "#prologue", "#relics", "#chronicle", ".band", "#colophon"]),
]

BASEURL = "file:///" + BASE.replace("\\", "/") + "/"

for name, hides in STEPS:
    css = "".join("%s{display:none !important}" % s for s in hides)
    inject = (
        "<style id='__shot'>html{scroll-behavior:auto !important;}"
        ".reveal{opacity:1 !important;transform:none !important;}"
        "*{animation-duration:.001s !important;transition:none !important;}"
        + css + "</style>\n</body>"
    )
    p = os.path.join(OUT, "preview-%s.html" % name)
    doc = html.replace("<head>", "<head>\n<base href='%s'>" % BASEURL, 1)
    doc = doc.replace("</body>", inject)
    open(p, "w", encoding="utf-8").write(doc)
    print("->", name)
