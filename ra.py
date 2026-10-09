"""maimai DX 单曲 Rating (RA) 计算（现行版公式）。

公式（已用真实成绩逆向验证，见 tests/test_mock.py）：

    单曲 RA = 定数 × 档位系数 × min(达成率, 100.5) / 100

与旧版公式的两点差异（旧版资料均已过时）：
- 达成率在档内连续生效：SSS 档打 100.4% 比 100.0% RA 更高，
  不再是"档内恒定、只有跨线才变"；
- SSS+ 档达成率按 100.5 封顶（打 101% 和 100.5% 同 RA）。

档位系数沿用经典分档线。低于最低档（62%）计 0。
"""

# (达成率下限, 档位系数)，从高到低
BANDS = [
    (100.5, 22.4),  # SSS+
    (100.0, 21.6),  # SSS
    (99.99, 21.4),  # SS+
    (99.5, 21.1),   # SS
    (99.0, 20.8),   # S+
    (98.99, 20.6),
    (98.0, 20.3),   # S
    (97.0, 19.25),  # AAA
    (94.0, 18.5),   # AA
    (92.0, 17.5),
    (90.0, 16.5),   # A
    (87.0, 15.2),
    (82.0, 13.6),
    (77.0, 12.0),
    (72.0, 10.4),
    (67.0, 8.8),
    (62.0, 7.1),
]

RATE_CAP = 100.5  # SSS+ 档达成率封顶
MAX_COEF = BANDS[0][1] * RATE_CAP / 100  # 满档等效系数 22.512


def single_ra(constant: float, achievements: float) -> float:
    """单曲 RA（浮点精确值；游戏内显示为向下取整）。"""
    coef = next((c for floor, c in BANDS if achievements >= floor), 0.0)
    if coef == 0.0:
        return 0.0
    return constant * coef * min(achievements, RATE_CAP) / 100


def max_ra(constant: float) -> float:
    """该定数谱面的 RA 上限（SSS+ 100.5%）。"""
    return constant * MAX_COEF


def next_band(achievements: float):
    """距当前达成率最近的上一档门槛，返回 (达成率线, 系数)；满档返回 None。"""
    for floor, c in reversed(BANDS):
        if achievements < floor:
            return floor, c
    return None


# 评级字符串（落雪 /scores 的 rate 字段）→ 达成率下限。
# 高档位（sssp~aaa）按官方评级线，低档位为近似值，仅用于估计"保底 RA"。
RANK_FLOORS = {
    "sssp": 100.5,
    "sss": 100.0,
    "ssp": 99.99,
    "ss": 99.5,
    "sp": 99.0,
    "s": 98.0,
    "aaa": 97.0,
    "aa": 94.0,
    "a": 90.0,
    "bbb": 87.0,
    "bb": 82.0,
    "b": 77.0,
    "c": 72.0,
    "d": 0.0,
}


def ra_from_rank(constant: float, rank: str) -> float:
    """按评级字符串估计 RA 下限（拿不到数值达成率时的替代品）。"""
    floor = RANK_FLOORS.get((rank or "").lower(), 0.0)
    return single_ra(constant, floor)
