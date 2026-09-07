# Window Sense: Algorithmic Architecture Specification

## 1. Executive Summary
Traditional home automation window detection relies on magnetic reed switches or tilt sensors placed on window sashes. Window Sense provides **non-intrusive window-open detection** using existing room climate telemetry:
- Indoor temperature & relative humidity
- Outdoor weather or local external sensor
- Optional adjacent reference room sensor
- Optional HVAC state feedback

The integration runs entirely locally within Home Assistant with negligible CPU overhead (<1ms per evaluation).

---

## 2. Thermodynamic & Psychrometric Foundations

### 2.1 Magnus-Tetens Formulation
Relative humidity ($RH$) is dependent on temperature; when room air cools rapidly from an open window, $RH$ rises even if no moisture is added. To detect true air exchange, WindowSense calculates **Absolute Humidity** ($AH$) in $g/m^3$:

$$P_{sat}(T) = 6.112 \cdot \exp\left(\frac{17.67 \cdot T}{T + 243.5}\right)$$

$$P_{act}(T, RH) = \frac{RH}{100} \cdot P_{sat}(T)$$

$$AH(T, RH) = \frac{216.7 \cdot P_{act}(T, RH)}{T + 273.15}$$

When a window is opened, the room's absolute humidity rapidly trends toward outdoor absolute humidity.

---

## 3. The 4-Stage Inference Pipeline

### Stage 1: Feature Extraction
- **Rolling deltas**: $\Delta_{1m}$, $\Delta_{5m}$, $\Delta_{10m}$, $\Delta_{20m}$
- **Derivative ($dT/dt$)**: Hourly thermal velocity in $^\circ\text{C}/\text{h}$
- **Acceleration ($d^2T/dt^2$)**: Second derivative distinguishing natural exponential decay from forced convection
- **Indoor/Outdoor gradient**: $\Delta T = T_{indoor} - T_{outdoor}$
- **Reference room divergence**: $\Delta (dT/dt)_{local} - (dT/dt)_{ref}$

### Stage 2: Adaptive Baseline Model
An exponential moving average models normal thermal equilibrium:
$$T_{expected}(t) = (1 - \alpha) \cdot T_{expected}(t-1) + \alpha \cdot \left[0.92 \cdot T_{in} + 0.08 \cdot T_{out}\right]$$
**Critical Principle**: When a window open event is detected or suspected, updates to $T_{expected}$ are **frozen** so that the system does not learn that an open window is normal.

### Stage 3: Page-Hinkley Change-Point Detection (CUSUM)
Detects sharp, sudden inflections in the thermal residual $R(t) = T_{in}(t) - T_{expected}(t)$:
$$S_n = \sum_{i=1}^n (|R_i| - \alpha)$$
$$m_n = \min_{1 \le i \le n} S_i$$
When $S_n - m_n > \lambda$, a change-point trigger is fired.

### Stage 4: Continuous Multi-Evidence Fusion
Positive evidence signals (rapid cooling, residual deviation, gradient, moisture alignment, reference divergence) are weighted into a raw score (0.0 – 1.0).

**Negative Evidence Suppression** penalizes false alarms:
1. **Recent heating cycle-off**: Heating turned off within 15 minutes.
2. **Outdoor cannot explain cooling**: Outdoor warmer than indoor, yet room is cooling.
3. **Multi-room global drop**: House-wide thermostat setback.
4. **Internal moisture source**: Shower steam or boiling water (humidity spike without temperature drop).

### Stage 5: Asymmetric Hysteresis State Machine
- **Entering OPEN**: Requires confidence $\ge 80\%$ sustained for 3 consecutive minutes.
- **Returning to CLOSED**: Requires confidence $\le 25\%$ sustained for 10 consecutive minutes.
