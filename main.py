"""猪bot查分（pig_maimai）：基于落雪咖啡屋 API 的舞萌DX查分插件。

v0.1.0 功能：
- /rating [QQ号]  查玩家 rating / 段位 / 好友码
- /b50 [QQ号]     查 B50 成绩（v1 为文本摘要，图片渲染规划中）
- /查歌 <关键词>   按曲名搜索曲库（公开接口，无需令牌）

配置：插件目录下 config.json 填 developer_token（落雪开发者令牌）。
"""

import asyncio
import glob
import json
import os
import random
import re
import sys
from pathlib import Path

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register

# 保证能 import 同目录下的 lxns.py / render.py（不依赖插件系统的模块命名方式）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ra as ra_calc  # noqa: E402
from lxns import LXNSError, LxnsClient  # noqa: E402

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))

# 难度序号 → 简称（level_index: 0=Basic 1=Advanced 2=Expert 3=Master 4=Re:Master）
DIFF_NAMES = ["BAS", "ADV", "EXP", "MAS", "ReM"]

# /来首 谱面难度缩写 → level_index
DIFF_ABBR = {
    "bas": 0, "basic": 0,
    "adv": 1, "advanced": 1,
    "exp": 2, "expert": 2,
    "mas": 3, "master": 3,
    "rem": 4, "remaster": 4, "re:master": 4,
}

# 段位编号 → 名称（maimai DX 段位认定，落雪 course_rank 字段）
COURSE_NAMES = {
    0: "无段位",
    1: "初学者", 2: "初学者+",
    3: "中级", 4: "中级+",
    5: "上级", 6: "上级+",
    7: "SPECIALIST", 8: "SPECIALIST+",
    9: "MASTER", 10: "MASTER+",
    11: "覇者", 12: "覇者+",
    13: "極", 14: "極+",
}


def _load_token() -> str:
    try:
        with open(os.path.join(PLUGIN_DIR, "config.json"), encoding="utf-8") as f:
            return (json.load(f).get("developer_token") or "").strip()
    except Exception:
        return ""


def _fmt_player(player: dict) -> str:
    course = COURSE_NAMES.get(player.get("course_rank", 0), str(player.get("course_rank")))
    return (
        "🐷 猪bot×落雪查分\n"
        f"玩家: {player.get('name', '???')}\n"
        f"DX Rating: {player.get('rating', '???')}\n"
        f"段位: {course.strip() or '无段位'}\n"
        f"数据同步: {player.get('upload_time', '???')[:10]}"
    )


def _fmt_b50_summary(bests: dict) -> str:
    std = bests.get("standard") or []
    dx = bests.get("dx") or []
    std_total = bests.get("standard_total", "—")
    dx_total = bests.get("dx_total", "—")

    def top_lines(scores, n=5):
        lines = []
        for s in scores[:n]:
            diff = DIFF_NAMES[s.get("level_index", 3)]
            lines.append(
                f"  {s.get('song_name', '???')} [{diff}] "
                f"{s.get('achievements', 0):.4f}%  ra={s.get('dx_rating', '?')}"
            )
        return "\n".join(lines) if lines else "  (无成绩数据)"

    return (
        "📊 B50 摘要（v1 文本版，渲染图规划中）\n"
        f"标准 B30 总 RA: {std_total}\n{top_lines(std)}\n"
        f"DX B15 总 RA: {dx_total}\n{top_lines(dx)}"
    )


