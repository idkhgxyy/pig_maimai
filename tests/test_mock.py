"""pig_maimai mock 测试：不依赖真实 QQ 登录和 AstrBot 框架。

原理：
- tests/stub/astrbot 提供框架桩，让 main.py 可在框架外 import；
- MockEvent 模拟消息事件，收集插件 yield 出来的结果；
- 曲库数据第一次拉取后落盘缓存 24h（tests/.song_cache.json），
  之后重复跑测试零 API 请求，不骚扰落雪服务器。

运行： .venv/bin/python tests/test_mock.py
"""

import asyncio
import json
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STUB_DIR = Path(__file__).resolve().parent / "stub"
SONG_CACHE = Path(__file__).resolve().parent / ".song_cache.json"

sys.path.insert(0, str(STUB_DIR))  # 必须在 import main 之前，抢在真框架前面
sys.path.insert(0, str(REPO_ROOT))

import main as plugin_main  # noqa: E402
from lxns import LxnsClient  # noqa: E402


class MockEvent:
    """模拟 AstrMessageEvent：只实现插件用到的接口，结果记进 self.results。"""

    def __init__(self, sender_id: str = "1760468630"):
        self.sender_id = sender_id
        self.results = []

    def get_sender_id(self) -> str:
        return self.sender_id

    def is_private_chat(self) -> bool:
        return False

    def plain_result(self, text: str):
        return ("plain", text)

    def image_result(self, path: str):
        return ("image", str(path))

    def chain_result(self, chain):
        return ("chain", chain)


async def collect(coro_gen) -> list:
    return [r async for r in coro_gen]


def make_plugin() -> plugin_main.PigMaimaiPlugin:
    plugin = plugin_main.PigMaimaiPlugin.__new__(plugin_main.PigMaimaiPlugin)
    plugin.client = LxnsClient(token="", cache_dir=str(REPO_ROOT))
    plugin.token_empty = True

    # 曲库落盘缓存：24h 内重复跑测试不发任何 API 请求
    def cached_song_list(force: bool = False) -> dict:
        if not force and SONG_CACHE.exists():
            age = time.time() - SONG_CACHE.stat().st_mtime
            if age < 86400:
                return json.loads(SONG_CACHE.read_text(encoding="utf-8"))
        data = LxnsClient.get_song_list(plugin.client, force=force)
        SONG_CACHE.write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
        return data

    plugin.client.get_song_list = cached_song_list
    return plugin


# ---------- 断言工具 ----------

PASS = []
FAIL = []


def check(name: str, cond: bool, detail: str = ""):
    if cond:
        PASS.append(name)
        print(f"  ✓ {name}")
    else:
        FAIL.append(name)
        print(f"  ✗ {name}  {detail}")


def texts(results: list) -> str:
    """把结果列表里的纯文本拼起来（图片结果记为 [图片]）。"""
    parts = []
    for kind, payload in results:
        parts.append(payload if kind == "plain" else f"[{kind}]")
    return "\n".join(parts)


LEVEL_RE = re.compile(r"谱面: (标准|DX) / (\S+) (\d+\+?)")


# ---------- 测试用例 ----------

async def test_random_song(plugin):
    print("\n[/来首] 随机选曲")
    ev = MockEvent()
    res = await collect(plugin.random_song(ev, ""))
    t = texts(res)
    check("无参数能抽到歌", "抽中了" in t, t)
    m = LEVEL_RE.search(t)
    check("输出含谱面行", bool(m), t)

    for spec, want_level, want_diff in [
        ("13", "13", None),
        ("13+", "13+", None),
        ("mas13", None, "MAS"),
        ("exp13", "13", "EXP"),
    ]:
        ev = MockEvent()
        res = await collect(plugin.random_song(ev, spec))
        t = texts(res)
        m = LEVEL_RE.search(t)
        ok = bool(m)
        if ok and want_level is not None:
            ok = m.group(3) == want_level
        if ok and want_diff is not None:
            ok = m.group(2) == want_diff
        check(f"/来首 {spec} 规格正确", ok, t)

    # 非法参数 → 用法提示
    ev = MockEvent()
    res = await collect(plugin.random_song(ev, "哈哈"))
    check("非法参数给用法", "用法" in texts(res), texts(res))

    # 不存在的谱面 → 空结果提示
    ev = MockEvent()
    res = await collect(plugin.random_song(ev, "bas15"))
    check("不存在的谱面给提示", "没有符合" in texts(res), texts(res))

    # 隐私红线：任何输出不得出现好友码
    check("无好友码泄漏", "friend_code" not in t and "好友码" not in t)


async def test_search_song(plugin):
    print("\n[/查歌] 别名与曲名搜索")
    ev = MockEvent()
    res = await collect(plugin.search_song(ev, "海底譚"))
    t = texts(res)
    check("唯一命中出详情（图或回退文字）",
          "417" in t or "[image]" in t or "海底譚" in t, t)

    ev = MockEvent()
    res = await collect(plugin.search_song(ev, "zzz不存在的曲子zzz"))
    check("搜不到给提示", "没找到" in texts(res), texts(res))


async def test_song_detail(plugin):
    print("\n[/歌曲] 详情查证")
    ev = MockEvent()
    res = await collect(plugin.song_detail(ev, "999999"))
    check("无效编号给提示", "没有编号" in texts(res), texts(res))


async def main():
    print("=== pig_maimai mock 测试 ===")
    plugin = make_plugin()
    await test_random_song(plugin)
    await test_search_song(plugin)
    await test_song_detail(plugin)

    print(f"\n结果: {len(PASS)} 通过, {len(FAIL)} 失败")
    if FAIL:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
