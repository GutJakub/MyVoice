import unittest
from unittest.mock import Mock, call, patch

from myvoice.commands.router import CommandRouter
from myvoice.main import execute_command, run_keyboard_mode


class CommandRouterNormalizationTests(unittest.TestCase):
    def test_normalization_preserves_commands_starting_with_wake_word_characters(self):
        self.assertEqual(CommandRouter._normalize("volume up"), "volume up")
        self.assertEqual(CommandRouter._normalize("set volume to 50"), "set volume to 50")

    def test_normalization_removes_explicit_wake_phrase(self):
        self.assertEqual(
            CommandRouter._normalize("Hey Jarvis, volume up!"),
            "volume up",
        )


class CommandExecutionTests(unittest.TestCase):
    @patch("myvoice.main.run_command")
    def test_execute_command_uses_agent_as_fallback(self, run_command):
        router = Mock()
        router.route.return_value = None
        run_command.return_value = "Agent response"

        self.assertEqual(execute_command("unknown", router), "Agent response")
        run_command.assert_called_once_with("unknown")

    @patch("builtins.print")
    @patch("builtins.input", side_effect=["volume up", "exit"])
    def test_keyboard_mode_routes_commands_until_exit(self, input_mock, print_mock):
        router = Mock()
        router.route.return_value = "Volume up."

        run_keyboard_mode(router)

        router.route.assert_called_once_with("volume up")
        self.assertIn(call("MyVoice: Volume up."), print_mock.call_args_list)


if __name__ == "__main__":
    unittest.main()
