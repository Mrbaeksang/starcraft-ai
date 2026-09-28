from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from starcraft_ai.data.backend_compare import BackendComparisonPolicy, compare_backends
from starcraft_ai.data.io import sha256_file

CERTIFICATE_SCHEMA_VERSION = 1


def _is_hex_digest(value: str, length: int) -> bool:
    return len(value) == length and all(ch in "0123456789abcdef" for ch in value.lower())


def _canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _certificate_id(payload_without_id: dict[str, Any]) -> str:
    digest = hashlib.sha256(_canonical_json(payload_without_id).encode("utf-8")).hexdigest()
    return f"bwapi-headless-v1-{digest[:20]}"


@dataclass(frozen=True, slots=True)
class BackendCertificateV1:
    schema_version: int
    certificate_id: str
    replay_sha256: str
    reference_backend: str
    reference_file_sha256: str
    candidate_backend: str
    candidate_backend_commit: str
    candidate_file_sha256: str
    policy: dict[str, Any]
    comparison: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _check_metrics(
    comparison: dict[str, Any],
    policy: BackendComparisonPolicy,
) -> list[str]:
    failures: list[str] = []

    checks = (
        (
            int(comparison["aligned_actions"]) >= policy.min_aligned_actions,
            "too few aligned actions",
        ),
        (
            float(comparison["reference_action_alignment"]) >= policy.min_action_alignment,
            "reference action alignment below threshold",
        ),
        (
            float(comparison["candidate_action_alignment"]) >= policy.min_action_alignment,
            "candidate action alignment below threshold",
        ),
        (
            float(comparison["actor_count_mae"]) <= policy.max_actor_count_mae,
            "actor-count MAE above threshold",
        ),
        (
            float(comparison["action_target_position_mae"])
            <= policy.max_action_target_position_mae,
            "action target-position MAE above threshold",
        ),
        (
            float(comparison["visible_unit_precision"]) >= policy.min_visible_unit_precision,
            "visible-unit precision below threshold",
        ),
        (
            float(comparison["visible_unit_recall"]) >= policy.min_visible_unit_recall,
            "visible-unit recall below threshold",
        ),
        (
            float(comparison["unit_position_mae"]) <= policy.max_unit_position_mae,
            "unit-position MAE above threshold",
        ),
        (
            float(comparison["unit_hp_mae"]) <= policy.max_unit_hp_mae,
            "unit HP MAE above threshold",
        ),
        (
            float(comparison["minerals_mae"]) <= policy.max_minerals_mae,
            "minerals MAE above threshold",
        ),
        (
            float(comparison["gas_mae"]) <= policy.max_gas_mae,
            "gas MAE above threshold",
        ),
        (
            float(comparison["supply_used_mae"]) <= policy.max_supply_used_mae,
            "supply-used MAE above threshold",
        ),
        (
            float(comparison["supply_total_mae"]) <= policy.max_supply_total_mae,
            "supply-total MAE above threshold",
        ),
        (
            float(comparison["state_frame_delta_mae"]) <= policy.max_state_frame_delta,
            "state-frame delta above threshold",
        ),
    )
    failures.extend(message for passed, message in checks if not passed)
    return failures


def create_backend_certificate(
    reference_path: Path,
    candidate_path: Path,
    *,
    replay_sha256: str,
    candidate_backend: str,
    candidate_backend_commit: str,
    policy: BackendComparisonPolicy | None = None,
) -> BackendCertificateV1:
    replay_sha256 = replay_sha256.lower()
    candidate_backend_commit = candidate_backend_commit.lower()
    if not _is_hex_digest(replay_sha256, 64):
        raise ValueError("replay_sha256 must be a 64-character hexadecimal digest")
    if not _is_hex_digest(candidate_backend_commit, 40):
        raise ValueError("candidate_backend_commit must be a 40-character git SHA")
    if not candidate_backend.strip():
        raise ValueError("candidate_backend must not be empty")

    active_policy = policy or BackendComparisonPolicy()
    comparison = compare_backends(reference_path, candidate_path, policy=active_policy)
    if not comparison.promotion_eligible:
        raise ValueError(
            "backend comparison did not pass promotion thresholds: "
            + "; ".join(comparison.promotion_failures)
        )

    payload_without_id: dict[str, Any] = {
        "schema_version": CERTIFICATE_SCHEMA_VERSION,
        "replay_sha256": replay_sha256,
        "reference_backend": "BWAPI 4.4.0 player-view replay",
        "reference_file_sha256": sha256_file(reference_path),
        "candidate_backend": candidate_backend,
        "candidate_backend_commit": candidate_backend_commit,
        "candidate_file_sha256": sha256_file(candidate_path),
        "policy": asdict(active_policy),
        "comparison": comparison.to_dict(),
    }
    return BackendCertificateV1(
        certificate_id=_certificate_id(payload_without_id),
        **payload_without_id,
    )


def validate_backend_certificate(payload: dict[str, Any]) -> BackendCertificateV1:
    expected = {
        "schema_version",
        "certificate_id",
        "replay_sha256",
        "reference_backend",
        "reference_file_sha256",
        "candidate_backend",
        "candidate_backend_commit",
        "candidate_file_sha256",
        "policy",
        "comparison",
    }
    unknown = set(payload) - expected
    missing = expected - set(payload)
    if unknown:
        raise ValueError(f"unknown certificate fields: {sorted(unknown)}")
    if missing:
        raise ValueError(f"missing certificate fields: {sorted(missing)}")
    if payload["schema_version"] != CERTIFICATE_SCHEMA_VERSION:
        raise ValueError("unsupported backend certificate schema_version")

    for field in ("replay_sha256", "reference_file_sha256", "candidate_file_sha256"):
        if not _is_hex_digest(str(payload[field]).lower(), 64):
            raise ValueError(f"{field} must be a 64-character hexadecimal digest")
    if not _is_hex_digest(str(payload["candidate_backend_commit"]).lower(), 40):
        raise ValueError("candidate_backend_commit must be a 40-character git SHA")

    try:
        policy = BackendComparisonPolicy(**dict(payload["policy"]))
    except TypeError as error:
        raise ValueError(f"invalid backend policy: {error}") from error

    comparison = dict(payload["comparison"])
    failures = _check_metrics(comparison, policy)
    if not bool(comparison.get("promotion_eligible")):
        failures.append("comparison is not marked promotion_eligible")
    if comparison.get("promotion_failures"):
        failures.append("comparison contains promotion_failures")
    if failures:
        raise ValueError("certificate metrics fail promotion policy: " + "; ".join(failures))

    without_id = {key: value for key, value in payload.items() if key != "certificate_id"}
    expected_id = _certificate_id(without_id)
    if payload["certificate_id"] != expected_id:
        raise ValueError("certificate_id does not match canonical certificate contents")

    return BackendCertificateV1(**payload)


def load_backend_certificate(path: Path) -> BackendCertificateV1:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("backend certificate must contain a JSON object")
    return validate_backend_certificate(payload)


def write_backend_certificate(path: Path, certificate: BackendCertificateV1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(certificate.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
