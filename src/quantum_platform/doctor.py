"""``qp doctor`` / ``doctor.run`` — device presence and SDK import checks."""

from __future__ import annotations

import platform
import sys
from typing import Any

from quantum_platform import __version__
from quantum_platform.hardware import current_platform, probe_all


def run_doctor() -> dict[str, Any]:
    plat = current_platform()
    probes = [p.to_dict() for p in probe_all()]
    thermal = next(p for p in probes if p["name"] == "thermal")
    return {
        "ok": True,
        "sidecar_version": __version__,
        "python": sys.version.split()[0],
        "python_recommended": "3.12",
        "platform": plat,
        "platform_detail": platform.platform(),
        "thermal_supported": thermal["platform_supported"],
        "notes": _notes(plat, thermal["platform_supported"]),
        "sdks": probes,
    }


def _notes(plat: str, thermal_supported: bool) -> list[str]:
    notes = [
        "Phase 1 dry-run uses mock workers; vendor SDKs are probed but not required.",
        "Prefer Python 3.12 — PySpin wheels on Win/Mac/Ubuntu 24.04 list 3.10 and 3.12, not 3.11 (SDK.md).",
        "Spinnaker and Optris still need a host install even when a sidecar is bundled (INTEGRATIONS.md §3).",
    ]
    if plat == "macos" or not thermal_supported:
        notes.append(
            "Thermal (Optris PI 450i / OTC) is unsupported on macOS. Full study capture needs Windows or Linux."
        )
    return notes
