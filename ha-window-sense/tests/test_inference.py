"""Unit tests for adaptive baseline, change-point detection, hysteresis, and anti-contamination safeguards."""
import unittest
from window_sense.inference import (
    AdaptiveBaselineModel,
    PageHinkleyChangePoint,
    WindowInferenceEngine,
)
from window_sense.features import SensorReading


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

    def test_baseline_slew_rate_limiting(self):
        """Baseline updates are strictly bounded by physical building thermal mass inertia."""
        baseline = AdaptiveBaselineModel(
            initial_temp=21.0,
            learning_rate=0.5,  # High learning rate
            max_slew_per_minute=0.015,  # Max 0.015°C per minute
        )

        # Room temperature suddenly jumps by 5°C
        updated = baseline.update(indoor_temp=16.0, outdoor_temp=0.0)

        # In a single update, delta cannot exceed max_slew_per_minute
        delta = abs(updated - 21.0)
        self.assertLessEqual(delta, 0.01501)

    def test_baseline_does_not_adapt_during_suspicious_cooling(self):
        """Baseline adaptation is suspended as soon as suspicious rapid cooling starts."""
        engine = WindowInferenceEngine(
            open_threshold=0.80,
            close_threshold=0.25,
            open_persistence_min=3,
        )

        t0 = 10000.0

        # Stabilize at 21.0°C
        for m in range(10):
            engine.process_reading(SensorReading(
                timestamp=t0 + (m * 60),
                indoor_temp=21.0,
                outdoor_temp=2.0,
                indoor_humidity=45.0,
                outdoor_humidity=85.0,
            ))

        pre_event_baseline = engine.baseline_model.expected_temp
        self.assertAlmostEqual(pre_event_baseline, 21.0, delta=0.2)

        # Rapid cooling starts (temp rate < -1.0°C/h)
        # Window is not yet declared open (requires 3 consecutive minutes of high confidence)
        for m in range(10, 12):
            engine.process_reading(SensorReading(
                timestamp=t0 + (m * 60),
                indoor_temp=21.0 - ((m - 9) * 0.6),
                outdoor_temp=2.0,
                indoor_humidity=45.0 + ((m - 9) * 4.0),
                outdoor_humidity=85.0,
            ))
            # Baseline must be frozen during suspicious onset
            self.assertTrue(engine.baseline_model.is_frozen)
            # Baseline expected temp must not have collapsed to follow the cold temperature
            self.assertAlmostEqual(engine.baseline_model.expected_temp, pre_event_baseline, delta=0.1)

    def test_baseline_rollback_on_open_event(self):
        """When an open window is confirmed, baseline rolls back to the clean pre-event snapshot."""
        engine = WindowInferenceEngine(
            open_threshold=0.80,
            close_threshold=0.25,
            open_persistence_min=3,
        )

        t0 = 10000.0

        # 15 minutes of pristine equilibrium at 21.5°C
        for m in range(15):
            engine.process_reading(SensorReading(
                timestamp=t0 + (m * 60),
                indoor_temp=21.5,
                outdoor_temp=1.0,
                indoor_humidity=40.0,
                outdoor_humidity=88.0,
            ))

        clean_equilibrium = engine.baseline_model.expected_temp

        # Plunge into open window: 5 minutes of steep cooling
        for m in range(15, 21):
            engine.process_reading(SensorReading(
                timestamp=t0 + (m * 60),
                indoor_temp=21.5 - ((m - 14) * 0.8),
                outdoor_temp=1.0,
                indoor_humidity=40.0 + ((m - 14) * 4.0),
                outdoor_humidity=88.0,
            ))

        # Window is confirmed open
        self.assertTrue(engine.is_open)
        # Expected baseline must match pristine clean equilibrium, not the cold room
        self.assertAlmostEqual(engine.baseline_model.expected_temp, clean_equilibrium, delta=0.1)

    def test_baseline_resistant_to_prolonged_open_window(self):
        """The baseline must NOT learn that an open window is normal room behavior over long durations."""
        engine = WindowInferenceEngine(
            open_threshold=0.80,
            close_threshold=0.25,
            open_persistence_min=3,
        )

        t0 = 10000.0

        # 10 minutes at 21.0°C
        for m in range(10):
            engine.process_reading(SensorReading(
                timestamp=t0 + (m * 60),
                indoor_temp=21.0,
                outdoor_temp=0.0,
                indoor_humidity=45.0,
                outdoor_humidity=85.0,
            ))

        pristine_baseline = engine.baseline_model.expected_temp

        # Window opens and remains open for 60 minutes!
        # Room drops down to 12.0°C and stays cold
        for m in range(10, 70):
            curr_temp = max(12.0, 21.0 - ((m - 9) * 0.7))
            state = engine.process_reading(SensorReading(
                timestamp=t0 + (m * 60),
                indoor_temp=curr_temp,
                outdoor_temp=0.0,
                indoor_humidity=75.0,
                outdoor_humidity=85.0,
            ))

        # Window must remain open
        self.assertTrue(engine.is_open)
        # CRITICAL ASSERTION: The baseline must NOT have adapted to 12°C!
        # It must still expect ~21°C!
        self.assertAlmostEqual(engine.baseline_model.expected_temp, pristine_baseline, delta=0.2)
        # Thermal residual must reflect the true ~9°C deficit
        self.assertLess(state.thermal_residual, -8.0)
        # Confidence must remain high
        self.assertGreater(state.confidence, 0.75)

    def test_baseline_quarantine_during_post_close_recovery(self):
        """When the window closes, recovery quarantine prevents baseline from learning cold temperature."""
        engine = WindowInferenceEngine(
            open_threshold=0.80,
            close_threshold=0.25,
            open_persistence_min=3,
            close_persistence_min=3,
        )

        t0 = 10000.0

        # Baseline established at 21.0°C
        for m in range(10):
            engine.process_reading(SensorReading(
                timestamp=t0 + (m * 60),
                indoor_temp=21.0,
                outdoor_temp=2.0,
                indoor_humidity=45.0,
                outdoor_humidity=85.0,
            ))

        pre_event_baseline = engine.baseline_model.expected_temp

        # Window opened for 10 minutes (cools to 15°C)
        for m in range(10, 20):
            engine.process_reading(SensorReading(
                timestamp=t0 + (m * 60),
                indoor_temp=21.0 - ((m - 9) * 0.6),
                outdoor_temp=2.0,
                indoor_humidity=70.0,
                outdoor_humidity=85.0,
            ))
        self.assertTrue(engine.is_open)

        # Window closed: temperature starts slow recovery at 15.0°C -> 16.0°C
        # Humidity drops back towards normal
        for m in range(20, 30):
            engine.process_reading(SensorReading(
                timestamp=t0 + (m * 60),
                indoor_temp=15.0 + ((m - 20) * 0.1),
                outdoor_temp=2.0,
                indoor_humidity=48.0,
                outdoor_humidity=85.0,
            ))

        # Even if window is closed, baseline model is in recovery quarantine
        self.assertTrue(
            engine.baseline_model.in_recovery_quarantine or engine.baseline_model.is_frozen
        )
        # Baseline must NOT have adapted to the 15-16°C cold room!
        self.assertAlmostEqual(engine.baseline_model.expected_temp, pre_event_baseline, delta=0.2)

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
