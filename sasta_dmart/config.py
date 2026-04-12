from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


VALID_RUNTIME_ROLES = {"pi", "laptop"}


@dataclass(frozen=True)
class RuntimeConfig:
    firebase_db_url: str
    firebase_service_account_path: str
    public_claim_base_url: str
    laptop_dashboard_base_url: str
    pi_node_name: str


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required configuration: {name}. "
            "Set it in the environment before starting the app."
        )
    return value


def _normalize_base_url(value: str, name: str) -> str:
    normalized = value.rstrip("/")
    if not normalized.startswith(("http://", "https://")):
        raise RuntimeError(
            f"Invalid {name}: expected an absolute http(s) URL, got {value!r}."
        )
    return normalized


def load_runtime_config(role: str) -> RuntimeConfig:
    if role not in VALID_RUNTIME_ROLES:
        raise RuntimeError(
            f"Unknown runtime role {role!r}. Expected one of {sorted(VALID_RUNTIME_ROLES)}."
        )

    firebase_db_url = _require_env("FIREBASE_DB_URL")
    firebase_service_account_path = _require_env("FIREBASE_SERVICE_ACCOUNT_PATH")
    public_claim_base_url = _normalize_base_url(
        _require_env("PUBLIC_CLAIM_BASE_URL"),
        "PUBLIC_CLAIM_BASE_URL",
    )
    laptop_dashboard_base_url = _normalize_base_url(
        _require_env("LAPTOP_DASHBOARD_BASE_URL"),
        "LAPTOP_DASHBOARD_BASE_URL",
    )
    pi_node_name = _require_env("PI_NODE_NAME")

    service_account_path = Path(firebase_service_account_path).expanduser()
    if not service_account_path.exists():
        raise RuntimeError(
            "FIREBASE_SERVICE_ACCOUNT_PATH points to a file that does not exist: "
            f"{service_account_path}"
        )

    return RuntimeConfig(
        firebase_db_url=firebase_db_url,
        firebase_service_account_path=str(service_account_path),
        public_claim_base_url=public_claim_base_url,
        laptop_dashboard_base_url=laptop_dashboard_base_url,
        pi_node_name=pi_node_name,
    )
