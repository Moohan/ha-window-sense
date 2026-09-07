"""Verification that the pure inference engine runs completely independent of Home Assistant."""
import sys
import unittest


class TestPureEngineIndependence(unittest.TestCase):
    def test_imports_without_homeassistant(self):
        """Verify window_sense has zero imports or dependencies on homeassistant."""
        # Check that homeassistant is not in sys.modules prior to import
        self.assertFalse(any("homeassistant" in mod for mod in sys.modules))

        import window_sense
        from window_sense.const import (
            DEFAULT_OPEN_THRESHOLD,
            DEFAULT_CLOSE_THRESHOLD,
            QUALITY_EXCELLENT,
        )
        from window_sense.features import (
            SensorReading,
            ExtractedFeatures,
            FeatureExtractor,
            calc_saturation_vapor_pressure,
            calc_actual_vapor_pressure,
            calc_absolute_humidity,
            calc_dew_point,
        )
        from window_sense.evidence import EvidenceScore, EvidenceScorer
        from window_sense.inference import (
            AdaptiveBaselineModel,
            PageHinkleyChangePoint,
            WindowState,
            WindowInferenceEngine,
        )

        # Confirm that NO homeassistant module was loaded as a side effect
        ha_loaded = [mod for mod in sys.modules if mod.startswith("homeassistant")]
        self.assertEqual(ha_loaded, [], f"Home Assistant modules were unexpectedly imported: {ha_loaded}")

    def test_end_to_end_inference_without_homeassistant(self):
        """Verify complete inference lifecycle executes in pure Python."""
        from window_sense.inference import WindowInferenceEngine
        from window_sense.features import SensorReading

        engine = WindowInferenceEngine(open_persistence_min=2)
        for m in range(3):
            state = engine.process_reading(SensorReading(
                timestamp=1700000000.0 + (m * 60),
                indoor_temp=21.5,
                outdoor_temp=2.0,
                indoor_humidity=45.0,
                outdoor_humidity=85.0,
            ))

        self.assertFalse(state.is_open)
        self.assertIsNotNone(state.confidence)
        self.assertIsNotNone(state.primary_reason)
        self.assertEqual(state.detection_quality, "good")


if __name__ == "__main__":
    unittest.main()
