"""Integration tests verifying behavior across full temporal scenarios."""
import unittest
from window_sense.inference import WindowInferenceEngine
from window_sense.features import SensorReading


class TestScenarios(unittest.TestCase):
    def test_winter_cold_shock_detection(self):
        """True Positive: Cold window opened at minute 15 for 15 minutes."""
        engine = WindowInferenceEngine(
            open_threshold=0.80,
            close_threshold=0.25,
            open_persistence_min=3,
            close_persistence_min=8,
        )

        t0 = 10000.0
        detected = False
        first_detected_min = None

        for m in range(45):
            # Window opens at m=15
            if m < 15:
                indoor_t = 21.5 - (m * 0.01)
                rh = 42.0
            elif 15 <= m < 30:
                # Window open: steep drop to 16°C
                progress = (m - 15) / 15.0
                indoor_t = 21.5 - (5.5 * progress)
                rh = 42.0 + (18.0 * progress)
            else:
                # Window closed: gradual rebound
                progress = (m - 30) / 15.0
                indoor_t = 16.0 + (2.5 * progress)
                rh = 60.0 - (10.0 * progress)

            state = engine.process_reading(SensorReading(
                timestamp=t0 + (m * 60),
                indoor_temp=indoor_t,
                outdoor_temp=1.0,
                indoor_humidity=rh,
                outdoor_humidity=90.0,
                reference_temp=21.0,
            ))

            if state.is_open and not detected:
                detected = True
                first_detected_min = m

        self.assertTrue(detected)
        self.assertIsNotNone(first_detected_min)
        # Should detect within 3 to 9 minutes of opening ramp starting at m=15
        self.assertTrue(17 <= first_detected_min <= 24)

    def test_shower_steam_false_positive_rejection(self):
        """False Positive candidate: Shower steam spikes humidity while temp stays warm."""
        engine = WindowInferenceEngine()
        t0 = 10000.0

        for m in range(30):
            if m < 10:
                indoor_t = 22.0
                rh = 50.0
            elif 10 <= m < 20:
                # Shower: humidity spikes from 50% to 92%, temp rises slightly to 23.2°C
                indoor_t = 22.0 + ((m - 10) * 0.12)
                rh = 50.0 + ((m - 10) * 4.2)
            else:
                indoor_t = 23.2 - ((m - 20) * 0.05)
                rh = 92.0 - ((m - 20) * 2.0)

            state = engine.process_reading(SensorReading(
                timestamp=t0 + (m * 60),
                indoor_temp=indoor_t,
                outdoor_temp=8.0,
                indoor_humidity=rh,
                outdoor_humidity=75.0,
            ))

            # MUST NEVER declare window open
            self.assertFalse(state.is_open)
            self.assertTrue(state.confidence < 0.70)

    def test_radiator_cycle_off_false_positive_rejection(self):
        """False Positive candidate: Radiator turns off; slow exponential thermal inertia cooling."""
        engine = WindowInferenceEngine()
        t0 = 10000.0

        for m in range(40):
            # Slow cooling at ~0.6°C/h
            indoor_t = 22.0 - (m * 0.01)
            state = engine.process_reading(SensorReading(
                timestamp=t0 + (m * 60),
                indoor_temp=indoor_t,
                outdoor_temp=4.0,
                indoor_humidity=45.0,
                outdoor_humidity=80.0,
                reference_temp=21.8 - (m * 0.01),  # Both rooms drift down similarly
                hvac_state="idle",
            ))

            # Must never declare window open
            self.assertFalse(state.is_open)


if __name__ == "__main__":
    unittest.main()
