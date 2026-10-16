# -*- coding: utf-8 -*-
"""下载 Pexels 候选素材并生成分类缩略图联络表"""
import os, sys, urllib.request, concurrent.futures as cf
from PIL import Image, ImageDraw

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(BASE, "_tools", "cand")
SHEET = os.path.join(BASE, "_tools", "sheets")
os.makedirs(RAW, exist_ok=True)
os.makedirs(SHEET, exist_ok=True)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

GROUPS = {
    "parchment": [16557322, 38316250, 7953297, 5102219, 12463677, 7232498, 5102224, 7233124, 7233099, 5102221],
    "gold":      [30243820, 7430598, 34034144, 35719283, 2248589, 4880794, 7325108, 7405670],
    "manuscript":[12039703, 30560588, 27980497, 13208790, 15983906, 12347306, 35481062, 16076979, 36306963, 29342494, 29342496, 12039705],
    "engraving": [7479025, 31350073, 35976200, 37374996, 36577320, 5711224, 35503967, 33141602, 29300542, 31350042, 9879475, 5668222],
    "leather":   [33352856, 34217726, 17144197, 8391471, 8545598, 8391464, 35769732, 13061425, 35098073, 35098071, 33352858, 13923801],
}

def url_of(pid, w=600):
    return (f"https://images.pexels.com/photos/{pid}/pexels-photo-{pid}.jpeg"
            f"?auto=compress&cs=tinysrgb&w={w}")

def grab(args):
    pid, name = args
    path = os.path.join(RAW, f"{name}_{pid}.jpg")
    if os.path.exists(path) and os.path.getsize(path) > 3000:
        return path
    try:
        req = urllib.request.Request(url_of(pid), headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=40) as r:
            data = r.read()
        if len(data) < 2000:
            return None
        with open(path, "wb") as f:
            f.write(data)
        return path
    except Exception as e:
        print("FAIL", pid, e)
        return None

jobs = [(pid, name) for name, ids in GROUPS.items() for pid in ids]
with cf.ThreadPoolExecutor(max_workers=8) as ex:
    list(ex.map(grab, jobs))

# 生成联络表
for name, ids in GROUPS.items():
    paths = [(pid, os.path.join(RAW, f"{name}_{pid}.jpg")) for pid in ids]
    paths = [(pid, p) for pid, p in paths if os.path.exists(p)]
    if not paths:
        continue
    COLS, CW, CH, PAD, TOP = 4, 300, 300, 8, 22
    rows = (len(paths) + COLS - 1) // COLS
    W = COLS * CW + PAD * (COLS + 1)
    H = rows * (CH + TOP) + PAD * (rows + 1)
    sheet = Image.new("RGB", (W, H), (18, 18, 20))
    d = ImageDraw.Draw(sheet)
    for i, (pid, p) in enumerate(paths):
        r, c = divmod(i, COLS)
        x = PAD + c * (CW + PAD)
        y = PAD + r * (CH + TOP + PAD)
        try:
            im = Image.open(p).convert("RGB")
            im.thumbnail((CW, CH))
            sheet.paste(im, (x + (CW - im.width) // 2, y + TOP + (CH - im.height) // 2))
        except Exception as e:
            print("IMG FAIL", pid, e)
        d.text((x + 4, y + 5), f"[{i}] {name} {pid}", fill=(255, 220, 130))
    out = os.path.join(SHEET, f"{name}.jpg")
    sheet.save(out, quality=82)
    print("sheet ->", out, sheet.size, len(paths))
