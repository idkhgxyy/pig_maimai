"""B50 图片渲染：自绘 HTML 模板（借鉴落雪/水鱼查分器视觉语言）+ Playwright 截图。

B50 语义说明（重要）：
落雪 API 的 /player/{fc}/bests 返回的 standard / dx 两个数组不是按"谱面类型"
划分的，而是按歌曲版本划分：standard = 旧版本曲 BEST 35（内含各种谱面类型），
dx = 当前版本曲 BEST 15。每条成绩的 type 字段才是谱面类型（standard/dx）。

布局：水鱼经典 5 列制——B35 占 7 排、B15 占 3 排，正好 10 排无空位。
每格为曲绘铺底的紧凑卡片：左上角谱面类型+难度徽章，右上角金色 RA，
底部曲名+达成率+FC/FS 标记。曲绘本地缓存。
"""

import asyncio
from html import escape
from pathlib import Path

import requests

PLUGIN_DIR = Path(__file__).resolve().parent
JACKET_DIR = PLUGIN_DIR / "jacket_cache"
JACKET_URL = "https://assets.lxns.net/maimai/jacket/{id}.png"

DIFF_NAMES = ["BAS", "ADV", "EXP", "MAS", "ReM"]
DIFF_COLORS = ["#34a853", "#f9ab00", "#ff6e91", "#a06cd5", "#c58af9"]

TYPE_NAMES = {"standard": "标准", "dx": "DX"}

FC_FS_NAMES = {
    "fc": "FC", "fcp": "FC+", "ap": "AP", "app": "AP+",
    "fs": "FS", "fsp": "FS+", "fdx": "FDX", "fdxp": "FDX+",
}

TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  width: 780px; padding: 24px;
  background: linear-gradient(160deg, #141428 0%, #1c2340 55%, #232a52 100%);
  color: #e8e8f0;
  font-family: 'Noto Sans CJK SC', 'Noto Sans SC', sans-serif;
}
.header { display: flex; align-items: center; margin-bottom: 20px; }
.avatar {
  width: 60px; height: 60px; border-radius: 12px; margin-right: 15px;
  background: #2c3562; display: flex; align-items: center; justify-content: center;
  font-size: 32px;
}
.pname { font-size: 21px; font-weight: 700; letter-spacing: 1px; }
.pmeta { font-size: 12px; color: #9aa0c3; margin-top: 4px; }
.rating-badge {
  margin-left: auto; text-align: center;
  background: rgba(255, 209, 102, 0.12); border: 1px solid rgba(255, 209, 102, 0.45);
  border-radius: 12px; padding: 9px 16px;
}
.rating-badge .num { font-size: 25px; font-weight: 800; color: #ffd166; }
.rating-badge .label { font-size: 10px; color: #b9a56b; letter-spacing: 2px; }
.sec-title {
  font-size: 13.5px; font-weight: 700; letter-spacing: 1px; color: #8fa3ff;
  margin: 2px 0 8px; padding-bottom: 5px;
  border-bottom: 1px solid rgba(143, 163, 255, 0.25);
}
.sec-title .total { float: right; color: #ffd166; }
.sec-title .count {
  font-size: 10px; font-weight: 400; color: #6b7299; margin-left: 8px;
  background: rgba(255,255,255,0.08); border-radius: 4px; padding: 1px 6px;
}
.grid5 { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin-bottom: 18px; }
.song { position: relative; height: 96px; border-radius: 8px; overflow: hidden; background: #2c3562; }
.jacket { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.shade {
  position: absolute; inset: 0;
  background: linear-gradient(180deg, rgba(8,10,26,0.10) 32%, rgba(8,10,26,0.90) 80%);
}
.tags { position: absolute; top: 4px; left: 5px; display: flex; gap: 3px; align-items: center; }
.type-chip {
  font-size: 8.5px; padding: 0 4px; border-radius: 3px;
  border: 1px solid rgba(255,255,255,0.5); color: #eef0ff;
  background: rgba(8,10,26,0.45); backdrop-filter: blur(2px);
}
.type-chip.dx { border-color: rgba(103, 232, 249, 0.8); color: #8ff3ff; }
.badge {
  font-size: 9px; font-weight: 700; padding: 1px 5px; border-radius: 4px; color: #fff;
  text-shadow: 0 1px 2px rgba(0,0,0,0.5);
}
.ra {
  position: absolute; top: 3px; right: 6px;
  font-size: 14px; font-weight: 800; color: #ffd166;
  text-shadow: 0 1px 3px rgba(0,0,0,0.9); font-variant-numeric: tabular-nums;
}
.binfo { position: absolute; left: 6px; right: 6px; bottom: 4px; }
.title {
  font-size: 10.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  text-shadow: 0 1px 2px rgba(0,0,0,0.9); margin-bottom: 2px;
}
.meta { font-size: 9px; display: flex; gap: 4px; align-items: center; color: #dfe3ff; }
.ach { font-variant-numeric: tabular-nums; }
.mini {
  background: rgba(255,255,255,0.18); border-radius: 3px; padding: 0 3px;
  font-size: 8.5px; color: #ffd7a8;
}
.footer { margin-top: 4px; text-align: center; font-size: 10px; color: #6b7299; }
</style></head><body>
  <div class="header">
    <div class="avatar">🐷</div>
    <div>
      <div class="pname">__PNAME__</div>
      <div class="pmeta">数据同步 __UPLOAD__ · 落雪咖啡屋 API</div>
    </div>
    <div class="rating-badge">
      <div class="num">__RATING__</div>
      <div class="label">DX RATING</div>
    </div>
  </div>
  <div class="sec-title">旧版本谱面 BEST <span class="count">B35</span><span class="total">__STD_TOTAL__</span></div>
  <div class="grid5">__STD_ROWS__</div>
  <div class="sec-title">当前版本谱面 BEST <span class="count">B15</span><span class="total">__DX_TOTAL__</span></div>
  <div class="grid5">__DX_ROWS__</div>
  <div class="footer">猪bot · pig_maimai · 数据来自落雪咖啡屋</div>
</body></html>
"""


def _jacket_file(song_id) -> Path:
    """取曲绘本地缓存，没有则下载；失败返回空（模板里显示灰色底）。"""
    JACKET_DIR.mkdir(exist_ok=True)
    path = JACKET_DIR / f"{song_id}.png"
    if not path.exists() or path.stat().st_size == 0:
        try:
            r = requests.get(JACKET_URL.format(id=song_id), timeout=15)
            r.raise_for_status()
            path.write_bytes(r.content)
        except Exception:
            return Path("")  # 空路径 → 无 src → 灰底占位
    return path


def _song_row(score: dict) -> str:
    idx = score.get("level_index", 3)
    color = DIFF_COLORS[idx] if 0 <= idx < len(DIFF_COLORS) else "#888"
    name = DIFF_NAMES[idx] if 0 <= idx < len(DIFF_NAMES) else "?"
    level = score.get("level", "")
    ach = score.get("achievements", 0)
    ra = int(round(score.get("dx_rating", 0)))
    title = escape(str(score.get("song_name", "???")))

    # 谱面类型（standard=标准 / dx=DX），这是每条成绩自带的字段
    t = TYPE_NAMES.get(score.get("type"), "?")
    chip_cls = "type-chip dx" if score.get("type") == "dx" else "type-chip"

    tags = ""
    fc = FC_FS_NAMES.get(score.get("fc") or "")
    fs = FC_FS_NAMES.get(score.get("fs") or "")
    if fc:
        tags += f'<span class="mini">{fc}</span>'
    if fs:
        tags += f'<span class="mini">{fs}</span>'

    jacket = _jacket_file(score.get("id"))
    src = f"file://{jacket}" if str(jacket) else ""

    return (
        f'<div class="song">'
        f'<img class="jacket" src="{src}">'
        f'<div class="shade"></div>'
        f'<div class="tags"><span class="{chip_cls}">{t}</span>'
        f'<span class="badge" style="background:{color}">{name} {level}</span></div>'
        f'<div class="ra">{ra}</div>'
        f'<div class="binfo">'
        f'<div class="title">{title}</div>'
        f'<div class="meta"><span class="ach">{ach:.4f}%</span>{tags}</div>'
        f'</div>'
        f'</div>'
    )


def build_html(player: dict, bests: dict) -> str:
    std = bests.get("standard") or []  # 旧版本曲 B35
    dx = bests.get("dx") or []  # 当前版本曲 B15
    html = TEMPLATE
    html = html.replace("__PNAME__", escape(str(player.get("name", "???"))))
    upload = str(player.get("upload_time", ""))[:10]
    html = html.replace("__UPLOAD__", upload)
    html = html.replace("__RATING__", str(player.get("rating", "???")))
    html = html.replace("__STD_TOTAL__", str(bests.get("standard_total", "")))
    html = html.replace("__DX_TOTAL__", str(bests.get("dx_total", "")))
    html = html.replace("__STD_ROWS__", "".join(_song_row(s) for s in std))
    html = html.replace("__DX_ROWS__", "".join(_song_row(s) for s in dx))
    return html


def render_png(player: dict, bests: dict, out_path: Path) -> None:
    """同步渲染（调用方用 asyncio.to_thread 包一层）。"""
    from playwright.sync_api import sync_playwright

    html_path = PLUGIN_DIR / "b50_last.html"
    html_path.write_text(build_html(player, bests), encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-gpu"])
        page = browser.new_page(
            viewport={"width": 780, "height": 900}, device_scale_factor=2
        )
        page.goto(html_path.as_uri())
        page.wait_for_timeout(1500)  # 等曲绘解码
        page.screenshot(path=str(out_path), full_page=True)
        browser.close()


async def render_b50_png_async(player: dict, bests: dict, out_path: Path) -> None:
    await asyncio.to_thread(render_png, player, bests, out_path)
