import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

import psutil
import requests

from app_config import Settings, load_settings
from otp_security import OTP_LENGTH, OtpSession
from telegram_client import TelegramDeliveryError, send_message
from WindowService import GameControllerApp

TEST_SETTINGS = Settings(bot_token="123:unit-test-only", chat_id="456")


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "config.json"
        self.env = patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": TEST_SETTINGS.bot_token,
            "TELEGRAM_CHAT_ID": TEST_SETTINGS.chat_id,
        }, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_missing_file_uses_defaults(self):
        self.assertEqual(load_settings(self.path), TEST_SETTINGS)

    def test_missing_credentials_fail_without_showing_secret(self):
        for variable in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
            with self.subTest(variable=variable), patch.dict(os.environ, {variable: ""}):
                with self.assertRaises(ValueError) as result:
                    load_settings(self.path)
                self.assertNotIn(TEST_SETTINGS.bot_token, str(result.exception))

    def test_secrets_not_in_settings_repr(self):
        self.assertNotIn(TEST_SETTINGS.bot_token, repr(TEST_SETTINGS))
        self.assertNotIn(TEST_SETTINGS.chat_id, repr(TEST_SETTINGS))

    def test_valid_local_config_with_bom(self):
        self.path.write_text(json.dumps({"game_name": "Game.exe", "time_limit_seconds": 60}), encoding="utf-8-sig")
        settings = load_settings(self.path)
        self.assertEqual(settings.game_name, "Game.exe")
        self.assertEqual(settings.time_limit_seconds, 60)

    def test_invalid_configs_are_rejected(self):
        invalid = [
            [], {"unknown": 1}, {"bot_token": "do-not-store-secrets"},
            {"game_name": "../game.exe"}, {"game_name": "C:\\game.exe"},
            {"game_name": None}, {"game_name": "game"},
            {"time_limit_seconds": True}, {"time_limit_seconds": 0},
            {"time_limit_seconds": 86401}, {"otp_ttl_seconds": "300"},
            {"otp_max_attempts": 11}, {"otp_max_attempts": 0},
            {"request_cooldown_seconds": -1}, {"report_interval_seconds": 0},
        ]
        for config in invalid:
            with self.subTest(config=config):
                self.path.write_text(json.dumps(config), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_settings(self.path)

    def test_malformed_json_is_rejected(self):
        self.path.write_text("{", encoding="utf-8")
        with self.assertRaises(ValueError):
            load_settings(self.path)


class OtpTests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.session = OtpSession(TEST_SETTINGS, clock=lambda: self.now)

    def test_empty_code_does_not_authorize(self):
        self.assertFalse(self.session.verify(""))
        self.assertEqual(self.session.remaining_seconds(), 0)

    def test_secure_six_digit_code_single_use(self):
        code = self.session.issue()
        self.assertEqual(len(code), OTP_LENGTH)
        self.assertTrue(code.isascii() and code.isdigit())
        self.assertTrue(self.session.verify(code))
        self.assertFalse(self.session.verify(code))
        self.assertEqual(self.session.remaining_seconds(), TEST_SETTINGS.time_limit_seconds)

    def test_expires_at_deadline(self):
        code = self.session.issue()
        self.now = TEST_SETTINGS.otp_ttl_seconds
        self.assertFalse(self.session.verify(code))

    def test_wrong_attempt_limit_cannot_be_bypassed_with_correct_code(self):
        code = self.session.issue()
        for _ in range(TEST_SETTINGS.otp_max_attempts):
            self.assertFalse(self.session.verify("wrong"))
        self.assertFalse(self.session.verify(code))

    def test_non_ascii_input_rejected_without_crashing(self):
        self.session.issue()
        self.assertFalse(self.session.verify("１２３４５６"))

    def test_request_cooldown_at_start_and_boundary(self):
        self.session.issue()
        self.now = TEST_SETTINGS.request_cooldown_seconds - 1
        with self.assertRaises(ValueError):
            self.session.issue()
        self.now += 1
        self.session.issue()

    def test_new_request_replaces_previous_code(self):
        with patch("otp_security.secrets.choice", side_effect=list("123456654321")):
            first = self.session.issue()
            self.now = TEST_SETTINGS.request_cooldown_seconds
            second = self.session.issue()
        self.assertFalse(self.session.verify(first))
        self.assertTrue(self.session.verify(second))

    def test_invalidation_on_delivery_failure(self):
        code = self.session.issue()
        self.session.invalidate()
        self.assertFalse(self.session.verify(code))

    def test_top_up_preserves_unspent_time(self):
        self.assertTrue(self.session.verify(self.session.issue()))
        self.now = TEST_SETTINGS.request_cooldown_seconds
        self.assertTrue(self.session.verify(self.session.issue()))
        self.assertEqual(self.session.remaining_seconds(), 2 * TEST_SETTINGS.time_limit_seconds - self.now)

    def test_grant_after_balance_expires(self):
        self.assertTrue(self.session.verify(self.session.issue()))
        self.now = TEST_SETTINGS.time_limit_seconds + 1
        self.assertEqual(self.session.remaining_seconds(), 0)
        self.assertTrue(self.session.verify(self.session.issue()))
        self.assertEqual(self.session.remaining_seconds(), TEST_SETTINGS.time_limit_seconds)


class TelegramTests(unittest.TestCase):
    @patch("telegram_client.requests.post")
    def test_delivery_has_timeout_no_redirect_and_checks_acknowledgement(self, post):
        post.return_value.__enter__.return_value.json.return_value = {"ok": True}
        send_message(TEST_SETTINGS, "test message")
        self.assertIn("timeout", post.call_args.kwargs)
        self.assertFalse(post.call_args.kwargs["allow_redirects"])

    @patch("telegram_client.requests.post")
    def test_failures_do_not_expose_secret(self, post):
        post.side_effect = requests.ConnectionError(f"secret URL: {TEST_SETTINGS.bot_token}")
        with self.assertRaises(TelegramDeliveryError) as result:
            send_message(TEST_SETTINGS, "test")
        self.assertNotIn(TEST_SETTINGS.bot_token, str(result.exception))

    @patch("telegram_client.requests.post")
    def test_invalid_api_acknowledgements_are_rejected(self, post):
        response = post.return_value.__enter__.return_value
        for payload in ({"ok": False}, {"ok": "true"}, [], None):
            with self.subTest(payload=payload):
                response.json.return_value = payload
                with self.assertRaises(TelegramDeliveryError):
                    send_message(TEST_SETTINGS, "test")

    @patch("telegram_client.requests.post")
    def test_http_error_is_rejected_without_secret(self, post):
        response = post.return_value.__enter__.return_value
        response.raise_for_status.side_effect = requests.HTTPError(TEST_SETTINGS.bot_token)
        with self.assertRaises(TelegramDeliveryError) as result:
            send_message(TEST_SETTINGS, "test")
        self.assertNotIn(TEST_SETTINGS.bot_token, str(result.exception))

    @patch("telegram_client.requests.post")
    def test_invalid_json_is_rejected(self, post):
        post.return_value.__enter__.return_value.json.side_effect = ValueError("bad JSON")
        with self.assertRaises(TelegramDeliveryError):
            send_message(TEST_SETTINGS, "test")

    @patch("telegram_client.requests.post")
    def test_empty_or_oversize_message_does_not_send(self, post):
        for message in ("", "x" * 4001):
            with self.assertRaises(TelegramDeliveryError):
                send_message(TEST_SETTINGS, message)
        post.assert_not_called()


class MonitoringTests(unittest.TestCase):
    def setUp(self):
        self.app = GameControllerApp.__new__(GameControllerApp)
        self.app.root = Mock()
        self.app.settings = replace(TEST_SETTINGS, game_name="Game.exe")
        self.app.label_status = Mock()
        self.app.label_timer = Mock()
        self.app.session = OtpSession(self.app.settings, clock=lambda: 0)

    @patch("WindowService.psutil.process_iter")
    def test_all_matching_processes_are_stopped_only(self, process_iter):
        processes = [Mock(info={"name": name}) for name in ("Game.exe", "GAME.EXE", "Other.exe", None)]
        process_iter.return_value = processes
        self.app.monitor_game()
        processes[0].terminate.assert_called_once()
        processes[1].terminate.assert_called_once()
        processes[2].terminate.assert_not_called()
        processes[3].terminate.assert_not_called()

    @patch("WindowService.psutil.process_iter")
    def test_authorized_game_is_not_stopped(self, process_iter):
        self.app.session.verify(self.app.session.issue())
        self.app.monitor_game()
        process_iter.assert_not_called()

    @patch("WindowService.psutil.process_iter")
    def test_denied_or_exited_process_does_not_break_monitor(self, process_iter):
        denied = Mock(info={"name": "Game.exe"})
        denied.terminate.side_effect = psutil.AccessDenied()
        exited = Mock(info={"name": "Game.exe"})
        exited.terminate.side_effect = psutil.NoSuchProcess(1)
        process_iter.return_value = [denied, exited]
        self.app.monitor_game()
        self.app.root.after.assert_called_once()


if __name__ == "__main__":
    unittest.main()
