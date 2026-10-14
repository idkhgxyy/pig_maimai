"""astrbot.api.message_components 桩。"""


class Plain(str):
    def __new__(cls, text):
        obj = super().__new__(cls, text)
        obj.text = text
        return obj


class Image:
    def __init__(self, url=""):
        self.url = url

    @classmethod
    def fromURL(cls, url):
        return cls(url=url)

    @classmethod
    def fromFileSystem(cls, path):
        return cls(url=str(path))


class At:
    def __init__(self, qq=""):
        self.qq = qq
