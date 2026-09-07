#!/usr/bin/env python3
"""CLI Replay Harness for WindowSense.

Usage:
    python replay.py --scenario winter_shock
    python replay.py --file recorded_ha_sensor_data.json
"""
import argparse
import json
import sys
import os

# Add parent directory to sys.path so custom_components can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from window_sense.inference import WindowInferenceEngine
from window_sense.features import SensorReading


def replay_fixture(readings_path: str):
    """Replays sensor readings from a JSON file and prints inference timeline."""
    with open(readings_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    engine = WindowInferenceEngine()
    print(f"{'Time (m)':<10} | {'T_in (°C)':<10} | {'T_out':<8} | {'RH_in (%)':<10} | {'Conf (%)':<9} | {'State':<10} | {'Reason'}")
    print("-" * 95)

    for item in data:
        t_sec = item.get("time_min", 0) * 60.0
        reading = SensorReading(
            timestamp=t_sec,
            indoor_temp=item["indoor_temp"],
            outdoor_temp=item["outdoor_temp"],
            indoor_humidity=item.get("indoor_rh"),
            outdoor_humidity=item.get("outdoor_rh"),
            reference_temp=item.get("ref_temp"),
            hvac_state=item.get("hvac", "idle"),
        )
        state = engine.process_reading(reading)
        status_str = "OPEN" if state.is_open else "CLOSED"
        conf_pct = round(state.confidence * 100)

        print(
            f"{item.get('time_min', 0):<10} | "
            f"{reading.indoor_temp:<10.1f} | "
            f"{reading.outdoor_temp:<8.1f} | "
            f"{reading.indoor_humidity or 0:<10.1f} | "
            f"{conf_pct:<9} | "
            f"{status_str:<10} | "
            f"{state.primary_reason[:30]}..."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Replay sensor data through WindowSense")
    parser.add_argument(
        "--file",
        default=os.path.join(os.path.dirname(__file__), "../tests/fixtures/sample_readings.json"),
        help="Path to JSON readings file",
    )
    args = parser.parse_args()
    replay_fixture(args.file)
