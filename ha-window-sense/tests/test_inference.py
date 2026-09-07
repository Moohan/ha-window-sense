"""Unit tests for adaptive baseline, change-point detection, and hysteresis."""
import unittest
from custom_components.window_sense.inference import (
    AdaptiveBaselineModel,
    PageHinkleyChangePoint,
    WindowInferenceEngine,
)
from custom_components.window_sense.features import SensorReading


class TestInference(unittest.TestCase):
    def test_baseline_freezing_on_open(self):
        """Baseline expected temperature must freeze when window is declared open."""
        baseline = AdaptiveBaselineModel(initial_temp=21.0, learning_rate=0.1)

        # Initial update learns normally
        b1 = baseline.update(20.0, 5.0)
        self.assertTrue(b1 < 21.0)

        # Freeze baseline (simulate window opened)
        baseline.is_frozen = True
        frozen_val = baseline.expected_temp

        # Room cools drastically to 14°C
        b2 = baseline.update(14.0, 5.0)
        self.assertEqual(b2, frozen_val)
        self.assertEqual(baseline.expected_temp, frozen_val)

    def test_page_hinkley_change_point(self):
        """Abrupt spike in residual triggers change-point detection."""
        cp = PageHinkleyChangePoint(threshold=1.0, alpha=0.05)

        # Steady state (low residual)
        for _ in range(10):
            self.assertFalse(cp.update(residual=0.05))

        # Sudden jump in residual
        triggered = False
        for r in [0.4, 0.9, 1.4, 1.8]:
            if cp.update(residual=r):
                triggered = True
                break
        self.assertTrue(triggered)

    def test_asymmetric_hysteresis_timers(self):
        """Engine enforces persistence window before declaring state transition."""
        engine = WindowInferenceEngine(
            open_threshold=0.80,
            close_threshold=0.25,
            open_persistence_min=3,
            close_persistence_min=5,
        )

        t0 = 10000.0

        # Feed 10 minutes of baseline steady state
        for m in range(10):
            engine.process_reading(SensorReading(
                timestamp=t0 + (m * 60),
                indoor_temp=21.0,
                outdoor_temp=2.0,
                indoor_humidity=45.0,
                outdoor_humidity=85.0,
            ))
        self.assertFalse(engine.is_open)

        # Simulate sudden window open: rapid temperature plunge
        # Should require 3 consecutive minutes of high confidence to switch to True
        for m in range(10, 16):
            state = engine.process_reading(SensorReading(
                timestamp=t0 + (m * 60),
                indoor_temp=21.0 - ((m - 9) * 0.7),  # steep cooling
                outdoor_temp=2.0,
                indoor_humidity=45.0 + ((m - 9) * 5.0),
                outdoor_humidity=85.0,
            ))

        self.assertTrue(engine.is_open)


if __name__ == "__main__":
    unittest.main()
