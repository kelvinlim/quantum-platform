"""REDCap and Box stubs. Network calls are out of scope for Phase 1.

Contracts: INTEGRATIONS.md §4 (REDCap field dictionary) and §5 (Box paths).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REDCAP_PARTICIPANT_FIELDS = (
    "record_id",
    "eligible",
    "consent_status",
    "consent_date",
    "notes",
)

REDCAP_SESSION_FIELDS = (
    "session_id",
    "session_date",
    "session_datetime",
    "session_status",
    "operator",
    "protocol_version",
    "box_folder_path",
    "box_folder_id",
    "local_complete",
    "upload_status",
    "qc_ok",
    "session_notes",
)


@dataclass
class RedcapConfig:
    base_url: str | None = None
    api_token: str | None = None
    project_id: str | int | None = None
    fields: dict[str, str] = field(default_factory=dict)


class RedcapClient:
    """Study registry only — never PUT RGB/thermal blobs (ARCHITECTURE.md §5)."""

    def __init__(self, config: RedcapConfig | None = None) -> None:
        self.config = config or RedcapConfig()

    def get_participant(self, record_id: str) -> dict[str, Any]:
        raise NotImplementedError(
            "REDCap HTTP is Phase 1 stub-only. Field dictionary: INTEGRATIONS.md §4."
        )

    def upsert_session(self, record_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(
            "REDCap HTTP is Phase 1 stub-only. Field dictionary: INTEGRATIONS.md §4."
        )


@dataclass
class BoxConfig:
    root_folder_id: str | None = None
    root_folder_path: str | None = None


class BoxUploader:
    """Async blob upload after local write. Phase 1 does not call the network."""

    def __init__(self, config: BoxConfig | None = None) -> None:
        self.config = config or BoxConfig()

    def planned_remote_path(self, participant_id: str, session_id: str) -> str:
        root = self.config.root_folder_path or "QuantumPlatform"
        return f"{root}/sessions/{participant_id}/{session_id}/"

    def upload_session(self, local_dir: str | Path) -> dict[str, Any]:
        raise NotImplementedError(
            "Box upload is Phase 1 stub-only. Taxonomy: INTEGRATIONS.md §5. "
            f"Would mirror {local_dir} under {self.config.root_folder_id or self.config.root_folder_path!r}."
        )
