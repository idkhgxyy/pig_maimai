"""落雪咖啡屋 (maimai.lxns.net) API 客户端。

API 文档: https://maimai.lxns.net/docs/api/maimai
鉴权方式: 请求头直接携带 Authorization: <developer_token>（注意不是 Bearer 格式）
限流说明: 官方未公布配额，触发限流返回 429；曲库/别名等资源接口要求勿频繁请求，
         故本客户端做了缓存：曲库 24h 内存缓存，别名落盘缓存 7 天，
         拉取失败时回退使用旧缓存文件，将对官方服务的请求压到最低。
"""

import json
import time
from pathlib import Path

import requests

BASE_URL = "https://maimai.lxns.net/api/v0/maimai"

ALIAS_REFRESH_SECONDS = 7 * 86400  # 别名库落盘缓存有效期：7 天


class LXNSError(Exception):
    """落雪 API 业务错误，message 可直接展示给用户。"""


class LxnsClient:
    def __init__(self, token: str = "", timeout: int = 15, cache_dir: str = None):
        self.token = (token or "").strip()
        self.timeout = timeout
        self._song_cache = None
        self._song_cache_time = 0.0
        self.cache_dir = Path(cache_dir) if cache_dir else None

    def _headers(self) -> dict:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = self.token
        return headers

    def _get(self, path: str):
        resp = requests.get(
            BASE_URL + path, headers=self._headers(), timeout=self.timeout
        )
        try:
            data = resp.json()
        except ValueError:
            raise LXNSError(f"落雪 API 返回非 JSON 响应 (HTTP {resp.status_code})")

        if isinstance(data, dict) and data.get("success") is False:
            code = data.get("code")
            message = data.get("message", "未知错误")
            if code == 401:
                raise LXNSError(
                    "鉴权失败：开发者令牌缺失或无效。请在插件 config.json 中填写令牌"
                )
            if code == 404:
                raise LXNSError(
                    "没有查到这个玩家——确认对方已在落雪（maimai.lxns.net）绑定该 QQ 号"
                )
            if code == 429:
                raise LXNSError("请求太频繁，触发了落雪限流，稍后再试")
            raise LXNSError(f"落雪 API 错误 {code}: {message}")

        # 部分端点返回 {"success": true, "data": {...}}，部分直接返回数据本身
        if (
            isinstance(data, dict)
            and data.get("success") is True
            and "data" in data
        ):
            return data["data"]
        return data

    # ---------- 玩家相关（需要开发者令牌） ----------

    def get_player_by_qq(self, qq: str) -> dict:
        """按 QQ 号查询玩家信息（玩家需在落雪设置里绑定过 QQ）。"""
        return self._get(f"/player/qq/{qq}")

    def get_bests(self, friend_code: str) -> dict:
        """按好友码查询 B50 成绩（标准 B30 + DX B15）。"""
        return self._get(f"/player/{friend_code}/bests")

    # ---------- 曲库（公开接口，带 24h 缓存） ----------

    def get_song_list(self, force: bool = False) -> dict:
        now = time.time()
        if self._song_cache is None or force or now - self._song_cache_time > 86400:
            self._song_cache = self._get("/song/list")
            self._song_cache_time = now
        return self._song_cache

    # ---------- 曲名别名（公开接口，落盘缓存 7 天，失败回退旧文件） ----------

    def get_alias_list(self, force: bool = False) -> list:
        """获取全量曲名别名列表：[{"song_id": int, "aliases": [str, ...]}, ...]

        缓存策略（对官方服务零压力）：
        1. 优先读本地缓存文件（7 天内有效）
        2. 过期/强制时才发一次网络请求，成功则覆盖缓存文件
        3. 网络失败时回退使用过期缓存（并向上标注数据可能过时）
        """
        cache_file = self.cache_dir / "alias_cache.json" if self.cache_dir else None

        def _read_file():
            if cache_file and cache_file.exists():
                try:
                    wrapper = json.loads(cache_file.read_text(encoding="utf-8"))
                    return wrapper.get("fetched_at", 0), wrapper.get("aliases", [])
                except Exception:
                    return 0, []
            return 0, []

        fetched_at, cached = _read_file()
        fresh = time.time() - fetched_at < ALIAS_REFRESH_SECONDS
        if cached and fresh and not force:
            return cached

        try:
            data = self._get("/alias/list")
            aliases = data.get("aliases", []) if isinstance(data, dict) else data
            if not aliases:
                raise LXNSError("别名接口返回空数据")
            if cache_file:
                cache_file.write_text(
                    json.dumps(
                        {"fetched_at": time.time(), "aliases": aliases},
                        ensure_ascii=False,
                    ),
                    encoding="utf-8",
                )
            return aliases
        except Exception:
            if cached:
                return cached  # 回退旧数据（可能过时）
            raise
