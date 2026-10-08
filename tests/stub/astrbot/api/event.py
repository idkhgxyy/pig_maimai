"""astrbot.api 桩：让插件 main.py 能在框架外被 import。"""


class AstrMessageEvent:
    """占位类型，测试里用 MockEvent 代替。"""


class _Filter:
    """@filter.command / @filter.on_llm_request 的空实现：注册动作跳过，原函数透传。"""

    @staticmethod
    def command(name, **kwargs):
        def deco(func):
            return func

        return deco

    @staticmethod
    def on_llm_request(**kwargs):
        def deco(func):
            return func

        return deco

    @staticmethod
    def event_message_type(*args, **kwargs):
        def deco(func):
            return func

        return deco


filter = _Filter()
