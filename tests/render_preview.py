"""本地渲染预览：用测试数据出一张 B50 图（不碰服务器）。"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import render  # noqa: E402

player = {
    "name": "Issac",
    "rating": 14723,
    "course_rank": 8,
    "upload_time": "2026-10-15T14:00:00",
}
bests = json.loads((REPO / "tests/.bests_fixture.json").read_text(encoding="utf-8"))
song_data = json.loads((REPO / "tests/.song_cache.json").read_text(encoding="utf-8"))

out = Path("/tmp/preview_b50.png")
render.render_png(player, bests, out, song_data=song_data)
print("渲染完成:", out)
