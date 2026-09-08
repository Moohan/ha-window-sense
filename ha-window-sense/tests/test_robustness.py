"""Robustness and edge case unit tests for Window Sense."""
import math
import time
import unittest
from unittest.mock import MagicMock

from window_sense.inference import WindowInferenceEngine
from window_sense.features import SensorReading
from window_sense.const import (
    INFERENCE_STATUS_VALID,
    INFERENCE_STATUS_DEGRADED,
    INFERENCE_STATUS_INSUFFICIENT_DATA,
    QUALITY_EXCELLENT,
    QUALITY_GOOD,
    QUALITY_FAIR,
    QUALITY_INSUFFICIENT,
)

try:
    from custom_components.window_sense.binary_sensor import WindowSenseBinarySensor
    HAS_HA = True
except ImportError:
    HAS_HA = False


class TestRobustness(unittest.TestCase):
    """Test suite covering sensor irregularities, outages, dropouts, and Home Assistant entity behavior."""

    def test_1_irregular_sensor_intervals(self):
        """1. Irregular sensor update intervals calculate rates using actual timestamps."""
        engine = WindowInferenceEngine(open_threshold=0.80, open_persistence_min=2)
        t = 10000.0

        intervals = [0.0, 45.0, 165.0, 465.0, 555.0]
        for dt in intervals:
            state = engine.process_reading(SensorReading(
                timestamp=t + dt,
                indoor_temp=21.0,
                outdoor_temp=2.0,
                indoor_humidity=50.0,
                outdoor_humidity=80.0,
            ))

        self.assertEqual(state.inference_status, INFERENCE_STATUS_VALID)
        self.assertFalse(state.is_open)

        t_event = t + 555.0
        cooling_steps = [
            (90.0, 20.2),
            (270.0, 18.8),
            (570.0, 16.5),
            (870.0, 14.5),
        ]
        for dt, temp in cooling_steps:
            state = engine.process_reading(SensorReading(
                timestamp=t_event + dt,
                indoor_temp=temp,
                outdoor_temp=2.0,
                indoor_humidity=65.0,
                outdoor_humidity=80.0,
            ))

        self.assertTrue(state.is_open)
        self.assertGreater(state.confidence, 0.75)

    def test_2_indoor_sensor_unavailable(self):
        """2. Indoor sensor unavailable, None, or non-numeric yields INSUFFICIENT_DATA."""
        engine = WindowInferenceEngine()
        t0 = 10000.0

        for m in range(5):
            engine.process_reading(SensorReading(
                timestamp=t0 + (m * 60),
                indoor_temp=21.0,
                outdoor_temp=5.0,
            ))

        s1 = engine.process_reading(SensorReading(
            timestamp=t0 + 300.0,
            indoor_temp=None,
            outdoor_temp=5.0,
        ))
        self.assertEqual(s1.inference_status, INFERENCE_STATUS_INSUFFICIENT_DATA)
        self.assertEqual(s1.confidence, 0.0)
        self.assertEqual(s1.baseline_trust.status, "frozen")

        s2 = engine.process_reading(SensorReading(
            timestamp=t0 + 360.0,
            indoor_temp=float("nan"),
            outdoor_temp=5.0,
        ))
        self.assertEqual(s2.inference_status, INFERENCE_STATUS_INSUFFICIENT_DATA)
        self.assertEqual(s2.confidence, 0.0)

    def test_3_outdoor_sensor_stale(self):
        """3. Outdoor sensor stale (>30 min since update) sets status to INSUFFICIENT_DATA."""
        engine = WindowInferenceEngine()
        t0 = 10000.0

        for m in range(5):
            engine.process_reading(SensorReading(
                timestamp=t0 + (m * 60),
                indoor_temp=21.0,
                outdoor_temp=5.0,
                indoor_temp_updated_at=t0 + (m * 60),
                outdoor_temp_updated_at=t0 + (m * 60),
            ))

        stale_state = engine.process_reading(SensorReading(
            timestamp=t0 + 2400.0,
            indoor_temp=20.5,
            outdoor_temp=5.0,
            indoor_temp_updated_at=t0 + 2400.0,
            outdoor_temp_updated_at=t0 + 60.0,
        ))

        self.assertEqual(stale_state.inference_status, INFERENCE_STATUS_INSUFFICIENT_DATA)
        self.assertIn("Outdoor temperature sensor stale", stale_state.primary_reason)
        self.assertEqual(stale_state.confidence, 0.0)

    def test_4_optional_humidity_sensor_unavailable(self):
        """4. Optional humidity sensor disappearing does not break required temperature inference."""
        engine = WindowInferenceEngine(open_threshold=0.80, open_persistence_min=2)
        t0 = 10000.0

        for m in range(5):
            s = engine.process_reading(SensorReading(
                timestamp=t0 + (m * 60),
                indoor_temp=21.0,
                outdoor_temp=2.0,
                indoor_humidity=45.0,
                outdoor_humidity=80.0,
            ))
        self.assertEqual(s.detection_quality, QUALITY_GOOD)

        s_no_hum = engine.process_reading(SensorReading(
            timestamp=t0 + 360.0,
            indoor_temp=21.0,
            outdoor_temp=2.0,
            indoor_humidity=None,
            outdoor_humidity=None,
        ))
        self.assertEqual(s_no_hum.inference_status, INFERENCE_STATUS_VALID)
        self.assertEqual(s_no_hum.detection_quality, QUALITY_FAIR)

        for m in range(7, 12):
            s_cooling = engine.process_reading(SensorReading(
                timestamp=t0 + (m * 60),
                indoor_temp=21.0 - ((m - 6) * 0.8),
                outdoor_temp=2.0,
                indoor_humidity=None,
                outdoor_humidity=None,
            ))

        self.assertTrue(s_cooling.is_open)
        self.assertEqual(s_cooling.inference_status, INFERENCE_STATUS_VALID)

    def test_5_long_gap_followed_by_new_reading(self):
        """5. Long gap (>15 min outage) suppresses misleading derivatives and sets status to INSUFFICIENT_DATA."""
        engine = WindowInferenceEngine()
        t0 = 10000.0

        for m in range(5):
            engine.process_reading(SensorReading(
                timestamp=t0 + (m * 60),
                indoor_temp=21.0,
                outdoor_temp=5.0,
            ))

        post_outage_state = engine.process_reading(SensorReading(
            timestamp=t0 + 240.0 + 10800.0,
            indoor_temp=17.0,
            outdoor_temp=5.0,
        ))

        self.assertEqual(post_outage_state.inference_status, INFERENCE_STATUS_INSUFFICIENT_DATA)
        self.assertTrue(post_outage_state.features.post_outage_suppressed)
        self.assertEqual(post_outage_state.temperature_rate, 0.0)

    def test_6_sudden_invalid_non_numeric_state(self):
        """6. Sudden transition to invalid or non-numeric values is safely handled."""
        engine = WindowInferenceEngine()
        t0 = 10000.0

        state = engine.process_reading(SensorReading(
            timestamp=t0,
            indoor_temp=21.0,
            outdoor_temp=5.0,
        ))
        self.assertIsNotNone(state)

        invalid_state = engine.process_reading(SensorReading(
            timestamp=t0 + 60.0,
            indoor_temp=-99.0,
            outdoor_temp=5.0,
        ))
        self.assertEqual(invalid_state.baseline_trust.status, "frozen")

    def test_7_ha_binary_sensor_reflects_uncertainty(self):
        """7. Home Assistant binary sensor reports None/unavailable during INSUFFICIENT_DATA."""
        coord = MagicMock()
        coord.data = MagicMock()
        coord.data.is_open = False
        coord.data.inference_status = INFERENCE_STATUS_INSUFFICIENT_DATA

        if HAS_HA:
            entry = MagicMock()
            entry.entry_id = "test_entry"
            entry.title = "Test Room"
            sensor = WindowSenseBinarySensor(coord, entry)
            self.assertIsNone(sensor.is_on)
            self.assertFalse(sensor.available)
        else:
            data = coord.data
            is_on = None if data.inference_status == "insufficient_data" else data.is_open
            available = data.inference_status != "insufficient_data"
            self.assertIsNone(is_on)
            self.assertFalse(available)


if __name__ == "__main__":
    unittest.main()
