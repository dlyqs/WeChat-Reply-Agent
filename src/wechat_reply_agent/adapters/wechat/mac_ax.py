"""G1-only AX candidate. Never activates, searches, clicks or scrolls WeChat.

AX traversal/identifiers and pixel classification adapted from WeChat-MCP,
MIT, Copyright (c) 2025 Banghao Chi. See THIRD_PARTY_NOTICES.md.
Native APIs load only when the user explicitly executes a real probe.
"""

import platform
from typing import Any
from uuid import uuid4

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.adapters.wechat.profile import AXProfile
from wechat_reply_agent.config import Settings
from wechat_reply_agent.domain.messages import (
    AdapterCapabilities,
    ConversationRef,
    Direction,
    Health,
    InboundEvent,
    SendIntent,
    SendResult,
)


def classify_direction(image, origin, position, size) -> Direction:
    """Upstream band sampling, deliberately heuristic (confidence 0.7).

    No screenshot is persisted. Non-text/system rows still require human G1 review.
    """
    x, y = position[0] - origin[0], position[1] - origin[1]
    w, h = size
    band = min(40, h)
    top = y + h / 2 - band / 2
    width = min(100, w / 3)

    def sample(left):
        box = (
            max(0, int(left)),
            max(0, int(top)),
            min(image.width, int(left + width)),
            min(image.height, int(top + band)),
        )
        if box[2] <= box[0] or box[3] <= box[1]:
            return 0, 0
        crop = image.crop(box).convert("RGB")
        colored = sum(
            1
            for r, g, b in crop.getdata()
            if (r + g + b) / 3 >= 20 and ((r + g + b) / 3 > 40 or max(r, g, b) - min(r, g, b) > 10)
        )
        return colored, crop.width * crop.height

    left, la = sample(x + 5)
    right, ra = sample(x + w - 5 - width)
    signal = max(10, (la + ra) / 2 * 0.01)
    if left < signal and right < signal:
        return Direction.UNKNOWN
    if right > left * 1.5:
        return Direction.OUTGOING
    if left > right * 1.5:
        return Direction.INCOMING
    return Direction.UNKNOWN


class NativeAX:
    """Small injectable bridge. Construction imports libraries, but never opens an app."""

    def __init__(self):
        if platform.system() != "Darwin":
            raise AdapterError("macos_required")
        try:
            import AppKit
            import ApplicationServices as AX
            import Quartz
        except ImportError as exc:
            raise AdapterError("mac_extra_not_installed") from exc
        self.appkit, self.ax, self.quartz = AppKit, AX, Quartz

    def get(self, element, key):
        err, value = self.ax.AXUIElementCopyAttributeValue(element, key, None)
        return value if err == 0 else None

    def walk(self, root):
        # Limit traversal: malformed/huge trees fail closed rather than recurse forever.
        stack, count = [(root, 0)], 0
        while stack:
            node, depth = stack.pop()
            count += 1
            if count > 10000 or depth > 80:
                raise AdapterError("ax_tree_limit")
            yield node
            stack.extend((child, depth + 1) for child in self.get(node, "AXChildren") or [])

    def matches(self, root, **attrs):
        return [n for n in self.walk(root) if all(self.get(n, k) == v for k, v in attrs.items())]

    def status(self):
        trusted = bool(self.ax.AXIsProcessTrusted())  # No prompt/options/system mutation.
        screen = bool(self.quartz.CGPreflightScreenCaptureAccess())
        apps = self.appkit.NSRunningApplication.runningApplicationsWithBundleIdentifier_(
            "com.tencent.xinWeChat"
        )
        session = self.quartz.CGSessionCopyCurrentDictionary() or {}
        unlocked = not bool(session.get("CGSSessionScreenIsLocked", False))
        unlocked = unlocked and bool(session.get("kCGSessionOnConsoleKey", False))
        return {
            "accessibility": trusted,
            "screen_recording": screen,
            "wechat_running": len(apps) == 1,
            "session_unlocked": unlocked,
        }

    def root(self):
        state = self.status()
        if not all(state.values()):
            raise AdapterError("permission_app_or_session_unavailable")
        apps = self.appkit.NSRunningApplication.runningApplicationsWithBundleIdentifier_(
            "com.tencent.xinWeChat"
        )
        app = apps[0]
        if not app.isActive():
            raise AdapterError("wechat_not_foreground")
        return self.ax.AXUIElementCreateApplication(app.processIdentifier())

    def bounds(self, node):
        result = []
        for key, kind in (
            ("AXPosition", self.ax.kAXValueCGPointType),
            ("AXSize", self.ax.kAXValueCGSizeType),
        ):
            value = self.get(node, key)
            if value is None:
                raise AdapterError("ax_bounds_missing")
            ok, pair = self.ax.AXValueGetValue(value, kind, None)
            if not ok:
                raise AdapterError("ax_bounds_invalid")
            result.append(tuple(pair))
        return result

    def screenshot(self, node):
        from PIL import ImageGrab

        (x, y), (w, h) = self.bounds(node)
        image = ImageGrab.grab(bbox=(int(x), int(y), int(x + w), int(y + h)))
        # Fail closed on an unexpected Retina scale rather than classify wrong coordinates.
        if image.size != (int(w), int(h)):
            raise AdapterError("screenshot_scale_mismatch")
        return image, (x, y)

    def set_text(self, node, text):
        if self.ax.AXUIElementSetAttributeValue(node, "AXValue", text) != 0:
            raise AdapterError("input_write_failed")

    def press_return(self):
        # The adapter marks the outcome unknown before/after this irreversible boundary.
        for down in (True, False):
            event = self.quartz.CGEventCreateKeyboardEvent(None, 36, down)
            if event is None:
                raise AdapterError("key_event_failed")
            self.quartz.CGEventPost(self.quartz.kCGHIDEventTap, event)


