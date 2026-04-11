"""OSC UDP sender — wraps python-osc SimpleUDPClient for Unity communication."""

from __future__ import annotations

import logging

from pythonosc.udp_client import SimpleUDPClient

logger = logging.getLogger(__name__)

_DEFAULT_HOST = "127.0.0.1"
_DEFAULT_PORT = 9000

_ADDR_IMPACT = "/impact/detected"
_ADDR_MAPPING = "/camera/mapping"


class OscSender:
    """
    Sends OSC messages to a Unity listener over UDP.

    Message contracts
    -----------------
    ``/impact/detected``  — args: ``[camera_id: str, x: float, y: float, velocity: float]``
    ``/camera/mapping``   — args: ``[camera_id: str, x: float, y: float, w: float, h: float]``

    Network errors are caught and logged as warnings so callers never have
    to guard :meth:`send_impact` / :meth:`send_camera_mapping` calls.

    Example::

        sender = OscSender("192.168.1.50", 9000)
        sender.send_impact("cam0", 0.5, 0.3, 1.2)
    """

    def __init__(self, host: str = _DEFAULT_HOST, port: int = _DEFAULT_PORT) -> None:
        """
        Initialise the sender with a target *host* and *port*.

        Parameters
        ----------
        host:
            IP address or hostname of the OSC listener (default ``127.0.0.1``).
        port:
            UDP port of the OSC listener (default ``9000``).
        """
        self._host = host
        self._port = port
        self._client = self._make_client(host, port)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_client(host: str, port: int) -> SimpleUDPClient:
        return SimpleUDPClient(host, port)

    def _send(self, address: str, args: list) -> None:
        """Send *args* to OSC *address*, logging any network error silently."""
        try:
            self._client.send_message(address, args)
            logger.debug("OSC %s -> %s:%d  args=%s", address, self._host, self._port, args)
        except Exception as exc:  # OSC / socket errors
            logger.warning("OSC send failed (%s %s:%d): %s", address, self._host, self._port, exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_impact(
        self,
        camera_id: str,
        x: float,
        y: float,
        velocity: float,
    ) -> None:
        """
        Notify Unity of a detected impact event.

        Parameters
        ----------
        camera_id:
            Identifier of the originating camera.
        x, y:
            Normalised impact position in ``[0.0, 1.0]``.
        velocity:
            Estimated impact velocity (arbitrary unit, ≥ 0).
        """
        self._send(_ADDR_IMPACT, [camera_id, float(x), float(y), float(velocity)])

    def send_camera_mapping(
        self,
        camera_id: str,
        x: float,
        y: float,
        w: float,
        h: float,
    ) -> None:
        """
        Send the floor-projection mapping rectangle for *camera_id*.

        Parameters
        ----------
        camera_id:
            Identifier of the camera being mapped.
        x, y:
            Top-left corner of the mapped region (normalised ``[0, 1]``).
        w, h:
            Width and height of the mapped region (normalised ``[0, 1]``).
        """
        self._send(_ADDR_MAPPING, [camera_id, float(x), float(y), float(w), float(h)])

    def update_target(self, host: str, port: int) -> None:
        """
        Change the OSC target at runtime without restarting the application.

        Parameters
        ----------
        host:
            New target IP address or hostname.
        port:
            New target UDP port.
        """
        self._host = host
        self._port = port
        self._client = self._make_client(host, port)
        logger.info("OSC target updated to %s:%d", host, port)

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return f"OscSender(host={self._host!r}, port={self._port!r})"
