import pytest

from wechat_reply_agent.adapters.wechat.mac_ax import MacAXAdapter
from wechat_reply_agent.adapters.wechat.profile import AXProfile
from wechat_reply_agent.config import Settings


class Bridge:
    def __init__(self):
        self.nodes = {
            "root": {"AXWindows": ["window"]},
            "window": {"AXMinimized": False},
            "session": {"AXRole": "AXStaticText", "AXIdentifier": "session_item_Test A"},
            "title": {
                "AXRole": "AXStaticText",
                "AXIdentifier": "big_title_line_h_view",
                "AXValue": "Test A",
            },
            "input": {
                "AXRole": "AXTextArea",
                "AXIdentifier": "chat_input_field",
                "AXValue": "",
                "AXFocused": True,
            },
            "messages": {"AXRole": "AXList", "AXTitle": "Messages", "AXChildren": ["m1", "m2"]},
            "m1": {"AXValue": "你好"},
            "m2": {"AXValue": "你好"},
        }
        self.keys = 0
        self.writes = 0
        self.available = True
        self.after_write = None
        self.key_error = False

    def status(self):
        return {
            "accessibility": self.available,
            "screen_recording": self.available,
            "wechat_running": self.available,
            "session_unlocked": self.available,
        }

    def root(self):
        from wechat_reply_agent.adapters.wechat.base import AdapterError

        if not self.available:
            raise AdapterError("permission_app_or_session_unavailable")
        return "root"

    def get(self, node, key):
        return self.nodes[node].get(key)

    def matches(self, root, **attrs):
        return [k for k, v in self.nodes.items() if all(v.get(a) == b for a, b in attrs.items())]

    def set_text(self, node, text):
        self.writes += 1
        self.nodes[node]["AXValue"] = text
        if self.after_write:
            self.after_write(self)

    def press_return(self):
        self.keys += 1
        if self.key_error:
            raise RuntimeError("private error must never escape")

    def bounds(self, node):
        return (0, 0), (120, 40)

    def screenshot(self, node):
        return Pixels("both"), (0, 0)


class Pixels:
    width, height = 120, 40

    def __init__(self, side):
        self.side = side

    def crop(self, box):
        cropped = Pixels(self.side)
        cropped.width, cropped.height = box[2] - box[0], box[3] - box[1]
        cropped.white = (
            self.side == "both"
            or self.side == "left"
            and box[0] < 60
            or self.side == "right"
            and box[0] > 60
        )
        return cropped

    def convert(self, _):
        return self

    def getdata(self):
        return [(255, 255, 255) if self.white else (0, 0, 0)] * (self.width * self.height)


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        wechat_adapter="mac_ax",
        wechat_allowlist=["a", "b"],
        send_mode="live",
        data_dir=tmp_path,
        wechat_account_ref="local-account",
    )


@pytest.fixture
def profile():
    return AXProfile(
        account_ref="local-account",
        account_confirmed=True,
        wechat_version="synthetic",
        distribution="offline",
        language="en",
        contacts=[
            {
                "alias": "a",
                "title": "Test A",
                "local_conversation_id": "c-a",
                "single_chat_confirmed": True,
            }
        ],
    )


@pytest.fixture
def bridge():
    return Bridge()


@pytest.fixture
def adapter(settings, profile, bridge):
    return MacAXAdapter(settings, profile, bridge)
