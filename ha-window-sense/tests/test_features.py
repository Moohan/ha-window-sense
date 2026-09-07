"""Unit tests for rolling feature extraction and derivatives."""
import unittest
from window_sense.features import (
    SensorReading,
    FeatureExtractor,
    calc_absolute_humidity,
)


class TestFeatures(unittest.TestCase):
    def test_feature_extractor_rolling_deltas(self):
        extractor = FeatureExtractor(max_history_minutes=30)

        # Feed 15 minutes of data, 1 reading per minute
        # Temp steadily drops from 21.0 to 19.5 (-1.5°C in 15m => -6.0°C/h)
        start_time = 10000.0
        for m in range(16):
            t = start_time + (m * 60)
            temp = 21.0 - (m * 0.1)
            reading = SensorReading(
                timestamp=t,
                indoor_temp=temp,
                outdoor_temp=5.0,
                indoor_humidity=45.0,
                outdoor_humidity=70.0,
            )
            extractor.add_reading(reading)

        features = extractor.extract(baseline_expected_temp=21.0)

        self.assertEqual(features.sample_count, 16)
        self.assertAlmostEqual(features.delta_1m, -0.1, delta=0.05)
        self.assertAlmostEqual(features.delta_5m, -0.5, delta=0.05)
        self.assertAlmostEqual(features.delta_10m, -1.0, delta=0.05)
        self.assertAlmostEqual(features.temp_rate, -6.0, delta=0.2)
        self.assertAlmostEqual(features.temp_diff, 19.5 - 5.0, delta=0.05)
        self.assertAlmostEqual(features.thermal_residual, 19.5 - 21.0, delta=0.05)

    def test_reference_room_divergence(self):
        extractor = FeatureExtractor(max_history_minutes=30)
        start_time = 10000.0

        for m in range(10):
            t = start_time + (m * 60)
            reading = SensorReading(
                timestamp=t,
                indoor_temp=21.0 - (m * 0.2),       # bedroom rapidly cooling (-12°C/h)
                outdoor_temp=5.0,
                reference_temp=21.0 - (m * 0.02),   # living room steady (-1.2°C/h)
            )
            extractor.add_reading(reading)

        features = extractor.extract(baseline_expected_temp=21.0)
        self.assertTrue(features.ref_room_diff_rate > 9.0)


if __name__ == "__main__":
    unittest.main()
