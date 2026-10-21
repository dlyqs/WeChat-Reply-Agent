import pytest

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.adapters.wechat.vision_diagnostic import OCRLine, select_target_panel


def line(text="Test target", x=400, y=30, confidence=1):
    return OCRLine(text=text, confidence=confidence, x=x, y=y, width=120, height=20)


def test_exact_title_excludes_sidebar_header_and_input():
    data = [
        line(),
        line("sidebar private", x=100, y=160),
        line("header", y=60),
        line("message", y=150),
        line("draft", y=580),
    ]
    result = select_target_panel(data, "Test target", 1000, 700)
    assert [row["text"] for row in result["observations"]] == ["message"]
    assert result["direction"] == "unknown" and result["sending_supported"] is False


@pytest.mark.parametrize(
    "data",
    [
        [],
        [line(x=100)],
        [line(confidence=0.8)],
        [line(), line(x=550)],
        [line("Test target (2)")],
        [line(y=300)],
    ],
)
def test_missing_ambiguous_sidebar_or_low_confidence_title_fails_closed(data):
    with pytest.raises(AdapterError, match="vision_title_missing_or_ambiguous"):
        select_target_panel(data, "Test target", 1000, 700)


def test_narrow_window_is_not_guessed():
    with pytest.raises(AdapterError, match="vision_window_too_small"):
        select_target_panel([line()], "Test target", 300, 700)
