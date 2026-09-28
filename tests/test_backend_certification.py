import json
from pathlib import Path

import pytest

from starcraft_ai.data.backend_compare import BackendComparisonPolicy
from starcraft_ai.data.certification import (
    create_backend_certificate,
    load_backend_certificate,
    validate_backend_certificate,
    write_backend_certificate,
)


FIXTURE = Path("tests/fixtures/transitions_v1.jsonl")
REPLAY_SHA = "a" * 64
BACKEND_SHA = "b" * 40


def test_certificate_round_trip(tmp_path: Path) -> None:
    certificate = create_backend_certificate(
        FIXTURE,
        FIXTURE,
        replay_sha256=REPLAY_SHA,
        candidate_backend="test-backend",
        candidate_backend_commit=BACKEND_SHA,
        policy=BackendComparisonPolicy(min_aligned_actions=1),
    )
    path = tmp_path / "certificate.json"
    write_backend_certificate(path, certificate)

    loaded = load_backend_certificate(path)
    assert loaded.certificate_id == certificate.certificate_id
    assert loaded.comparison["promotion_eligible"] is True


def test_tampered_certificate_is_rejected() -> None:
    certificate = create_backend_certificate(
        FIXTURE,
        FIXTURE,
        replay_sha256=REPLAY_SHA,
        candidate_backend="test-backend",
        candidate_backend_commit=BACKEND_SHA,
        policy=BackendComparisonPolicy(min_aligned_actions=1),
    )
    payload = certificate.to_dict()
    payload["comparison"]["unit_position_mae"] = 999.0

    with pytest.raises(ValueError, match="promotion policy"):
        validate_backend_certificate(payload)


def test_repository_certificates_validate() -> None:
    for path in sorted(Path("data/certifications").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        validate_backend_certificate(payload)
