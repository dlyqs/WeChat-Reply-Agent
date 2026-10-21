"""Windows v4 identity compatibility and platform/report isolation without native imports."""

import hashlib
import json
from contextlib import closing
from types import SimpleNamespace

import pytest

from wechat_reply_agent.adapters.wechat.base import AdapterError
from wechat_reply_agent.adapters.wechat.replica import ReplicaAdapter
from wechat_reply_agent.adapters.wechat.replica_acceptance import require_runtime_acceptance
from wechat_reply_agent.adapters.wechat.replica_profile import ReplicaProfile
from wechat_reply_agent.cli import write_private
from wechat_reply_agent.config import Settings
from wechat_reply_agent.storage.database import Ledger
from wechat_reply_agent.storage.migrations import bind_identity


@pytest.fixture
def windows(tmp_path, monkeypatch):
    from wechat_reply_agent.adapters.wechat import replica_acceptance

    root = tmp_path / "client"
    source = root / "account/db_storage/message.db"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"source identity!")
    settings = Settings(_env_file=None, data_dir=tmp_path, wechat_account_ref="account")
    profile = ReplicaProfile(
        account_ref="account",
        account="account",
        self_username="self",
        account_generation="g1",
        db_root=root,
        account_confirmed=True,
        wechat_version="4.synthetic",
    )
    adapter = ReplicaAdapter(settings, profile)
    binding = adapter.runtime_binding()
    for phase in (1, 2):
        write_private(
            tmp_path / f"acceptance/phase-{phase}/report.json",
            {
                "plan_version": "v4",
                "foundation": "replica",
                f"g{phase}": "passed",
                "environment": {"wechat_version": "4.synthetic"},
                "evidence_mode": "synthetic",
            },
        )
    monkeypatch.setattr(
        replica_acceptance,
        "environment",
        lambda: {"platform": "Windows", "wechat_version": "4.synthetic"},
    )
    return settings, profile, binding


def test_windows_binding_matches_the_original_phase3_fingerprint(windows):
    settings, profile, binding = windows
    root = profile.db_root / profile.account / "db_storage"
    original = {
        "account_ref": profile.account_ref,
        "generation": profile.account_generation,
        "account": profile.account,
        "self": profile.self_username,
        "root": str(profile.db_root.resolve()),
        "databases": [
            (str(p.relative_to(root)), (p.stat().st_dev, p.stat().st_ino))
            for p in sorted(root.rglob("*.db"))
        ],
    }
    legacy = hashlib.sha256(json.dumps(original, sort_keys=True).encode()).hexdigest()
    assert binding.fingerprint == legacy
    with closing(Ledger(settings.data_dir / "prototype.sqlite3")) as ledger:
        bind_identity(ledger.db, legacy, profile.account_ref, profile.account_generation)
    before = [
        (settings.data_dir / f"acceptance/phase-{g}/report.json").read_bytes() for g in (1, 2)
    ]
    require_runtime_acceptance(settings, profile, binding)
    assert before == [
        (settings.data_dir / f"acceptance/phase-{g}/report.json").read_bytes() for g in (1, 2)
    ]


def test_copied_legacy_passed_report_without_ledger_identity_is_rejected(windows):
    with pytest.raises(AdapterError, match="windows_matching_acceptance_required"):
        require_runtime_acceptance(*windows)


@pytest.mark.parametrize(
    "wrong",
    [
        {"platform": "macOS"},
        {"foundation": "mac_db"},
        {"environment": {"wechat_version": "other"}},
        {"g1": "not_tested"},
    ],
)
def test_windows_original_reports_cannot_bypass_platform_version_or_status(windows, wrong):
    settings, profile, binding = windows
    with closing(Ledger(settings.data_dir / "prototype.sqlite3")) as ledger:
        bind_identity(ledger.db, binding.fingerprint)
    path = settings.data_dir / "acceptance/phase-1/report.json"
    write_private(path, json.loads(path.read_text()) | wrong)
    with pytest.raises(AdapterError, match="windows_matching_acceptance_required"):
        require_runtime_acceptance(settings, profile, binding)


def test_v5_windows_report_requires_revision_and_binding_fingerprint(windows):
    from wechat_reply_agent.adapters.wechat.replica_acceptance import REVISION

    settings, profile, binding = windows
    for phase in (1, 2):
        write_private(
            settings.data_dir / f"acceptance/windows/phase-{phase}/report.json",
            {
                "platform": "Windows",
                "plan_version": "v5",
                "foundation": "replica",
                "foundation_revision": REVISION,
                "wechat_version": profile.wechat_version,
                "binding_fingerprint": binding.fingerprint,
                f"g{phase}": "passed",
            },
        )
    require_runtime_acceptance(settings, profile, binding)
    path = settings.data_dir / "acceptance/windows/phase-2/report.json"
    write_private(path, json.loads(path.read_text()) | {"binding_fingerprint": "other"})
    with pytest.raises(AdapterError, match="windows_matching_acceptance_required"):
        require_runtime_acceptance(settings, profile, binding)


@pytest.mark.parametrize(
    "rows",
    [
        [],
        [
            {"username": "friend", "remark": "Unique", "nick_name": ""},
            {"username": "other", "remark": "Unique", "nick_name": ""},
        ],
        [{"username": "other", "remark": "Unique", "nick_name": ""}],
    ],
)
def test_mac_title_binding_rejects_renamed_duplicate_or_wrong_native_friend(rows):
    from wechat_reply_agent.adapters.wechat.mac_bridge import validate_contact_binding

    reader = SimpleNamespace(resolve=lambda name: rows)
    contact = SimpleNamespace(username="friend", title="Unique")
    with pytest.raises(AdapterError, match="title_ambiguous_or_changed"):
        validate_contact_binding(reader, contact)
