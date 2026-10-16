# -*- coding: utf-8 -*-
"""生成无缝「羊皮纸」底色纹理（1024×1024 JPEG），供 .sheet 平铺使用。
原理：可平铺的多倍频值噪声 + 纸纤维条纹 + 霉斑（foxing），全部走环形边界。"""
import os
import numpy as np
from PIL import Image, ImageFilter

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "assets", "img", "parchment-tile.jpg")
N = 1024
rng = np.random.default_rng(20261015)


def tileable_noise(n, cells, seed):
    """在 cells×cells 的随机格点上双线性插值放大到 n×n，边界环绕 → 无缝"""
    r = np.random.default_rng(seed)
    g = r.random((cells, cells)).astype(np.float32)
    # 环形延拓后放大
    g2 = np.concatenate([g, g[:1]], axis=0)
    g2 = np.concatenate([g2, g2[:, :1]], axis=1)

    ys = np.linspace(0, cells, n, endpoint=False, dtype=np.float32)
    xs = np.linspace(0, cells, n, endpoint=False, dtype=np.float32)
    y0 = np.floor(ys).astype(int); x0 = np.floor(xs).astype(int)
    fy = (ys - y0)[:, None]; fx = (xs - x0)[None, :]

    # 用 smoothstep 让插值更自然
    fy = fy * fy * (3 - 2 * fy); fx = fx * fx * (3 - 2 * fx)

    a = g2[np.ix_(y0, x0)]
    b = g2[np.ix_(y0, x0 + 1)]
    c = g2[np.ix_(y0 + 1, x0)]
    d = g2[np.ix_(y0 + 1, x0 + 1)]
    top = a * (1 - fx) + b * fx
    bot = c * (1 - fx) + d * fx
    return top * (1 - fy) + bot * fy


# --- 多倍频噪声：只保留中高频细节（低频交给 CSS 渐变做旧，避免平铺露馅） ---
field = np.zeros((N, N), np.float32)
for cells, a in [(6, 0.16), (13, 0.20), (29, 0.22), (71, 0.22), (160, 0.20)]:
    field += a * tileable_noise(N, cells, 1000 + cells)
field /= field.max()
field = (field - field.mean()) / (field.std() + 1e-6) * 0.20 + 0.5
field = np.clip(field, 0, 1)

# --- 纸纤维：细密横向条纹 ---
fiber = tileable_noise(N, 300, 77)
band = 0.5 + 0.5 * np.sin(np.arange(N, dtype=np.float32)[None, :] / N * 2 * np.pi * 96)
fiber = 0.5 + (fiber - 0.5) * 0.7 * (0.7 + 0.6 * band)

# --- 霉斑 foxing：环形随机软斑，暖褐色，克制地加 ---
fox = np.zeros((N, N), np.float32)
yy = np.arange(N, dtype=np.float32)[:, None]
xx = np.arange(N, dtype=np.float32)[None, :]
for _ in range(14):
    cy, cx = rng.integers(0, N, 2)
    rad = rng.integers(30, 110)
    dy = np.minimum(np.abs(yy - cy), N - np.abs(yy - cy))
    dx = np.minimum(np.abs(xx - cx), N - np.abs(xx - cx))
    d = np.sqrt(dy ** 2 + dx ** 2)
    fox += np.exp(-(d ** 2) / (2 * (rad * 0.5) ** 2)) * float(rng.uniform(.25, .7))
fox = np.clip(fox / max(fox.max(), 1e-6), 0, 1)

# --- 配色：整体接近奶蜜色，只做轻微明暗 ---
c_light = np.array([250, 243, 224], np.float32)
c_dark  = np.array([221, 203, 166], np.float32)
c_fox   = np.array([196, 158, 104], np.float32)

lum = 0.55 * field + 0.45 * fiber          # 0..1
rgb = c_light * lum[..., None] + c_dark * (1 - lum[..., None])
rgb *= (0.975 + 0.05 * (fiber - 0.5))[..., None]
f = (fox * 0.55)[..., None]
rgb = rgb * (1 - 0.20 * f) + c_fox * (0.22 * f)

img = Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8), "RGB")
img = img.filter(ImageFilter.GaussianBlur(0.5))

# 细颗粒（纸面微砂感）
noise = (rng.random((N, N, 1)).astype(np.float32) - 0.5) * 7.0
arr = np.clip(np.asarray(img, np.float32) + noise, 0, 255).astype(np.uint8)
Image.fromarray(arr, "RGB").save(OUT, "JPEG", quality=90, optimize=True, progressive=True)
print("seamless parchment ->", OUT, os.path.getsize(OUT) // 1024, "KB")

# 顺带输出一张缩略预览，便于人工确认无明显接缝
img.resize((512, 512)).save(os.path.join(os.path.dirname(OUT), "..", "..",
                                         "_tools", "sheets", "tile-check.png"))