class MacAXAdapter:
    def __init__(self, settings: Settings, profile: AXProfile | None = None, bridge: Any = None):
        self.settings, self.profile = settings, profile
        self._bridge = bridge
        self._conversation: ConversationRef | None = None

    @property
    def bridge(self):
        if self._bridge is None:
            self._bridge = NativeAX()
        return self._bridge

    @property
    def capabilities(self):
        return AdapterCapabilities(profile=self.profile.name if self.profile else "unconfigured")

    def health(self) -> Health:
        env = {
            "os": platform.system(),
            "os_version": platform.mac_ver()[0],
            "architecture": platform.machine(),
        }
        if self.profile:
            env.update(
                wechat_version=self.profile.wechat_version,
                distribution=self.profile.distribution,
                language=self.profile.language,
                version_source="user_declared_not_detected",
            )
        try:
            state = self.bridge.status()
            env.update(state)
            ready = all(state.values())
            reason = "permissions_available_profile_unverified" if ready else "permissions_or_app"
            # Doctor checks availability; does not activate WeChat or inspect chat text.
            return Health(
                healthy=ready, reason=reason, environment=env, capabilities=self.capabilities
            )
        except AdapterError as exc:
            return Health(
                healthy=False, reason=str(exc), environment=env, capabilities=self.capabilities
            )
        except Exception:
            return Health(
                healthy=False,
                reason="native_diagnostic_failed",
                environment=env,
                capabilities=self.capabilities,
            )

    def _window(self):
        root = self.bridge.root()
        windows = self.bridge.get(root, "AXWindows") or []
        if len(windows) != 1 or self.bridge.get(windows[0], "AXMinimized") is not False:
            raise AdapterError("single_visible_window_required")
        return windows[0]

    def _one(self, root, **attrs):
        nodes = self.bridge.matches(root, **attrs)
        if len(nodes) != 1:
            raise AdapterError("ax_control_missing_or_ambiguous")
        return nodes[0]

    def resolve_conversation(self, alias: str) -> ConversationRef:
        p = self.profile
        if alias not in self.settings.wechat_allowlist:
            raise AdapterError("contact_not_allowlisted")
        if (
            p is None
            or not p.account_confirmed
            or p.account_ref != self.settings.wechat_account_ref
        ):
            raise AdapterError("account_binding_unconfirmed")
        bindings = [c for c in p.contacts if c.alias == alias and c.single_chat_confirmed]
        if len(bindings) != 1:
            raise AdapterError("contact_binding_unconfirmed")
        binding = bindings[0]
        window = self._window()
        # Duplicate session titles are rejected, not collapsed into a dictionary.
        self._one(window, AXRole="AXStaticText", AXIdentifier="session_item_" + binding.title)
        title = self._one(window, AXRole="AXStaticText", AXIdentifier=p.title_identifier)
        if (
            self.bridge.get(title, "AXValue") or self.bridge.get(title, "AXTitle")
        ) != binding.title:
            raise AdapterError("current_chat_mismatch")
        ref = ConversationRef(
            account_ref=p.account_ref,
            conversation_id=binding.local_conversation_id,
            contact_alias=alias,
            profile=p.name,
            confidence=1,
            identity_basis="user-bound unique visible title; local ID, not wxid",
        )
        self._conversation = ref
        return ref

    def poll_events(self, cursor=None):
        if self._conversation is None:
            raise AdapterError("resolve_conversation_first")
        ref = self.resolve_conversation(self._conversation.contact_alias)
        window = self._window()
        listing = self._one(window, AXRole="AXList", AXTitle=self.profile.messages_title)
        image, origin = self.bridge.screenshot(listing)
        observation = str(uuid4())
        events = []
        for index, child in enumerate(self.bridge.get(listing, "AXChildren") or []):
            text = self.bridge.get(child, "AXValue") or self.bridge.get(child, "AXTitle")
            if not isinstance(text, str) or not text.strip():
                continue
            try:
                position, size = self.bridge.bounds(child)
                direction = classify_direction(image, origin, position, size)
            except AdapterError:
                direction = Direction.UNKNOWN
            events.append(
                InboundEvent(
                    conversation_id=ref.conversation_id,
                    occurrence_ref=f"{observation}:{index}",
                    direction=direction,
                    text=text,
                    confidence=0.7 if direction != "unknown" else 0,
                )
            )
        # Recheck after capture. Never attribute a switched frame to the old conversation.
        if self.resolve_conversation(ref.contact_alias) != ref:
            raise AdapterError("chat_changed_during_read")
        # Snapshot cursor only: no history alignment/dedup claims in Phase 1.
        return events, observation

    def send_text(self, intent: SendIntent) -> SendResult:
        if intent.mode != "live" or self.settings.send_mode != "live":
            return SendResult(outcome="not_sent", basis="dry_run")
        attempted = False
        try:
            ref = self.resolve_conversation(intent.conversation.contact_alias)
            if ref != intent.conversation:
                raise AdapterError("identity_changed")
            window = self._window()
            field = self._one(
                window, AXRole="AXTextArea", AXIdentifier=self.profile.input_identifier
            )
            if self.bridge.get(field, "AXValue") != "":
                raise AdapterError("existing_draft_preserved")
            if self.bridge.get(field, "AXFocused") is not True:
                raise AdapterError("input_not_focused")
            self.bridge.set_text(field, intent.reply_text)
            # Recheck after mutation, immediately before the irreversible key event.
            self.resolve_conversation(ref.contact_alias)
            if self._window() != window:
                raise AdapterError("window_changed")
            if self.bridge.get(field, "AXFocused") is not True:
                raise AdapterError("input_lost_focus")
            if self.bridge.get(field, "AXValue") != intent.reply_text:
                raise AdapterError("input_verification_failed")
            attempted = True
            self.bridge.press_return()
            return SendResult(outcome="unknown", basis="return_attempted_not_delivery_confirmation")
        except AdapterError as exc:
            return SendResult(
                outcome="unknown" if attempted else "not_sent", basis="send_guard", error=str(exc)
            )
        except Exception:
            return SendResult(
                outcome="unknown" if attempted else "not_sent",
                basis="native_failure",
                error="native_operation_failed",
            )
