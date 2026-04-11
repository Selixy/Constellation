"""Tests for OscSender (UDP OSC wrapper)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch, call

import pytest

from riverflow_server.osc.sender import OscSender, _ADDR_IMPACT, _ADDR_MAPPING


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_client() -> MagicMock:
    return MagicMock()


@pytest.fixture
def sender(mock_client: MagicMock) -> OscSender:
    """OscSender with a mocked SimpleUDPClient."""
    with patch("riverflow_server.osc.sender.SimpleUDPClient", return_value=mock_client):
        s = OscSender("127.0.0.1", 9000)
    # Inject the mock directly so subsequent calls use it
    s._client = mock_client
    return s


# ---------------------------------------------------------------------------
# send_impact
# ---------------------------------------------------------------------------

class TestSendImpact:
    def test_calls_send_message_with_correct_address(self, sender: OscSender, mock_client: MagicMock) -> None:
        sender.send_impact("cam0", 0.5, 0.3, 1.2)
        mock_client.send_message.assert_called_once()
        address, args = mock_client.send_message.call_args.args
        assert address == _ADDR_IMPACT

    def test_calls_send_message_with_correct_args(self, sender: OscSender, mock_client: MagicMock) -> None:
        sender.send_impact("cam1", 0.1, 0.9, 2.5)
        _, args = mock_client.send_message.call_args.args
        assert args[0] == "cam1"
        assert pytest.approx(args[1]) == 0.1
        assert pytest.approx(args[2]) == 0.9
        assert pytest.approx(args[3]) == 2.5

    def test_floats_are_cast(self, sender: OscSender, mock_client: MagicMock) -> None:
        """Integer inputs must be cast to float in the message."""
        sender.send_impact("cam0", 1, 0, 3)
        _, args = mock_client.send_message.call_args.args
        assert isinstance(args[1], float)
        assert isinstance(args[2], float)
        assert isinstance(args[3], float)

    def test_network_error_is_silent(self, sender: OscSender, mock_client: MagicMock) -> None:
        """A socket/OSC error must not propagate — it should be swallowed."""
        mock_client.send_message.side_effect = OSError("network unreachable")
        # Must not raise
        sender.send_impact("cam0", 0.5, 0.5, 1.0)


# ---------------------------------------------------------------------------
# send_camera_mapping
# ---------------------------------------------------------------------------

class TestSendCameraMapping:
    def test_calls_send_message_with_correct_address(self, sender: OscSender, mock_client: MagicMock) -> None:
        sender.send_camera_mapping("cam0", 0.0, 0.0, 1.0, 1.0)
        address, args = mock_client.send_message.call_args.args
        assert address == _ADDR_MAPPING

    def test_correct_args(self, sender: OscSender, mock_client: MagicMock) -> None:
        sender.send_camera_mapping("cam2", 0.1, 0.2, 0.8, 0.6)
        _, args = mock_client.send_message.call_args.args
        assert args == ["cam2", 0.1, 0.2, 0.8, 0.6]

    def test_network_error_is_silent(self, sender: OscSender, mock_client: MagicMock) -> None:
        mock_client.send_message.side_effect = ConnectionRefusedError("refused")
        sender.send_camera_mapping("cam0", 0.0, 0.0, 1.0, 1.0)  # must not raise


# ---------------------------------------------------------------------------
# update_target
# ---------------------------------------------------------------------------

class TestUpdateTarget:
    def test_recreates_client_with_new_host_port(self, mock_client: MagicMock) -> None:
        new_client = MagicMock()
        with patch("riverflow_server.osc.sender.SimpleUDPClient", return_value=mock_client) as MockUDP:
            s = OscSender("127.0.0.1", 9000)
            MockUDP.return_value = new_client
            s.update_target("192.168.1.10", 8000)
            MockUDP.assert_called_with("192.168.1.10", 8000)

        assert s._host == "192.168.1.10"
        assert s._port == 8000
        assert s._client is new_client

    def test_subsequent_send_uses_new_client(self) -> None:
        old_client = MagicMock()
        new_client = MagicMock()

        with patch("riverflow_server.osc.sender.SimpleUDPClient", return_value=old_client):
            s = OscSender("127.0.0.1", 9000)

        with patch("riverflow_server.osc.sender.SimpleUDPClient", return_value=new_client):
            s.update_target("10.0.0.1", 7000)

        s.send_impact("cam0", 0.0, 0.0, 0.0)
        new_client.send_message.assert_called_once()
        old_client.send_message.assert_not_called()

    def test_update_target_network_error_on_subsequent_send_is_silent(self) -> None:
        """Even after update_target, network errors on send should be caught."""
        bad_client = MagicMock()
        bad_client.send_message.side_effect = Exception("boom")

        with patch("riverflow_server.osc.sender.SimpleUDPClient", return_value=MagicMock()):
            s = OscSender()

        with patch("riverflow_server.osc.sender.SimpleUDPClient", return_value=bad_client):
            s.update_target("10.0.0.2", 5005)

        s.send_impact("cam0", 0.5, 0.5, 1.0)  # must not raise


# ---------------------------------------------------------------------------
# Constructor / repr
# ---------------------------------------------------------------------------

class TestOscSenderInit:
    def test_default_host_port(self) -> None:
        with patch("riverflow_server.osc.sender.SimpleUDPClient") as MockUDP:
            MockUDP.return_value = MagicMock()
            s = OscSender()
        assert s._host == "127.0.0.1"
        assert s._port == 9000

    def test_repr(self) -> None:
        with patch("riverflow_server.osc.sender.SimpleUDPClient", return_value=MagicMock()):
            s = OscSender("192.168.0.1", 8765)
        assert "192.168.0.1" in repr(s)
        assert "8765" in repr(s)
