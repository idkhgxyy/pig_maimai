"""落雪咖啡屋 (maimai.lxns.net) API 客户端。

API 文档: https://maimai.lxns.net/docs/api/maimai
鉴权方式: 请求头直接携带 Authorization: <developer_token>（注意不是 Bearer 格式）
限流说明: 官方未公布配额，触发限流返回 429；曲库等资源接口要求勿频繁请求，
         故本客户端对曲库做了 24 小时内存缓存。
"""

import time

import requests

BASE_URL = "https://maimai.lxns.net/api/v0/maimai"


class LXNSError(Exception):
    """落雪 API 业务错误，message 可直接展示给用户。"""


class LxnsClient:
    def __init__(self, token: str = "", timeout: int = 15):
        self.token = (token or "").strip()
        self.timeout = timeout
        self._song_cache = None
        self._song_cache_time = 0.0

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
