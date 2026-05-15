"""Unit tests for Codex CLI detection helpers.

Run with:
    python3 -m unittest core.test_codex_detect -v
"""

from __future__ import annotations

import io
import os
import subprocess
import time
import unittest
from unittest.mock import Mock, patch

from core.codex_detect import (
    _CACHE,
    detect_codex,
    format_fallback_marker,
    read_setting,
    should_fallback,
)


class _BaseCodexDetectTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _CACHE.clear()

    def tearDown(self) -> None:
        _CACHE.clear()


class DetectCodexTests(_BaseCodexDetectTestCase):
    @patch("core.codex_detect.subprocess.run")
    def test_detect_codex_returns_version_when_command_succeeds(
        self, run_mock: Mock
    ) -> None:
        run_mock.return_value = subprocess.CompletedProcess(
            args=["codex", "--version"],
            returncode=0,
            stdout="Codex CLI 1.2.3\n",
            stderr="",
        )

        result = detect_codex()

        self.assertTrue(result.available)
        self.assertEqual(result.version, "1.2.3")
        self.assertIsNone(result.reason)

    @patch("core.codex_detect.subprocess.run", side_effect=FileNotFoundError)
    def test_detect_codex_handles_missing_binary(self, run_mock: Mock) -> None:
        result = detect_codex()

        self.assertFalse(result.available)
        self.assertIsNone(result.version)
        self.assertIn("not found", result.reason or "")

    @patch("core.codex_detect.subprocess.run")
    def test_detect_codex_handles_non_zero_exit(self, run_mock: Mock) -> None:
        run_mock.return_value = subprocess.CompletedProcess(
            args=["codex", "--version"],
            returncode=1,
            stdout="",
            stderr="boom",
        )

        result = detect_codex()

        self.assertFalse(result.available)
        self.assertIsNone(result.version)
        self.assertIn("1", result.reason or "")

    @patch(
        "core.codex_detect.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["codex", "--version"], timeout=2.0),
    )
    def test_detect_codex_handles_timeout(self, run_mock: Mock) -> None:
        result = detect_codex(timeout=2.0)

        self.assertFalse(result.available)
        self.assertIsNone(result.version)
        self.assertIn("timeout", result.reason or "")

    @patch("core.codex_detect.subprocess.run")
    def test_detect_codex_caches_result(self, run_mock: Mock) -> None:
        run_mock.return_value = subprocess.CompletedProcess(
            args=["codex", "--version"],
            returncode=0,
            stdout="Codex CLI 1.2.3\n",
            stderr="",
        )

        first = detect_codex()
        second = detect_codex()

        self.assertEqual(run_mock.call_count, 1)
        self.assertEqual(first, second)

    @patch("core.codex_detect.subprocess.run")
    def test_detect_codex_force_bypasses_cache(self, run_mock: Mock) -> None:
        run_mock.return_value = subprocess.CompletedProcess(
            args=["codex", "--version"],
            returncode=0,
            stdout="Codex CLI 1.2.3\n",
            stderr="",
        )

        detect_codex()
        detect_codex(force=True)

        self.assertEqual(run_mock.call_count, 2)

    @patch(
        "core.codex_detect.subprocess.run",
        side_effect=OSError("permission denied"),
    )
    def test_detect_codex_handles_oserror(self, run_mock: Mock) -> None:
        result = detect_codex()

        self.assertFalse(result.available)
        self.assertIsNone(result.version)
        self.assertIn("OSError", result.reason or "")

    @patch(
        "core.codex_detect.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["codex", "--version"], timeout=2.0),
    )
    def test_detect_codex_returns_within_timeout_window(self, run_mock: Mock) -> None:
        started = time.monotonic()
        result = detect_codex(timeout=2.0)
        elapsed = time.monotonic() - started

        self.assertFalse(result.available)
        self.assertLess(elapsed, 2.5)


class ReadSettingTests(_BaseCodexDetectTestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_read_setting_returns_default_when_unset(self) -> None:
        self.assertEqual(read_setting(), "auto")

    @patch.dict(os.environ, {"CODEX_HARNESS_FALLBACK": "off"}, clear=True)
    def test_read_setting_returns_explicit_value(self) -> None:
        self.assertEqual(read_setting(), "off")

    @patch.dict(os.environ, {"CODEX_HARNESS_FALLBACK": "bogus"}, clear=True)
    def test_read_setting_warns_and_falls_back_on_invalid_value(self) -> None:
        stderr = io.StringIO()
        with patch("sys.stderr", stderr):
            result = read_setting()

        self.assertEqual(result, "auto")
        self.assertIn("Invalid CODEX_HARNESS_FALLBACK=bogus", stderr.getvalue())

    @patch.dict(os.environ, {"CODEX_HARNESS_FALLBACK": ""}, clear=True)
    def test_read_setting_treats_empty_string_as_default(self) -> None:
        stderr = io.StringIO()
        with patch("sys.stderr", stderr):
            result = read_setting()

        self.assertEqual(result, "auto")
        self.assertEqual(stderr.getvalue(), "")


class ShouldFallbackTests(_BaseCodexDetectTestCase):
    @patch.dict(os.environ, {"CODEX_HARNESS_FALLBACK": "auto"}, clear=True)
    @patch("core.codex_detect.subprocess.run")
    def test_should_fallback_false_when_codex_available_and_auto(
        self, run_mock: Mock
    ) -> None:
        run_mock.return_value = subprocess.CompletedProcess(
            args=["codex", "--version"],
            returncode=0,
            stdout="Codex CLI 1.2.3\n",
            stderr="",
        )

        self.assertEqual(should_fallback(), (False, "codex-native"))

    @patch.dict(os.environ, {"CODEX_HARNESS_FALLBACK": "auto"}, clear=True)
    @patch("core.codex_detect.subprocess.run", side_effect=FileNotFoundError)
    def test_should_fallback_true_when_codex_unavailable_and_auto(
        self, run_mock: Mock
    ) -> None:
        self.assertEqual(should_fallback(), (True, "claude-subagent"))

    @patch.dict(os.environ, {"CODEX_HARNESS_FALLBACK": "off"}, clear=True)
    @patch("core.codex_detect.subprocess.run")
    def test_should_fallback_false_when_setting_off(self, run_mock: Mock) -> None:
        self.assertEqual(should_fallback(), (False, "off"))
        self.assertEqual(run_mock.call_count, 0)


class FormatFallbackMarkerTests(_BaseCodexDetectTestCase):
    def test_format_fallback_marker_matches_adr_specification(self) -> None:
        marker = format_fallback_marker("not found", "claude-subagent")

        self.assertEqual(
            marker,
            "[harness-core] FALLBACK MODE: Codex unavailable (not found). "
            "Strategy: claude-subagent. Quality may degrade.",
        )


if __name__ == "__main__":
    unittest.main()
