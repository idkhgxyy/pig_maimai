"""B50 图片渲染：自绘 HTML 模板（视觉参照 EasyMai 渲染器与游戏结算界面语言）+ Playwright 截图。

B50 语义说明（重要）：
落雪 API 的 /player/{fc}/bests 返回的 standard / dx 两个数组不是按"谱面类型"
划分的，而是按歌曲版本划分：standard = 旧版本曲 BEST 35（内含各种谱面类型），
dx = 当前版本曲 BEST 15。每条成绩的 type 字段才是谱面类型（standard/dx）。

布局：5 列制——B35 占 7 排、B15 占 3 排。
卡片：左侧曲绘 + 右侧信息面板，达成率为视觉主角（贴游戏结算界面心智）；
面板颜色区分谱面类型（紫=DX 谱、红=SD 谱）；信息行「难度（定数）=> RA · 物量」；
底部徽章排：评级彩虹章 + FC/AP 章 + FS/SYNC 章。
头部：DX Rating 金色大数字 + 段位章 + 「B35 + B15 = 总分」分解式。曲绘本地缓存。
"""

import asyncio
from html import escape
from pathlib import Path

import requests

PLUGIN_DIR = Path(__file__).resolve().parent
JACKET_DIR = PLUGIN_DIR / "jacket_cache"
JACKET_URL = "https://assets.lxns.net/maimai/jacket/{id}.png"

DIFF_NAMES = ["BAS", "ADV", "EXP", "MAS", "ReM"]

TYPE_NAMES = {"standard": "SD", "dx": "DX"}

COURSE_NAMES = {
    1: "初学者", 2: "初学者+", 3: "中级", 4: "中级+",
    5: "上级", 6: "上级+", 7: "SPECIALIST", 8: "SPECIALIST+",
    9: "MASTER", 10: "MASTER+", 11: "覇者", 12: "覇者+",
    13: "極", 14: "極+",
}

RANK_TEXT = {
    "d": "D", "c": "C", "b": "B", "bb": "BB", "bbb": "BBB",
    "a": "A", "aa": "AA", "aaa": "AAA", "s": "S", "sp": "S+",
    "ss": "SS", "ssp": "SS+", "sss": "SSS", "sssp": "SSS+",
}

FC_TEXT = {"fc": "FC", "fcp": "FC+", "ap": "AP", "app": "AP+"}
FS_TEXT = {"sync": "SYNC", "fs": "FS", "fsp": "FS+", "fsd": "FDX", "fsdp": "FDX+"}

TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  width: 1560px; padding: 22px;
  background: linear-gradient(165deg, #14162b 0%, #1c2145 52%, #262e5e 100%);
  color: #eceefc;
  font-family: 'Noto Sans CJK SC', 'Noto Sans SC', sans-serif;
}
.header {
  display: flex; align-items: center; gap: 20px;
  padding: 16px 26px; margin-bottom: 18px; border-radius: 16px;
  background: linear-gradient(120deg, rgba(255,255,255,0.07), rgba(255,255,255,0.02));
  border: 1px solid rgba(255,255,255,0.10);
}
.pname { font-size: 25px; font-weight: 800; letter-spacing: 1px; }
.pmeta { font-size: 12px; color: #9aa3cf; margin-top: 6px; }
.dan {
  margin-left: 6px; padding: 5px 18px; border-radius: 20px;
  background: linear-gradient(135deg, #e8543f, #c22e57);
  border: 1px solid rgba(255, 190, 120, 0.65);
  color: #fff; font-weight: 800; font-size: 16px;
  text-shadow: 0 1px 2px rgba(0,0,0,0.45);
}
.rating-box { margin-left: auto; text-align: right; }
.rating-box .label {
  font-size: 11px; color: #b9a56b; letter-spacing: 3px; margin-bottom: 2px;
}
.rating-num {
  font-size: 46px; font-weight: 900; line-height: 1;
  background: linear-gradient(180deg, #ffe08a 20%, #f5a623);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  font-variant-numeric: tabular-nums;
}
.split { text-align: right; font-size: 13px; color: #aab2e0; margin-top: 7px; }
.split b { color: #ffd166; font-variant-numeric: tabular-nums; }
.sec-title {
  font-size: 14px; font-weight: 700; letter-spacing: 1px; color: #8fa3ff;
  margin: 2px 0 9px; padding-bottom: 6px;
  border-bottom: 1px solid rgba(143, 163, 255, 0.25);
}
.sec-title .total { float: right; color: #ffd166; font-variant-numeric: tabular-nums; }
.grid5 { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; margin-bottom: 16px; }
.card { display: flex; height: 104px; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 7px rgba(0,0,0,0.38); }
.jacket { width: 96px; height: 104px; object-fit: cover; flex: none; background: #2c3562; }
.info { flex: 1; min-width: 0; padding: 8px 10px 7px; display: flex; flex-direction: column; }
.info.dx { background: linear-gradient(160deg, #7b5fc2 0%, #4a3488 100%); }
.info.sd { background: linear-gradient(160deg, #c04a68 0%, #7c2340 100%); }
.title { font-size: 13px; font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ach { font-size: 23px; font-weight: 800; line-height: 1.12; font-variant-numeric: tabular-nums; text-shadow: 0 1px 3px rgba(0,0,0,0.3); }
.ach small { font-size: 13px; font-weight: 700; }
.eq { font-size: 11.5px; color: rgba(255,255,255,0.88); margin-top: 1px; font-variant-numeric: tabular-nums; }
.eq .lv { font-weight: 700; color: #ffe08a; }
.badges { margin-top: auto; display: flex; gap: 3px; align-items: center; overflow: hidden; }
.rank {
  font-size: 10.5px; font-weight: 800; padding: 1px 8px; border-radius: 9px;
  color: #fff; text-shadow: 0 1px 1px rgba(0,0,0,0.35); white-space: nowrap; flex: none;
}
.rank.sssp { background: linear-gradient(90deg, #ff8a65, #ffd54f, #69f0ae, #40c4ff, #b388ff); color: #241a3d; text-shadow: none; }
.rank.sss { background: linear-gradient(90deg, #ffd54f, #ffb300); }
.rank.ssp { background: linear-gradient(90deg, #cfd8dc, #90a4ae); color: #263238; text-shadow: none; }
.rank.ss { background: linear-gradient(90deg, #80cbc4, #4db6ac); }
.rank.sp { background: linear-gradient(90deg, #f48fb1, #ec407a); }
.rank.s { background: linear-gradient(90deg, #90caf9, #42a5f5); }
.rank.aaa { background: linear-gradient(90deg, #a5d6a7, #66bb6a); }
.pill {
  font-size: 9.5px; font-weight: 700; padding: 1px 5px; border-radius: 9px;
  border: 1px solid; letter-spacing: 0.3px; white-space: nowrap; flex: none;
}
.pill.fc { color: #b9ffd6; border-color: #69f0ae; background: rgba(105,240,174,0.14); }
.pill.ap { color: #ffd8a8; border-color: #ffb74d; background: rgba(255,183,77,0.14); }
.pill.fs { color: #a5f3fc; border-color: #22d3ee; background: rgba(34,211,238,0.14); }
.pill.sync { color: #c7d2fe; border-color: #818cf8; background: rgba(129,140,248,0.14); }
.pill.note { color: #d8dcf2; border-color: rgba(216,220,242,0.5); background: rgba(255,255,255,0.08); }
.footer { margin-top: 4px; text-align: center; font-size: 10.5px; color: #6b7299; }
</style></head><body>
  <div class="header">
    <div>
      <div class="pname">__PNAME__</div>
      <div class="pmeta">数据同步 __UPLOAD__ · 落雪咖啡屋 API</div>
    </div>
    <div class="dan">__DAN__</div>
    <div class="rating-box">
      <div class="label">DX RATING</div>
      <div class="rating-num">__RATING__</div>
      <div class="split">B35 <b>__STD_TOTAL__</b> + B15 <b>__DX_TOTAL__</b> = <b>__RATING__</b></div>
    </div>
  </div>
  <div class="sec-title">旧版本曲 BEST <span class="total">__STD_TOTAL__</span></div>
  <div class="grid5">__STD_ROWS__</div>
  <div class="sec-title">当前版本曲 BEST <span class="total">__DX_TOTAL__</span></div>
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


def _build_chart_lookup(song_data: dict) -> dict:
    """{(song_id, type, level_index): chart}，用于取难度标签/定数/物量。"""
    lookup = {}
    for s in (song_data or {}).get("songs", []):
        for tk in ("standard", "dx"):
            for li, ch in enumerate(s.get("difficulties", {}).get(tk) or []):
                lookup[(s.get("id"), tk, li)] = ch
    return lookup


def _pill(cls: str, text: str) -> str:
    return f'<span class="pill {cls}">{text}</span>'


def _song_row(score: dict, lookup: dict) -> str:
    idx = score.get("level_index", 3)
    diff_name = DIFF_NAMES[idx] if 0 <= idx < len(DIFF_NAMES) else "?"
    t = score.get("type", "standard")
    type_cls = "info dx" if t == "dx" else "info sd"
    title = escape(str(score.get("song_name", "???")))
    ach = score.get("achievements", 0)
    ra = int(round(score.get("dx_rating", 0)))

    ch = lookup.get((score.get("id"), t, idx), {})
    level = ch.get("level", score.get("level", ""))
    lv_value = ch.get("level_value")
    notes_total = (ch.get("notes") or {}).get("total")
    eq = f'<span class="lv">{diff_name} {level}</span>'
    if lv_value:
        eq += f"（{lv_value:.1f}）"
    eq += f" => {ra} RA"

    rank_key = str(score.get("rate") or "").lower()
    rank_text = RANK_TEXT.get(rank_key, rank_key.upper())
    badges = f'<span class="rank {rank_key}">{rank_text}</span>'
    fc_text = FC_TEXT.get(score.get("fc") or "")
    if fc_text:
        badges += _pill("ap" if "AP" in fc_text else "fc", fc_text)
    fs_text = FS_TEXT.get(score.get("fs") or "")
    if fs_text:
        badges += _pill("fs" if fs_text != "SYNC" else "sync", fs_text)
    if notes_total:
        badges += _pill("note", f"物量{notes_total}")

    jacket = _jacket_file(score.get("id"))
    src = f"file://{jacket}" if str(jacket) else ""

    return (
        f'<div class="card">'
        f'<img class="jacket" src="{src}">'
        f'<div class="{type_cls}">'
        f'<div class="title">{title}</div>'
        f'<div class="ach">{ach:.4f}<small>%</small></div>'
        f'<div class="eq">{eq}</div>'
        f'<div class="badges">{badges}</div>'
        f'</div></div>'
    )


def build_html(player: dict, bests: dict, song_data: dict = None) -> str:
    std = bests.get("standard") or []  # 旧版本曲 B35
    dx = bests.get("dx") or []  # 当前版本曲 B15
    lookup = _build_chart_lookup(song_data)

    dan = COURSE_NAMES.get(player.get("course_rank", 0), "")
    html = TEMPLATE
    html = html.replace("__PNAME__", escape(str(player.get("name", "???"))))
    html = html.replace("__UPLOAD__", str(player.get("upload_time", ""))[:10])
    html = html.replace("__DAN__", escape(dan) if dan else "无段位")
    html = html.replace("__RATING__", str(player.get("rating", "???")))
    html = html.replace("__STD_TOTAL__", str(bests.get("standard_total", "")))
    html = html.replace("__DX_TOTAL__", str(bests.get("dx_total", "")))
    html = html.replace("__STD_ROWS__", "".join(_song_row(s, lookup) for s in std))
    html = html.replace("__DX_ROWS__", "".join(_song_row(s, lookup) for s in dx))
    return html


def render_png(player: dict, bests: dict, out_path: Path, song_data: dict = None) -> None:
    """同步渲染（调用方用 asyncio.to_thread 包一层）。"""
    from playwright.sync_api import sync_playwright

    html_path = PLUGIN_DIR / "b50_last.html"
    html_path.write_text(build_html(player, bests, song_data), encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-gpu"])
        page = browser.new_page(
            viewport={"width": 1560, "height": 1200}, device_scale_factor=2
        )
        page.goto(html_path.as_uri())
        page.wait_for_timeout(1500)  # 等曲绘解码
        page.screenshot(path=str(out_path), full_page=True)
        browser.close()


async def render_b50_png_async(player: dict, bests: dict, out_path: Path, song_data: dict = None) -> None:
    await asyncio.to_thread(render_png, player, bests, out_path, song_data)



# ==================== 歌曲详情卡 ====================

SONG_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  width: 560px; padding: 24px;
  background: linear-gradient(160deg, #141428 0%, #1c2340 55%, #232a52 100%);
  color: #e8e8f0;
  font-family: 'Noto Sans CJK SC', 'Noto Sans SC', sans-serif;
}
.top { display: flex; gap: 18px; margin-bottom: 18px; }
.jacket {
  width: 170px; height: 170px; border-radius: 12px; object-fit: cover;
  background: #2c3562; flex-shrink: 0;
}
.idline {
  font-size: 11px; color: #8fa3ff; letter-spacing: 2px; margin-bottom: 4px;
}
.title {
  font-size: 19px; font-weight: 800; line-height: 1.3; margin-bottom: 10px;
  word-break: break-all;
}
.frow { font-size: 12px; margin-bottom: 6px; color: #b6bade; }
.frow .k { color: #8fa3ff; font-weight: 700; margin-right: 6px; }
.frow .v { color: #e8e8f0; }
.charts { width: 100%; border-collapse: collapse; }
.charts td {
  padding: 7px 8px; font-size: 12px;
  background: rgba(255, 255, 255, 0.05);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.charts tr:first-child td { color: #8fa3ff; font-size: 10.5px; background: none; }
.badge {
  font-size: 10px; font-weight: 700; padding: 2px 7px; border-radius: 4px; color: #fff;
  white-space: nowrap;
}
.cnst { color: #ffd166; font-weight: 700; font-variant-numeric: tabular-nums; }
.notes { color: #9aa0c3; font-variant-numeric: tabular-nums; }
.footer { margin-top: 14px; text-align: center; font-size: 10px; color: #6b7299; }
</style></head><body>
  <div class="top">
    <img class="jacket" src="__JACKET__">
    <div>
      <div class="idline">__ID__</div>
      <div class="title">__TITLE__</div>
      <div class="frow"><span class="k">曲师</span><span class="v">__ARTIST__</span></div>
      <div class="frow"><span class="k">分类</span><span class="v">__GENRE__</span></div>
      <div class="frow"><span class="k">版本</span><span class="v">__VERSION__</span></div>
      <div class="frow"><span class="k">BPM</span><span class="v">__BPM__</span></div>
    </div>
  </div>
  <table class="charts">
    <tr><td>难度</td><td>定数</td><td>谱师</td><td>物量</td></tr>
    __CHART_ROWS__
  </table>
  <div class="footer">猪bot · pig_maimai · 数据来自落雪咖啡屋</div>
</body></html>
"""


def _fmt_level(level_value) -> str:
    """7.5 → 7+（定数换算显示难度），14.0 → 14"""
    lv = float(level_value)
    return f"{int(lv)}+" if lv % 1 else str(int(lv))


def _chart_row(chart: dict) -> str:
    idx = chart.get("difficulty", 3)
    color = DIFF_COLORS[idx] if 0 <= idx < len(DIFF_COLORS) else "#888"
    name = DIFF_NAMES[idx] if 0 <= idx < len(DIFF_NAMES) else "?"
    badge = f'<span class="badge" style="background:{color}">{name} {_fmt_level(chart.get("level_value", 0))}</span>'
    cnst = f'<span class="cnst">{chart.get("level_value", "?")}</span>'
    designer = escape(str(chart.get("note_designer") or "-"))
    notes = chart.get("notes") or {}
    total = notes.get("total", "?") if notes else "?"
    return (
        f"<tr><td>{badge}</td><td>{cnst}</td>"
        f"<td>{designer}</td><td class='notes'>{total}</td></tr>"
    )


def build_song_html(song: dict, version_names: dict, genre_names: dict) -> str:
    html = SONG_TEMPLATE
    html = html.replace("__JACKET__", JACKET_URL.format(id=song.get("id")))
    html = html.replace("__ID__", f"No.{song.get('id', '???')}")
    html = html.replace("__TITLE__", escape(str(song.get("title", "???"))))
    html = html.replace("__ARTIST__", escape(str(song.get("artist", "???"))))
    genre = genre_names.get(song.get("genre"), song.get("genre", "???"))
    html = html.replace("__GENRE__", escape(str(genre)))
    version = version_names.get(song.get("version"), song.get("version", "???"))
    html = html.replace("__VERSION__", escape(str(version)))
    html = html.replace("__BPM__", str(song.get("bpm", "???")))

    diffs = song.get("difficulties", {})
    charts = (diffs.get("standard") or []) + (diffs.get("dx") or [])
    html = html.replace("__CHART_ROWS__", "".join(_chart_row(c) for c in charts))
    return html


def render_song_png(song: dict, version_names: dict, genre_names: dict, out_path: Path) -> None:
    """同步渲染歌曲详情卡（调用方用 asyncio.to_thread 包一层）。"""
    from playwright.sync_api import sync_playwright

    html_path = PLUGIN_DIR / "song_last.html"
    html_path.write_text(
        build_song_html(song, version_names, genre_names), encoding="utf-8"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox", "--disable-gpu"])
        page = browser.new_page(
            viewport={"width": 560, "height": 700}, device_scale_factor=2
        )
        page.goto(html_path.as_uri())
        page.wait_for_timeout(1200)  # 等曲绘加载
        page.screenshot(path=str(out_path), full_page=True)
        browser.close()


async def render_song_png_async(
    song: dict, version_names: dict, genre_names: dict, out_path: Path
) -> None:
    await asyncio.to_thread(render_song_png, song, version_names, genre_names, out_path)
