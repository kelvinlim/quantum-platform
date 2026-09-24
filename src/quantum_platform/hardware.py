"""Vendor SDK probe stubs.

Real capture is Phase 2. These interfaces exist so ``qp doctor`` can report
whether host runtimes are importable, and so workers have a clean place to
plug OTC / PySpin / Polar BLE / MediaPipe / pylsl later.

OS support follows SDK.md: OTC is Windows/Linux only; Spinnaker/PySpin is
Win/Mac/Linux.
"""

from __future__ import annotations

import sys
from dataclasses import asdict, dataclass
from typing import Any, Protocol


@dataclass
class ProbeResult:
    name: str
    import_name: str
    importable: bool
    platform_supported: bool
    message: str
    platform: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def current_platform() -> str:
    if sys.platform == "darwin":
        return "macos"
    if sys.platform.startswith("win"):
        return "windows"
    return "linux"


def _try_import(module: str) -> tuple[bool, str]:
    try:
        __import__(module)
        return True, "importable"
    except Exception as exc:  # noqa: BLE001 — doctor should not crash
        return False, f"{type(exc).__name__}: {exc}"


class CaptureBackend(Protocol):
    """Phase 2 hook. Mock backends implement this; vendor backends stub start()."""

    name: str

    def probe(self) -> ProbeResult: ...


def probe_otc() -> ProbeResult:
    """Optris OTC SDK (``import optris.otcsdk as otc``). No official macOS SDK."""
    plat = current_platform()
    supported = plat in {"windows", "linux"}
    if not supported:
        return ProbeResult(
            name="thermal",
            import_name="optris.otcsdk",
            importable=False,
            platform_supported=False,
            message="OTC SDK is not available on macOS (SDK.md). Use a Windows/Linux lab host for thermal.",
            platform=plat,
        )
    ok, msg = _try_import("optris.otcsdk")
    return ProbeResult(
        name="thermal",
        import_name="optris.otcsdk",
        importable=ok,
        platform_supported=True,
        message=msg if ok else f"OTC not importable ({msg}). Host install required.",
        platform=plat,
    )


def probe_pyspin() -> ProbeResult:
    plat = current_platform()
    ok, msg = _try_import("PySpin")
    if not ok:
        alt_ok, alt_msg = _try_import("spinnaker_python")
        if alt_ok:
            ok, msg = True, "importable via spinnaker_python"
        else:
            msg = f"PySpin not importable ({msg}); spinnaker_python ({alt_msg})"
    return ProbeResult(
        name="rgb",
        import_name="PySpin",
        importable=ok,
        platform_supported=True,
        message=msg if ok else f"{msg}. Install Spinnaker runtime + matching wheel (prefer Python 3.12).",
        platform=plat,
    )


def probe_bleak() -> ProbeResult:
    plat = current_platform()
    ok, msg = _try_import("bleak")
    return ProbeResult(
        name="verity",
        import_name="bleak",
        importable=ok,
        platform_supported=True,
        message=msg if ok else f"Polar BLE stack not importable ({msg}). Phase 2 will use bleak (or equivalent).",
        platform=plat,
    )


def probe_mediapipe() -> ProbeResult:
    plat = current_platform()
    ok, msg = _try_import("mediapipe")
    return ProbeResult(
        name="gaze",
        import_name="mediapipe",
        importable=ok,
        platform_supported=True,
        message=msg if ok else f"MediaPipe not importable ({msg}). Software gaze is Phase 2.",
        platform=plat,
    )


def probe_pylsl() -> ProbeResult:
    plat = current_platform()
    ok, msg = _try_import("pylsl")
    return ProbeResult(
        name="lsl",
        import_name="pylsl",
        importable=ok,
        platform_supported=True,
        message=msg if ok else f"pylsl not importable ({msg}). Phase 1 writes events.jsonl only.",
        platform=plat,
    )


def probe_libirimager() -> ProbeResult:
    """Legacy Optris path. Prefer OTC. Windows/Linux only."""
    plat = current_platform()
    supported = plat in {"windows", "linux"}
    ok, msg = _try_import("irimager")
    return ProbeResult(
        name="thermal_legacy",
        import_name="irimager",
        importable=ok and supported,
        platform_supported=supported,
        message=(
            "legacy libirimager fallback; prefer OTC"
            if supported
            else "libirimager is Windows/Linux only"
        )
        + ("" if ok else f" ({msg})"),
        platform=plat,
    )


class OptrisOtcBackend:
    name = "otc"

    def probe(self) -> ProbeResult:
        return probe_otc()

    def start(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError("Optris OTC capture is Phase 2")


class PySpinBackend:
    name = "pyspin"

    def probe(self) -> ProbeResult:
        return probe_pyspin()

    def start(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError("Spinnaker / PySpin capture is Phase 2")


class PolarBleBackend:
    name = "polar_ble"

    def probe(self) -> ProbeResult:
        return probe_bleak()

    def start(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError("Polar Verity Sense BLE capture is Phase 2")


class MediaPipeGazeBackend:
    name = "mediapipe"

    def probe(self) -> ProbeResult:
        return probe_mediapipe()

    def start(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError("MediaPipe gaze is Phase 2")


class LslBackend:
    name = "pylsl"

    def probe(self) -> ProbeResult:
        return probe_pylsl()

    def start(self, *args: Any, **kwargs: Any) -> None:
        raise NotImplementedError("pylsl outlets are Phase 2")


def probe_all() -> list[ProbeResult]:
    return [
        probe_otc(),
        probe_pyspin(),
        probe_bleak(),
        probe_mediapipe(),
        probe_pylsl(),
        probe_libirimager(),
    ]
