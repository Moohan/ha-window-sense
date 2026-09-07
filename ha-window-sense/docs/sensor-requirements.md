# Sensor Requirements & Placement Recommendations

To ensure optimal detection speed (<5 minutes) and zero nuisance false alarms, follow these sensor recommendations:

## 1. Sensor Hardware Recommendations
- **Resolution**: 0.1°C temperature resolution and 1% RH resolution.
- **Reporting Interval**:
  - **Ideal**: Report on 0.1°C change or at least once every 60 seconds.
  - **Acceptable**: Maximum heartbeat reporting period $\le 3\text{ minutes}$.
- **Protocols**: Zigbee 3.0 (e.g., Aqara, Sonoff, Tuya, Heiman) or ESPHome BLE / WiFi sensors.

## 2. Sensor Placement Guidelines
- **Height**: 1.2m to 1.6m above the floor (breathing/living zone).
- **Distance from Windows**: 1.5m to 3.5m from the exterior window. Placing directly on the sill produces extreme localized flutter; placing across a large room increases detection latency.
- **Direct Sunlight**: Keep sensor away from direct solar exposure (avoid thermal radiation bias).
- **Radiator/HVAC Proximity**: Keep at least 1.5m away from direct convection heat sources or AC supply registers.

## 3. Optional Reference Sensor Placement
- Having an indoor reference sensor in a hallway or adjacent interior room substantially enhances false positive immunity against central heating setbacks or house-wide cooling.
