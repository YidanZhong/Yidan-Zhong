"""Fault-injection checks for bounded GPU telemetry; not real Isaac evidence."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from run_windows_probe import GpuTelemetry


class TelemetryTests(unittest.TestCase):
    def test_two_timeouts_then_recovery_and_counter_reset(self):
        timeout = subprocess.TimeoutExpired('nvidia-smi', 8)
        with patch('run_windows_probe.subprocess.check_output', side_effect=[timeout, timeout, '2000, 8000', timeout]):
            monitor = GpuTelemetry()
            self.assertIsNone(monitor.sample())
            self.assertIsNone(monitor.sample())
            self.assertEqual(monitor.sample(), .25)
            self.assertEqual(monitor.consecutive_failures, 0)
            self.assertIsNone(monitor.sample())
            self.assertEqual(monitor.consecutive_failures, 1)
            self.assertEqual(monitor.total_failures, 3)

    def test_third_failure_stops(self):
        with patch('run_windows_probe.subprocess.check_output', side_effect=subprocess.TimeoutExpired('nvidia-smi', 8)):
            monitor = GpuTelemetry()
            monitor.sample(); monitor.sample()
            with self.assertRaisesRegex(RuntimeError, 'bounded retry'):
                monitor.sample()

    def test_preflight_requires_current_sample(self):
        with patch('run_windows_probe.subprocess.check_output', side_effect=OSError('missing executable')):
            with self.assertRaises(RuntimeError):
                GpuTelemetry().sample(strict=True)

    def test_invalid_values_never_report_healthy(self):
        for value in ['', 'N/A, 8000', 'nan, 8000', '1, 0', '-1, 8000', '9000, 8000', '1, inf']:
            with self.subTest(value=value), patch('run_windows_probe.subprocess.check_output', return_value=value):
                with self.assertRaises(RuntimeError):
                    GpuTelemetry().sample(strict=True)

    def test_highest_gpu_usage_remains_visible_to_guard(self):
        with patch('run_windows_probe.subprocess.check_output', return_value='1000, 8000\n7200, 8000'):
            self.assertEqual(GpuTelemetry().sample(), .9)


if __name__ == '__main__':
    unittest.main()
