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
import sys
from pathlib import Path

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register

# 保证能 import 同目录下的 lxns.py / render.py（不依赖插件系统的模块命名方式）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lxns import LXNSError, LxnsClient  # noqa: E402

PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))

# 难度序号 → 简称（level_index: 0=Basic 1=Advanced 2=Expert 3=Master 4=Re:Master）
DIFF_NAMES = ["BAS", "ADV", "EXP", "MAS", "ReM"]

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


@register("pig_maimai", "gxyy", "猪bot查分：落雪API舞萌DX查分/B50/查歌", "0.1.0")
class PigMaimaiPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.client = LxnsClient(token=_load_token())
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
        """/查歌 <关键词> 按曲名搜索曲库（无需令牌）"""
        keyword = (keyword or "").strip()
        if not keyword:
            yield event.plain_result("用法：/查歌 <曲名关键词>，例如 /查歌 狂乱")
            return
        try:
            song_data = await asyncio.to_thread(self._client().get_song_list)
            songs = song_data.get("songs", [])
        except LXNSError as e:
            yield event.plain_result(f"🐷 曲库查询失败：{e}")
            return
        kw = keyword.lower()
        hits = [s for s in songs if kw in s.get("title", "").lower()][:8]
        if not hits:
            yield event.plain_result(f"没找到带「{keyword}」的曲子（曲库缓存每天更新一次）")
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
            lines.append(f"  [{s.get('id')}] {s.get('title')} - {s.get('artist', '?')} ({'/'.join(lv)})")
        yield event.plain_result("🎼 查到这些：\n" + "\n".join(lines))
