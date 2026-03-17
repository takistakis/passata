from unittest.mock import patch

from passata import die


def test_die_calls_notify_on_linux() -> None:
    message = "Test error"
    icon = "dialog-warning"

    with (
        patch("passata.call") as mock_call,
        patch("sys.exit") as mock_exit,
        patch("sys.platform", "linux"),
    ):
        die(message)
        mock_call.assert_called_once_with(
            ["notify-send", "-i", icon, "passata", message],
        )
        mock_exit.assert_called_once_with(1)


def test_die_calls_osascript_on_darwin() -> None:
    """Test that die calls osascript on macOS."""
    message = "Test error"

    with (
        patch("passata.call") as mock_call,
        patch("sys.exit") as mock_exit,
        patch("sys.platform", "darwin"),
    ):
        die(message)
        mock_call.assert_called_once_with(
            [
                "osascript",
                "-e",
                f'display notification "{message}" with title "passata"',
            ],
        )
        mock_exit.assert_called_once_with(1)
