"""Unit tests for psychrometric and thermodynamic calculations."""
import unittest
from window_sense.features import (
    calc_saturation_vapor_pressure,
    calc_actual_vapor_pressure,
    calc_absolute_humidity,
    calc_dew_point,
)


class TestPhysics(unittest.TestCase):
    def test_saturation_vapor_pressure_at_20c(self):
        """At 20°C, saturation vapor pressure of water is ~23.38 hPa."""
        p_sat = calc_saturation_vapor_pressure(20.0)
        self.assertTrue(23.0 < p_sat < 23.8)

    def test_absolute_humidity_magnus_tetens(self):
        """At 20°C and 50% RH, absolute humidity is approximately 8.65 g/m³."""
        ah = calc_absolute_humidity(20.0, 50.0)
        self.assertTrue(8.4 < ah < 8.9)

    def test_dew_point_calculation(self):
        """At 20°C and 50% RH, dew point is approximately 9.3°C."""
        dp = calc_dew_point(20.0, 50.0)
        self.assertTrue(9.0 < dp < 9.6)

    def test_null_and_boundary_handling(self):
        """Handles None and extreme boundary conditions gracefully."""
        self.assertEqual(calc_absolute_humidity(None, 50.0), 0.0)
        self.assertEqual(calc_absolute_humidity(20.0, None), 0.0)
        self.assertEqual(calc_dew_point(None, 50.0), -50.0)
        self.assertEqual(calc_dew_point(20.0, 0.0), -50.0)


if __name__ == "__main__":
    unittest.main()
