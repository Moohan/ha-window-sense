# Window Sense (`ha-window-sense`)

[![HACS Custom Component](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/default)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1+-blue.svg)](https://www.home-assistant.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Window Sense** is a native Home Assistant custom integration that accurately infers whether a window is **OPEN** or **CLOSED** using room temperature, absolute humidity dynamics, and thermodynamic baseline modeling—**without requiring contact sensors on window frames**.

---

## 🌟 Key Features

- **No Contact Sensors Required**: Uses existing indoor/outdoor climate telemetry (Zigbee, Z-Wave, BLE, ESPHome, or weather integrations).
- **Absolute Moisture Infiltration Tracking**: Uses the Magnus-Tetens formula to compute invariant absolute humidity ($g/m^3$), separating air mass exchange from temperature swings.
- **Adaptive Baseline Model**: Models room thermal inertia and automatically freezes updates during suspected open states.
- **Change-Point Detection (CUSUM)**: Employs the Page-Hinkley cumulative sum algorithm for rapid inflection alerts.
- **False-Positive Suppression**: Automatically suppresses false alarms caused by heating shutoffs, shower steam, cooking, or house-wide thermostat setbacks.
- **100% Local & Privacy-Respecting**: Zero cloud dependencies, zero external ML calls, negligible CPU usage (<1ms per update).

---

## 📂 Project Structure

```
ha-window-sense/
│
├── custom_components/
│   └── window_sense/
│       ├── __init__.py           # Integration lifecycle and platform setup
│       ├── manifest.json         # Integration metadata and dependencies
│       ├── const.py              # Constants, thresholds, and keys
│       ├── config_flow.py        # UI configuration and options flow
│       ├── coordinator.py        # DataUpdateCoordinator handling telemetry
│       ├── inference.py          # Baseline model, change-point & state machine
│       ├── features.py           # Psychrometrics & rolling feature extraction
│       ├── evidence.py           # Multi-signal evidence fusion & diagnostics
│       ├── binary_sensor.py      # Main binary_sensor entity (device_class: window)
│       ├── sensor.py             # Confidence, anomaly & rate sensors
│       └── diagnostics.py        # HA diagnostic data dump provider
│
├── tests/
│   ├── test_inference.py         # Unit tests for inference & state machine
│   ├── test_features.py          # Unit tests for feature extraction
│   ├── test_physics.py           # Unit tests for psychrometric formulas
│   ├── test_scenarios.py         # Full temporal scenario benchmark tests
│   └── fixtures/                 # Sample time-series sensor data
│
├── testbed/
│   ├── scenarios/                # Standard test scenario catalog
│   ├── replay.py                 # CLI replay harness
│   └── notebooks/                # Jupyter notebook for calibration analysis
│
├── docs/
│   ├── algorithm.md              # Mathematical and thermodynamic specification
│   └── sensor-requirements.md    # Sensor placement and accuracy guide
│
├── README.md
├── hacs.json                     # HACS distribution manifest
├── pyproject.toml                # Build configuration and test tooling
└── requirements.txt              # Test and development dependencies
```

---

## 🚀 Installation

### Option 1: HACS (Recommended)
1. Open Home Assistant.
2. Go to **HACS** > **Integrations** > Three dots in upper right > **Custom Repositories**.
3. Add repository URL with category **Integration**.
4. Click **Download**, then restart Home Assistant.

### Option 2: Manual Installation
1. Download the `custom_components/window_sense` directory.
2. Copy it into your Home Assistant directory:
   `<config_dir>/custom_components/window_sense/`
3. Restart Home Assistant.

---

## ⚙️ Configuration

1. In Home Assistant, navigate to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for **WindowSense**.
3. Select your room's:
   - **Indoor Temperature Sensor** *(required)*
   - **Outdoor Temperature Sensor** *(required)*
   - **Indoor Humidity Sensor** *(optional, recommended)*
   - **Outdoor Humidity Sensor** *(optional, recommended)*
   - **Reference Adjacent Room Sensor** *(optional)*
   - **HVAC State Entity** *(optional)*
4. Click **Submit**.

---

## 📊 Provided Entities

| Entity ID | Device Class | Description |
|-----------|--------------|-------------|
| `binary_sensor.<room>_window_state` | `window` | `on` when window is open, `off` when closed |
| `sensor.<room>_window_confidence` | `confidence` | Probability score (0% – 100%) |
| `sensor.<room>_thermal_residual` | `temperature` | Temperature deviation from equilibrium (°C) |
| `sensor.<room>_temp_drift_rate` | — | Rate of temperature change (°C/h) |

---

## 💡 Example Automation: Turn off Heating when Window is Open

```yaml
alias: "Turn Off Heating When Bedroom Window Opens"
trigger:
  - platform: state
    entity_id: binary_sensor.bedroom_window_state
    to: "on"
    for:
      minutes: 1
action:
  - service: climate.set_hvac_mode
    target:
      entity_id: climate.bedroom_radiator
    data:
      hvac_mode: "off"
```
