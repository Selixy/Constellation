"""Application configuration — dataclass + JSON persistence, no external deps."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppConfig:
    """Top-level configuration for the RiverFlow Vision Server.

    Attributes
    ----------
    cameras:
        List of camera source descriptors.  Each entry is a dict with at
        least the keys ``"id"`` (str) and ``"source"`` (int | str).
        Example: ``[{"id": "cam0", "source": 0}, {"id": "cam1", "source": "rtsp://..."}]``
    osc_host:
        IP address or hostname of the OSC listener (Unity target).
    osc_port:
        UDP port of the OSC listener.
    grid_rows:
        Number of rows in the calibration grid.
    grid_cols:
        Number of columns in the calibration grid.
    velocity_threshold:
        Minimum optical-flow velocity magnitude to trigger an impact event.
    calibration_file:
        Path to the JSON file used to persist homography calibration data.
    """

    cameras: list[dict] = field(default_factory=list)
    osc_host: str = "127.0.0.1"
    osc_port: int = 9000
    grid_rows: int = 8
    grid_cols: int = 6
    velocity_threshold: float = 5.0
    calibration_file: str = "calibration.json"


def default_config() -> AppConfig:
    """Return an :class:`AppConfig` with a single default webcam source.

    The returned config is ready to use out of the box on a development machine
    with a built-in webcam (OpenCV index ``0``).
    """
    return AppConfig(
        cameras=[{"id": "cam0", "source": 0}],
    )


def load_config(path: str | Path) -> AppConfig:
    """Deserialize an :class:`AppConfig` from a JSON file.

    Parameters
    ----------
    path:
        Path to the JSON configuration file.

    Returns
    -------
    AppConfig
        Populated with values from the file; any missing keys fall back to
        the dataclass defaults.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If the file contains invalid JSON.
    """
    path = Path(path)
    try:
        data: dict = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in config file '{path}': {exc}") from exc

    return AppConfig(
        cameras=list(data.get("cameras", [])),
        osc_host=str(data.get("osc_host", "127.0.0.1")),
        osc_port=int(data.get("osc_port", 9000)),
        grid_rows=int(data.get("grid_rows", 8)),
        grid_cols=int(data.get("grid_cols", 6)),
        velocity_threshold=float(data.get("velocity_threshold", 5.0)),
        calibration_file=str(data.get("calibration_file", "calibration.json")),
    )


def save_config(config: AppConfig, path: str | Path) -> None:
    """Serialize *config* to a JSON file.

    Parameters
    ----------
    config:
        The :class:`AppConfig` instance to persist.
    path:
        Destination file path.  The parent directory must already exist.
    """
    path = Path(path)
    data = {
        "cameras": config.cameras,
        "osc_host": config.osc_host,
        "osc_port": config.osc_port,
        "grid_rows": config.grid_rows,
        "grid_cols": config.grid_cols,
        "velocity_threshold": config.velocity_threshold,
        "calibration_file": config.calibration_file,
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
