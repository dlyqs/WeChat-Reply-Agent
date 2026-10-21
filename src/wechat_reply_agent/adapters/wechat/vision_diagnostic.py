"""Read-only candidate feasibility probe; no mouse, keyboard or send implementation.

Vision request/bounding-box conversion adapted from wechat-mac-rpa at
0c129a5bb255a6640694c73fcdf178e7c3dda49b, MIT, Copyright (c) 2026
wechat-mac-rpa contributors. See THIRD_PARTY_NOTICES.md.
"""

from dataclasses import asdict, dataclass
from io import BytesIO

from wechat_reply_agent.adapters.wechat.base import AdapterError


@dataclass(frozen=True)
class OCRLine:
    text: str
    confidence: float
    x: float
    y: float
    width: float
    height: float


def recognize(image) -> list[OCRLine]:
    # Lazy native import: offline geometry tests never access the desktop.
    import Quartz
    import Vision
    from Foundation import NSData

    data = BytesIO()
    image.save(data, format="PNG")
    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLanguages_(["zh-Hans", "en-US"])
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(False)
    encoded = data.getvalue()
    native_data = NSData.dataWithBytes_length_(encoded, len(encoded))
    source = Quartz.CGImageSourceCreateWithData(native_data, None)
    cg_image = Quartz.CGImageSourceCreateImageAtIndex(source, 0, None) if source else None
    if cg_image is None:
        raise AdapterError("local_vision_image_decode_failed")
    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg_image, None)
    ok, error = handler.performRequests_error_([request], None)
    if not ok:
        raise AdapterError("local_vision_recognition_failed")
    lines = []
    for observation in request.results() or []:
        candidates = observation.topCandidates_(1)
        if not candidates:
            continue
        candidate = candidates[0]
        box = observation.boundingBox()
        lines.append(
            OCRLine(
                text=str(candidate.string()).strip(),
                confidence=float(candidate.confidence()),
                x=float(box.origin.x) * image.width,
                y=(1 - float(box.origin.y) - float(box.size.height)) * image.height,
                width=float(box.size.width) * image.width,
                height=float(box.size.height) * image.height,
            )
        )
    return sorted(lines, key=lambda line: (line.y, line.x))


def select_target_panel(lines: list[OCRLine], expected_title: str, width: int, height: int):
    """Diagnostic only: exact top-right title gate, never a send identity resolver."""
    if width < 600 or height < 400:
        raise AdapterError("vision_window_too_small")
    titles = [
        line
        for line in lines
        if line.text == expected_title
        and line.confidence >= 0.9
        and line.x >= width * 0.25
        and 0 <= line.y < height * 0.2
    ]
    if len(titles) != 1:
        raise AdapterError("vision_title_missing_or_ambiguous")
    title = titles[0]
    left = max(width * 0.25, title.x - 20)
    # Only provisional body observations, not messages or reliable sender directions.
    # Exclude the sidebar, title/header, and bottom input area from the private report.
    body = [
        asdict(line)
        for line in lines
        if line.x >= left
        and line.y >= title.y + title.height + 20
        and line.y + line.height < height * 0.78
    ]
    return {
        "title_matched": True,
        "title_confidence": title.confidence,
        "panel_left": left,
        "observations": body,
        "direction": "unknown",
        "sending_supported": False,
        "note": "OCR feasibility only; no bubble grouping, message dedup or sender claims",
    }


def capture_target(expected_title: str):
    import AppKit

    from wechat_reply_agent.adapters.wechat.mac_ax import NativeAX

    bridge = NativeAX()
    root = bridge.root()  # Requires permissions, foreground and unlocked session.
    windows = bridge.get(root, "AXWindows") or []
    if len(windows) != 1 or bridge.get(windows[0], "AXMinimized") is not False:
        raise AdapterError("single_visible_window_required")
    window = windows[0]
    image, _ = bridge.screenshot(window)
    lines = recognize(image)
    # Retain no screenshot or unrelated sidebar text; recheck foreground/window after OCR.
    current_root = bridge.root()
    if bridge.get(current_root, "AXWindows") != windows:
        raise AdapterError("window_changed_during_ocr")
    front = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
    if not front or front.bundleIdentifier() != "com.tencent.xinWeChat":
        raise AdapterError("wechat_not_foreground")
    return {
        "mode": "local_vision_diagnostic",
        "image_size": list(image.size),
        **select_target_panel(lines, expected_title, image.width, image.height),
    }
