from unittest.mock import patch

from passata import die


def test_die_calls_notify_and_exits() -> None:
    message = "Test error"
    icon = "dialog-warning"

    with patch("passata.call") as mock_call, patch("sys.exit") as mock_exit:
        die(message)
        mock_call.assert_called_once_with(
            ["notify-send", "-i", icon, "passata", message]
        )
        mock_exit.assert_called_once_with(1)