@register("pig_maimai", "gxyy", "猪bot查分：落雪API舞萌DX查分/B50/查歌/随机选曲/吃分推荐", "0.5.0")
class PigMaimaiPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.client = LxnsClient(
            token=_load_token(), cache_dir=os.path.dirname(os.path.abspath(__file__))
        )
        self.token_empty = not self.client.token
        print(f"=== pig_maimai 已加载，令牌{'已配置' if not self.token_empty else '未配置'} ===", flush=True)

    def _client(self) -> LxnsClient:
        """惰性刷新令牌（改完 config.json 重启前也能热读）。"""
        self.client.token = _load_token()
        return self.client

    def _resolve_qq(self, event: AstrMessageEvent, arg: str) -> str:
        """不带参数查自己，带参数查指定 QQ。"""
        return (arg or "").strip() or str(event.get_sender_id())

    @filter.command("rating")
    async def rating(self, event: AstrMessageEvent, qq: str = ""):
        """/rating [QQ号] 查舞萌DX rating"""
        qq = self._resolve_qq(event, qq)
        if self.token_empty and not _load_token():
            yield event.plain_result("开发者令牌还没配置，等猪主人填好就能查啦")
            return
        try:
            player = await asyncio.to_thread(self._client().get_player_by_qq, qq)
            yield event.plain_result(_fmt_player(player))
        except LXNSError as e:
            yield event.plain_result(f"🐷 查分失败：{e}")

    @filter.command("b50")
    async def b50(self, event: AstrMessageEvent, qq: str = ""):
        """/b50 [QQ号] 查B50成绩摘要"""
        qq = self._resolve_qq(event, qq)
        if self.token_empty and not _load_token():
            yield event.plain_result("开发者令牌还没配置，等猪主人填好就能查啦")
            return
        try:
            client = self._client()
            player = await asyncio.to_thread(client.get_player_by_qq, qq)
            friend_code = str(player.get("friend_code", ""))
            bests = await asyncio.to_thread(client.get_bests, friend_code)
        except LXNSError as e:
            yield event.plain_result(f"🐷 查分失败：{e}")
            return

        out_dir = Path(PLUGIN_DIR) / "render_cache"
        out_dir.mkdir(exist_ok=True)
        out = out_dir / f"b50_{qq}.png"
        try:
            import render as b50render  # noqa: PLC0415

            await b50render.render_b50_png_async(player, bests, out)
            yield event.image_result(str(out))
        except Exception as e:  # 渲染兜底：回退文本版
            yield event.plain_result(
                _fmt_b50_summary(bests) + f"\n\n(图片渲染失败已回退: {type(e).__name__}: {e})"
            )

    @filter.command("查歌")
    async def search_song(self, event: AstrMessageEvent, keyword: str = ""):
        """/查歌 <关键词> 按官方曲名或别名搜索曲库（别名无需令牌）"""
        keyword = (keyword or "").strip()
        if not keyword:
            yield event.plain_result("用法：/查歌 <曲名或别名>，例如 /查歌 狂乱 或 /查歌 水鱼")
            return
        try:
            client = self._client()
            song_data = await asyncio.to_thread(client.get_song_list)
            alias_list = await asyncio.to_thread(client.get_alias_list)
        except LXNSError as e:
            yield event.plain_result(f"🐷 曲库查询失败：{e}")
            return

        songs = song_data.get("songs", [])
        kw = keyword.lower()

        # 1. 官方曲名子串匹配
        hits = [s for s in songs if kw in s.get("title", "").lower()]

        # 2. 别名匹配（精确优先，其次包含），命中的别名用于展示
        alias_map = {a["song_id"]: a.get("aliases", []) for a in alias_list}
        alias_hits = {}  # song_id -> 命中的别名
        exact = [sid for sid, aliases in alias_map.items() if keyword in aliases]
        fuzzy = [
            sid
            for sid, aliases in alias_map.items()
            if sid not in exact and any(kw in al.lower() for al in aliases)
        ]
        songs_by_id = {s.get("id"): s for s in songs}
        for sid in exact + fuzzy:
            if sid in songs_by_id and sid not in {s.get("id") for s in hits}:
                alias_hits[sid] = next(al for al in alias_map[sid] if keyword in al)
                hits.append(songs_by_id[sid])

        hits = hits[:8]
        if not hits:
            yield event.plain_result(
                f"没找到带「{keyword}」的曲子（支持官方曲名与别名，曲库缓存每天更新）"
            )
            return

        # 唯一命中 → 直接出详情卡
        if len(hits) == 1:
            async for r in self._song_card(event, hits[0], song_data):
                yield r
            return

        lines = []
        for s in hits:
            diffs = s.get("difficulties", {})
            lv = []
            for key, tag in (("standard", "MAS"), ("dx", "DX")):
                arr = diffs.get(key) or []
                if arr:
                    last = arr[-1].get("level", "?")
                    lv.append(f"{tag}{last}")
            via = f"（别名「{alias_hits[s['id']]}」）" if s.get("id") in alias_hits else ""
            lines.append(
                f"  [{s.get('id')}] {s.get('title')} - {s.get('artist', '?')} "
                f"({'/'.join(lv)}){via}"
            )
        yield event.plain_result(
            "🎼 查到这些（/歌曲 <编号> 看详情）：\n" + "\n".join(lines)
        )

    async def _song_card(self, event: AstrMessageEvent, song: dict, song_data: dict):
        """渲染并发送歌曲详情卡。"""
        version_names = {
            v.get("version"): v.get("title") for v in song_data.get("versions", [])
        }
        genre_names = {
            g.get("genre"): g.get("title") for g in song_data.get("genres", [])
        }
        out_dir = Path(PLUGIN_DIR) / "render_cache"
        out_dir.mkdir(exist_ok=True)
        out = out_dir / f"song_{song.get('id')}.png"
        try:
            import render as b50render  # noqa: PLC0415

            await b50render.render_song_png_async(
                song, version_names, genre_names, out
            )
            yield event.image_result(str(out))
        except Exception as e:  # 渲染兜底：回退文字版
            diffs = song.get("difficulties", {})
            lv = "/".join(
                f"{c.get('level')}" for k in ("standard", "dx") for c in (diffs.get(k) or [])
            )
            yield event.plain_result(
                f"[{song.get('id')}] {song.get('title')} - {song.get('artist')}\n"
                f"难度: {lv}\n(图片渲染失败已回退: {type(e).__name__}: {e})"
            )

    @filter.command("来首")
    async def random_song(self, event: AstrMessageEvent, spec: str = ""):
        """/来首 [谱面][难度] 随机抽一首歌，如 /来首、/来首 13+、/来首 mas13"""
        spec = (spec or "").strip().lower()
        want_idx, want_lv = None, None
        if spec:
            m = re.fullmatch(r"(bas|adv|exp|mas|rem|basic|advanced|expert|master|remaster)?(\d{1,2}\+?)?", spec)
            if not m or (not m.group(1) and not m.group(2)):
                yield event.plain_result(
                    "用法：/来首 [谱面][难度]\n"
                    "例如：/来首（全随机）、/来首 13、/来首 13+、/来首 mas13、/来首 exp14"
                )
                return
            if m.group(1):
                want_idx = DIFF_ABBR[m.group(1)]
            if m.group(2):
                want_lv = m.group(2)

        try:
            song_data = await asyncio.to_thread(self._client().get_song_list)
        except LXNSError as e:
            yield event.plain_result(f"🐷 曲库查询失败：{e}")
            return

        # 收集所有符合条件谱面（standard/dx 各 5 个难度，逐一过筛）
        candidates = []
        for s in song_data.get("songs", []):
            diffs = s.get("difficulties", {})
            for type_key, type_name in (("standard", "标准"), ("dx", "DX")):
                for idx, chart in enumerate(diffs.get(type_key) or []):
                    if want_idx is not None and idx != want_idx:
                        continue
                    if want_lv and chart.get("level") != want_lv:
                        continue
                    candidates.append((s, type_key, type_name, idx, chart))

        if not candidates:
            yield event.plain_result(
                f"曲库里没有符合「{spec}」的谱面（难度写 7~15，谱面可加 bas/adv/exp/mas/rem）"
            )
            return

        song, type_key, type_name, idx, chart = random.choice(candidates)
        lv_value = chart.get("level_value")
        lv_text = f"{DIFF_NAMES[idx]} {chart.get('level', '?')}"
        if lv_value:
            lv_text += f"（定数 {lv_value:.1f}）"
        yield event.plain_result(
            "🎲 抽中了！\n"
            f"[{song.get('id')}] {song.get('title')} - {song.get('artist', '?')}\n"
            f"谱面: {type_name} / {lv_text}\n"
            f"用 /歌曲 {song.get('id')} 看详情卡"
        )

    @filter.command("吃分")
    async def eat_rating(self, event: AstrMessageEvent, qq: str = ""):
        """/吃分 [QQ号] B50 挖潜：推荐当前版本涨分最快的谱"""
        qq = self._resolve_qq(event, qq)
        if self.token_empty and not _load_token():
            yield event.plain_result("开发者令牌还没配置，等猪主人填好就能查啦")
            return
        try:
            client = self._client()
            player = await asyncio.to_thread(client.get_player_by_qq, qq)
            friend_code = str(player.get("friend_code", ""))
            bests = await asyncio.to_thread(client.get_bests, friend_code)
            song_data = await asyncio.to_thread(client.get_song_list)
        except LXNSError as e:
            yield event.plain_result(f"🐷 查分失败：{e}")
            return

        songs_by_id = {s.get("id"): s for s in song_data.get("songs", [])}
        rows = []
        for sc in (bests.get("standard") or []) + (bests.get("dx") or []):
            song = songs_by_id.get(sc.get("id"))
            if not song:
                continue
            charts = (song.get("difficulties") or {}).get(sc.get("type")) or []
            li = sc.get("level_index", 0)
            if li >= len(charts) or not charts[li].get("level_value"):
                continue
            lv = charts[li]["level_value"]
            ach = sc.get("achievements", 0)
            cur_ra = sc.get("dx_rating") or 0
            gap = ra_calc.max_ra(lv) - cur_ra
            if gap <= 0.05:  # 已满档/误差抹平
                continue
            rows.append(
                (gap, sc.get("song_name", "?"), DIFF_NAMES[li], lv, ach, cur_ra)
            )

        if not rows:
            yield event.plain_result(
                f"{player.get('name', '你')} 的 B50 已经全是满档，本猪无分可安排——去开新谱吧"
            )
            return

        rows.sort(key=lambda r: -r[0])
        top = rows[:8]
        total = sum(r[0] for r in rows)
        lines = ["🐷 涨分安排（B50 内挖潜，目标 SSS+ 100.5%）"]
        for i, (gap, name, diff, lv, ach, cur) in enumerate(top, 1):
            lines.append(
                f"{i}. {name} {diff} 定数{lv}\n"
                f"   当前 {ach:.4f}%（{cur:.1f} RA）→ 满档可得 "
                f"{ra_calc.max_ra(lv):.1f}，+{gap:.1f}"
            )
        lines.append(f"\n全部吃满预计 +{total:.1f} RA（共 {len(rows)} 首有肉）")
        yield event.plain_result("\n".join(lines))

    @filter.command("歌曲")
    async def song_detail(self, event: AstrMessageEvent, song_id: str = ""):
        """/歌曲 <编号> 查看歌曲详情卡"""
        song_id = (song_id or "").strip()
        if not song_id.isdigit():
            yield event.plain_result("用法：/歌曲 <曲目编号>，编号可先用 /查歌 查到")
            return
        try:
            client = self._client()
            song_data = await asyncio.to_thread(client.get_song_list)
        except LXNSError as e:
            yield event.plain_result(f"🐷 曲库查询失败：{e}")
            return
        songs_by_id = {s.get("id"): s for s in song_data.get("songs", [])}
        song = songs_by_id.get(int(song_id))
        if not song:
            yield event.plain_result(f"曲库里没有编号 {song_id} 的曲子")
            return
        async for r in self._song_card(event, song, song_data):
            yield r
