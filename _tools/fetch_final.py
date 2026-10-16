# -*- coding: utf-8 -*-
"""下载最终素材（Pexels 授权 CC0 类）+ Google Fonts latin 子集，本地化到 assets/"""
import os, re, io, urllib.request, concurrent.futures as cf
from PIL import Image

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG  = os.path.join(BASE, "assets", "img")
FON  = os.path.join(BASE, "assets", "fonts")
os.makedirs(IMG, exist_ok=True); os.makedirs(FON, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# name -> (pexels id, target width, output quality, max height)
PICKS = {
    "parchment":   (16557322, 1800, 84, None),   # 泛黄羊皮纸/旧纸纹理
    "torn":        (38316250, 1100, 84, None),   # 毛边羊皮纸（黑底）
    "blackletter": (12347306, 1900, 82, None),   # 哥特黑体拉丁经文
    "goldleaf":    (30243820, 1400, 86, None),   # 旧金箔纹理
    "card-knight": (36577320, 1000, 84, None),   # 铠甲/纹章
    "card-codex":  (15983906, 1000, 84, None),   # 泥金手抄本内页
    "card-vault":  (35503967, 1000, 84, None),   # 古修道院木门
    "codex-spine": (8391471,  1400, 84, None),   # 古籍书脊烫金
}

def fetch_image(item):
    name, (pid, w, q, _mh) = item
    out = os.path.join(IMG, f"{name}.jpg")
    if os.path.exists(out) and os.path.getsize(out) > 5000:
        return out
    url = (f"https://images.pexels.com/photos/{pid}/pexels-photo-{pid}.jpeg"
           f"?auto=compress&cs=tinysrgb&w={w}")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    im = Image.open(io.BytesIO(data)).convert("RGB")
    if im.width > w:
        im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    im.save(out, "JPEG", quality=q, optimize=True, progressive=True)
    return out

with cf.ThreadPoolExecutor(max_workers=6) as ex:
    for p in ex.map(fetch_image, PICKS.items()):
        print("img  ", os.path.basename(p), os.path.getsize(p) // 1024, "KB")

# ---------- 字体：解析 google.css，只取 latin 子集 ----------
css_path = os.path.join(FON, "google.css")
css = open(css_path, encoding="utf-8").read()

blocks = re.findall(r"@font-face\s*\{(.*?)\}", css, re.S)
wanted, seen = [], set()
for b in blocks:
    fam = re.search(r"font-family:\s*'([^']+)'", b)
    sty = re.search(r"font-style:\s*(\w+)", b)
    wgt = re.search(r"font-weight:\s*(\d+)", b)
    url = re.search(r"url\((https://fonts\.gstatic\.com/[^)]+)\)", b)
    rng = re.search(r"unicode-range:\s*([^;]+);", b)
    if not (fam and url and rng):
        continue
    if not rng.group(1).strip().startswith("U+0000-00FF"):
        continue                      # 仅 latin 基本区
    key = url.group(1)
    if key in seen:
        continue
    seen.add(key)
    wanted.append((fam.group(1), sty.group(1) if sty else "normal",
                   wgt.group(1) if wgt else "400", key))

face_css = []
for fam, sty, wgt, url in wanted:
    slug = (fam.lower().replace(" ", "-") + "-" + wgt +
            ("-i" if sty == "italic" else ""))
    fn = slug + ".woff2"
    path = os.path.join(FON, fn)
    if not os.path.exists(path):
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            open(path, "wb").write(r.read())
    face_css.append(
        "@font-face{font-family:'%s';font-style:%s;font-weight:%s;font-display:swap;"
        "src:url('./%s') format('woff2');}" % (fam, sty, wgt, fn))
    print("font ", fn, os.path.getsize(path) // 1024, "KB")

open(os.path.join(FON, "fonts-local.css"), "w", encoding="utf-8").write(
    "\n".join(face_css) + "\n")
print("\nOK  fonts-local.css 已生成，共", len(face_css), "个 face")
