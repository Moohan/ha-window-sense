import { SensorReading, TestScenario } from '../types';

export const TEST_SCENARIOS: TestScenario[] = [
  {
    id: 'winter_cold_shock',
    title: 'Winter Cold Shock (Window Fully Open)',
    category: 'True Positive',
    description: 'Outdoor temperature is 3.5°C. Room is at 21.2°C. Window opens at min 20 and closes at min 45. Demonstrates rapid cooling and absolute humidity drop.',
    durationMinutes: 70,
    windowOpenPeriods: [{ startMin: 20, endMin: 45 }],
    generateData: () => {
      const readings: SensorReading[] = [];
      const baseTime = 1710000000000;
      let indoorTemp = 21.2;
      let indoorRH = 48.0;
      const outdoorTemp = 3.5;
      const outdoorRH = 85.0;
      let refTemp = 21.0;

      for (let m = 0; m <= 70; m++) {
        const isOpen = m >= 20 && m < 45;
        const noise = (Math.sin(m * 0.7) * 0.05) + (Math.cos(m * 1.3) * 0.04);
        
        if (isOpen) {
          // Rapid infiltration of cold outdoor air
          indoorTemp -= 0.18 + (Math.random() * 0.04);
          // Outdoor air at 3.5°C and 85% RH has AH ~ 5.3 g/m³. Indoor AH drops.
          indoorRH = Math.max(30, indoorRH - 0.4);
          // Reference room stays warm
          refTemp -= 0.01;
        } else if (m >= 45) {
          // Closed, heating recovers
          indoorTemp = Math.min(21.0, indoorTemp + 0.07);
          indoorRH = Math.min(46, indoorRH + 0.15);
        } else {
          // Normal baseline
          indoorTemp += noise * 0.1;
        }

        readings.push({
          timestamp: baseTime + m * 60 * 1000,
          indoorTemp: parseFloat((indoorTemp + noise).toFixed(2)),
          outdoorTemp: parseFloat((outdoorTemp + (m * 0.01)).toFixed(2)),
          indoorHumidity: parseFloat(indoorRH.toFixed(1)),
          outdoorHumidity: outdoorRH,
          referenceTemp: parseFloat(refTemp.toFixed(2)),
          referenceHumidity: 48,
          hvacState: m >= 45 ? 'heating' : 'idle',
        });
      }
      return readings;
    },
  },
  {
    id: 'summer_heat_rush',
    title: 'Summer Heat Rush (Window Opened in Heatwave)',
    category: 'True Positive',
    description: 'Outdoor temperature is 33.0°C. Air-conditioned room is at 22.0°C. Window opens at min 25 to min 50. Tests positive temperature anomaly when outdoor is hotter.',
    durationMinutes: 75,
    windowOpenPeriods: [{ startMin: 25, endMin: 50 }],
    generateData: () => {
      const readings: SensorReading[] = [];
      const baseTime = 1710000000000;
      let indoorTemp = 22.0;
      let indoorRH = 42.0;
      const outdoorTemp = 33.2;
      const outdoorRH = 65.0; // very humid outside
      let refTemp = 22.1;

      for (let m = 0; m <= 75; m++) {
        const isOpen = m >= 25 && m < 50;
        const noise = Math.sin(m * 0.5) * 0.04;

        if (isOpen) {
          indoorTemp += 0.14 + (Math.random() * 0.03);
          indoorRH += 0.6; // humid outdoor air rushes in
          refTemp += 0.01;
        } else if (m >= 50) {
          indoorTemp = Math.max(22.2, indoorTemp - 0.09);
          indoorRH = Math.max(44, indoorRH - 0.3);
        }

        readings.push({
          timestamp: baseTime + m * 60 * 1000,
          indoorTemp: parseFloat((indoorTemp + noise).toFixed(2)),
          outdoorTemp: parseFloat((outdoorTemp + Math.sin(m * 0.1) * 0.3).toFixed(2)),
          indoorHumidity: parseFloat(indoorRH.toFixed(1)),
          outdoorHumidity: outdoorRH,
          referenceTemp: parseFloat(refTemp.toFixed(2)),
          referenceHumidity: 43,
          hvacState: isOpen ? 'idle' : 'cooling',
        });
      }
      return readings;
    },
  },
  {
    id: 'partial_window_ventilation',
    title: 'Partial Window Tilt / Trickle Vent',
    category: 'True Positive',
    description: 'Window tilted open slightly in cool weather (outdoor 8°C). Slower cooling slope (-0.8°C/h) that tests sensitivity and baseline residual detection.',
    durationMinutes: 80,
    windowOpenPeriods: [{ startMin: 20, endMin: 60 }],
    generateData: () => {
      const readings: SensorReading[] = [];
      const baseTime = 1710000000000;
      let indoorTemp = 20.8;
      let indoorRH = 50.0;
      const outdoorTemp = 8.0;

      for (let m = 0; m <= 80; m++) {
        const isOpen = m >= 20 && m < 60;
        if (isOpen) {
          indoorTemp -= 0.045; // subtle steady drop
          indoorRH -= 0.12;
        } else if (m >= 60) {
          indoorTemp += 0.03;
        }

        readings.push({
          timestamp: baseTime + m * 60 * 1000,
          indoorTemp: parseFloat((indoorTemp + Math.sin(m * 0.8) * 0.03).toFixed(2)),
          outdoorTemp: outdoorTemp,
          indoorHumidity: parseFloat(indoorRH.toFixed(1)),
          outdoorHumidity: 78,
          referenceTemp: 20.7,
          referenceHumidity: 50,
          hvacState: 'idle',
        });
      }
      return readings;
    },
  },
  {
    id: 'ventilation_during_heating',
    title: 'Ventilation While Radiator Is Active',
    category: 'True Positive',
    description: 'Radiator heating is on full blast, but window is opened at min 30. Demonstrates how strong thermal anomaly overcomes the heating gain.',
    durationMinutes: 70,
    windowOpenPeriods: [{ startMin: 30, endMin: 55 }],
    generateData: () => {
      const readings: SensorReading[] = [];
      const baseTime = 1710000000000;
      let indoorTemp = 19.5;
      const outdoorTemp = 2.0;

      for (let m = 0; m <= 70; m++) {
        const isOpen = m >= 30 && m < 55;
        if (m < 30) {
          indoorTemp += 0.05; // heating up
        } else if (isOpen) {
          indoorTemp -= 0.12; // cooling despite heater on!
        } else {
          indoorTemp += 0.08; // heating resumes
        }

        readings.push({
          timestamp: baseTime + m * 60 * 1000,
          indoorTemp: parseFloat(indoorTemp.toFixed(2)),
          outdoorTemp,
          indoorHumidity: 45,
          outdoorHumidity: 85,
          referenceTemp: 21.0,
          hvacState: 'heating',
          heatingPower: 100,
        });
      }
      return readings;
    },
  },
  {
    id: 'radiator_thermostat_decay',
    title: 'Radiator Cycles Off (False Positive Candidate)',
    category: 'False Positive Candidate',
    description: 'Radiator clicks off at min 20. Room slowly cools by 1.1°C over 40 minutes, matching adjacent reference room. Should NOT trigger window open!',
    durationMinutes: 70,
    windowOpenPeriods: [],
    generateData: () => {
      const readings: SensorReading[] = [];
      const baseTime = 1710000000000;
      let indoorTemp = 22.4;
      let refTemp = 22.3;
      const outdoorTemp = 7.0;

      for (let m = 0; m <= 70; m++) {
        const hvacState = m < 20 ? 'heating' : 'idle';
        if (m >= 20) {
          // Slow natural building thermal decay
          indoorTemp -= 0.022;
          refTemp -= 0.021; // Reference room drops similarly
        }

        readings.push({
          timestamp: baseTime + m * 60 * 1000,
          indoorTemp: parseFloat((indoorTemp + Math.sin(m * 0.4) * 0.02).toFixed(2)),
          outdoorTemp,
          indoorHumidity: 45,
          outdoorHumidity: 80,
          referenceTemp: parseFloat(refTemp.toFixed(2)),
          referenceHumidity: 46,
          hvacState,
        });
      }
      return readings;
    },
  },
  {
    id: 'shower_moisture_event',
    title: 'En-Suite Shower Steam Spike (False Positive Candidate)',
    category: 'False Positive Candidate',
    description: 'Hot shower causes indoor humidity to jump from 45% to 88% while temperature stays warm (21.5°C). The algorithm must recognize this as internal steam, not a cold window.',
    durationMinutes: 60,
    windowOpenPeriods: [],
    generateData: () => {
      const readings: SensorReading[] = [];
      const baseTime = 1710000000000;
      let indoorTemp = 21.5;
      let indoorRH = 45.0;

      for (let m = 0; m <= 60; m++) {
        if (m >= 15 && m < 30) {
          indoorRH = Math.min(88, indoorRH + 3.0);
          indoorTemp += 0.03; // hot shower warms room slightly
        } else if (m >= 30) {
          indoorRH = Math.max(50, indoorRH - 0.8);
        }

        readings.push({
          timestamp: baseTime + m * 60 * 1000,
          indoorTemp: parseFloat(indoorTemp.toFixed(2)),
          outdoorTemp: 4.0,
          indoorHumidity: parseFloat(indoorRH.toFixed(1)),
          outdoorHumidity: 70,
          referenceTemp: 21.2,
          hvacState: 'idle',
        });
      }
      return readings;
    },
  },
  {
    id: 'cooking_thermal_burst',
    title: 'Kitchen Cooking / Oven Heat (False Positive Candidate)',
    category: 'False Positive Candidate',
    description: 'Oven and stove produce warmth (+1.8°C) and steam without outdoor ventilation. Must reject open window inference.',
    durationMinutes: 65,
    windowOpenPeriods: [],
    generateData: () => {
      const readings: SensorReading[] = [];
      const baseTime = 1710000000000;
      let indoorTemp = 20.5;
      let indoorRH = 45;

      for (let m = 0; m <= 65; m++) {
        if (m >= 15 && m < 45) {
          indoorTemp += 0.07;
          indoorRH += 0.3;
        } else if (m >= 45) {
          indoorTemp -= 0.04;
        }

        readings.push({
          timestamp: baseTime + m * 60 * 1000,
          indoorTemp: parseFloat(indoorTemp.toFixed(2)),
          outdoorTemp: 5.0,
          indoorHumidity: parseFloat(indoorRH.toFixed(1)),
          outdoorHumidity: 80,
          referenceTemp: 20.6,
          hvacState: 'idle',
        });
      }
      return readings;
    },
  },
  {
    id: 'occupancy_body_heat',
    title: 'People Entering Room (False Positive Candidate)',
    category: 'False Positive Candidate',
    description: 'Several people enter the room. Temperature drifts up +0.4°C and CO2 increases. Window stays closed.',
    durationMinutes: 60,
    windowOpenPeriods: [],
    generateData: () => {
      const readings: SensorReading[] = [];
      const baseTime = 1710000000000;
      let indoorTemp = 20.8;
      let co2 = 520;

      for (let m = 0; m <= 60; m++) {
        if (m >= 20 && m < 50) {
          indoorTemp += 0.015;
          co2 = Math.min(1350, co2 + 30);
        } else if (m >= 50) {
          co2 = Math.max(600, co2 - 20);
        }

        readings.push({
          timestamp: baseTime + m * 60 * 1000,
          indoorTemp: parseFloat(indoorTemp.toFixed(2)),
          outdoorTemp: 9.0,
          indoorHumidity: 48,
          outdoorHumidity: 70,
          referenceTemp: 20.8,
          co2: Math.round(co2),
          occupancy: m >= 20 && m < 50,
        });
      }
      return readings;
    },
  },
  {
    id: 'solar_gain_afternoon',
    title: 'Solar Gain / Sun Through Window (False Positive Candidate)',
    category: 'False Positive Candidate',
    description: 'Afternoon sun directly heats the bedroom window sill, raising room temperature from 20.5°C to 23.2°C gradually while outdoor is 12°C. Window is closed.',
    durationMinutes: 90,
    windowOpenPeriods: [],
    generateData: () => {
      const readings: SensorReading[] = [];
      const baseTime = 1710000000000;
      let indoorTemp = 20.5;

      for (let m = 0; m <= 90; m++) {
        if (m >= 20 && m < 70) {
          indoorTemp += 0.055;
        } else if (m >= 70) {
          indoorTemp -= 0.02;
        }

        readings.push({
          timestamp: baseTime + m * 60 * 1000,
          indoorTemp: parseFloat(indoorTemp.toFixed(2)),
          outdoorTemp: 12.0 + Math.sin(m * 0.03) * 2.0,
          indoorHumidity: 42,
          outdoorHumidity: 65,
          referenceTemp: 21.0,
          hvacState: 'idle',
        });
      }
      return readings;
    },
  },
  {
    id: 'sudden_outdoor_cold_front',
    title: 'Outdoor Cold Front (Building Envelope Delay)',
    category: 'False Positive Candidate',
    description: 'Outdoor temperature drops sharply from 15°C down to 4°C over 1 hour. Well-insulated indoor room cools with a normal 0.3°C lag without window open.',
    durationMinutes: 80,
    windowOpenPeriods: [],
    generateData: () => {
      const readings: SensorReading[] = [];
      const baseTime = 1710000000000;
      let outdoorTemp = 15.0;
      let indoorTemp = 21.5;
      let refTemp = 21.4;

      for (let m = 0; m <= 80; m++) {
        if (m >= 15 && m < 60) {
          outdoorTemp -= 0.24; // severe outdoor cold front
          indoorTemp -= 0.012; // slow envelope diffusion
          refTemp -= 0.011;
        }

        readings.push({
          timestamp: baseTime + m * 60 * 1000,
          indoorTemp: parseFloat(indoorTemp.toFixed(2)),
          outdoorTemp: parseFloat(outdoorTemp.toFixed(2)),
          indoorHumidity: 45,
          outdoorHumidity: 88,
          referenceTemp: parseFloat(refTemp.toFixed(2)),
          hvacState: 'idle',
        });
      }
      return readings;
    },
  },
  {
    id: 'sensor_dropout_recovery',
    title: 'Sensor Packet Loss & Recovery',
    category: 'Edge Case',
    description: 'Zigbee sensor drops offline for 12 minutes (unavailable state), then reconnects with normal readings. Tests graceful degradation and readiness recovery.',
    durationMinutes: 60,
    windowOpenPeriods: [],
    generateData: () => {
      const readings: SensorReading[] = [];
      const baseTime = 1710000000000;

      for (let m = 0; m <= 60; m++) {
        // Between min 20 and 32, sensor packet loss occurs
        const isOffline = m >= 20 && m < 32;
        
        readings.push({
          timestamp: baseTime + m * 60 * 1000,
          indoorTemp: isOffline ? 20.8 : parseFloat((20.8 + Math.sin(m * 0.5) * 0.05).toFixed(2)),
          outdoorTemp: 6.0,
          indoorHumidity: isOffline ? undefined : 48,
          outdoorHumidity: 75,
          referenceTemp: 20.7,
        });
      }
      return readings;
    },
  },
];
