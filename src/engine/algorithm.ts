import {
  AlgorithmConfig,
  EvidenceBreakdown,
  ExtractedFeatures,
  InferredState,
  ModelReadiness,
  SensorReading,
} from '../types';
import { calculateAbsoluteHumidity, calculateDewPoint } from './physics';

export const DEFAULT_CONFIG: AlgorithmConfig = {
  openConfidenceThreshold: 0.80,
  openPersistenceMinutes: 3,
  closeConfidenceThreshold: 0.25,
  closePersistenceMinutes: 10,
  baselineLearningRate: 0.04,
  thermalInertiaFactor: 0.92,
  changePointSensitivity: 1.1,
  minIndoorOutdoorDiffForOpen: 2.0,
  weightResidual: 0.35,
  weightRate: 0.25,
  weightChangePoint: 0.15,
  weightHumidity: 0.15,
  weightReferenceRoom: 0.10,
};

export class WindowInferenceEngine {
  private config: AlgorithmConfig;
  private history: SensorReading[] = [];
  private learnedBaselineTemp: number | null = null;
  private learnedConductance: number = 0.08; // °C per hour per °C gradient
  private learnedHvacGain: number = 2.2; // °C per hour when heating
  private samplesCount: number = 0;
  private firstTimestamp: number | null = null;
  
  // Hysteresis tracking
  private currentState: boolean = false;
  private lastStateChangeTime: number = 0;
  private highConfidenceStartTime: number | null = null;
  private lowConfidenceStartTime: number | null = null;
  
  // Change point detector state (Page-Hinkley cumulative sum)
  private cusumMin: number = 0;
  private cusumValue: number = 0;
  private changePointActive: boolean = false;
  private lastHvacStateChangeTime: number = 0;
  private previousHvacState: string = 'idle';

  constructor(config: Partial<AlgorithmConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  public updateConfig(newConfig: Partial<AlgorithmConfig>): void {
    this.config = { ...this.config, ...newConfig };
  }

  public reset(): void {
    this.history = [];
    this.learnedBaselineTemp = null;
    this.samplesCount = 0;
    this.firstTimestamp = null;
    this.currentState = false;
    this.lastStateChangeTime = 0;
    this.highConfidenceStartTime = null;
    this.lowConfidenceStartTime = null;
    this.cusumMin = 0;
    this.cusumValue = 0;
    this.changePointActive = false;
  }

  /**
   * Processes a new incoming sensor reading and produces an updated InferredState
   */
  public processReading(reading: SensorReading): InferredState {
    this.samplesCount++;
    if (!this.firstTimestamp) {
      this.firstTimestamp = reading.timestamp;
      this.lastStateChangeTime = reading.timestamp;
    }
    
    // Check HVAC state transition for negative evidence tracking
    const currentHvac = reading.hvacState || 'idle';
    if (currentHvac !== this.previousHvacState) {
      this.lastHvacStateChangeTime = reading.timestamp;
      this.previousHvacState = currentHvac;
    }

    // Add reading to sliding history (keep up to 120 minutes of history at 1-min intervals)
    this.history.push(reading);
    if (this.history.length > 180) {
      this.history.shift();
    }

    // 1. Feature Extraction
    const features = this.extractFeatures(reading);

    // 2. Change Point Detection
    this.updateChangePoint(features);

    // 3. Evidence Fusion & Confidence Scoring
    const evidence = this.evaluateEvidence(features, reading);

    // 4. Update Adaptive Baseline (only if NOT suspected to be open)
    this.updateBaseline(reading, features, evidence.finalConfidence);

    // 5. State Decision with Asymmetric Hysteresis
    this.updateHysteresis(reading.timestamp, evidence.finalConfidence);

    // 6. Readiness Evaluation
    const readiness = this.evaluateReadiness(reading);

    // 7. Detection Quality
    const detectionQuality = this.evaluateQuality(reading);

    return {
      isOpen: this.currentState,
      confidence: Math.round(evidence.finalConfidence * 100),
      readiness,
      detectionQuality,
      thermalAnomaly: parseFloat(features.thermalResidual.toFixed(2)),
      temperatureRate: parseFloat(features.tempRate.toFixed(2)),
      indoorTemp: reading.indoorTemp,
      outdoorTemp: reading.outdoorTemp,
      tempDiff: parseFloat(features.tempDiff.toFixed(2)),
      humiditySignal: features.indoorAbsHumidity !== undefined 
        ? `${features.indoorAbsHumidity.toFixed(1)} g/m³ (Δ5m: ${(features.absHumidityDelta5m ?? 0).toFixed(2)})`
        : 'Not Available',
      referenceRoomSignal: features.refRateDiff !== undefined
        ? `Rate diff: ${features.refRateDiff > 0 ? '+' : ''}${features.refRateDiff.toFixed(2)} °C/h`
        : 'No Reference Sensor',
      hvacSignal: reading.hvacState || 'idle',
      modelAgeDays: parseFloat(((reading.timestamp - (this.firstTimestamp || reading.timestamp)) / (86400 * 1000)).toFixed(2)),
      samplesAvailable: this.samplesCount,
      lastStateChange: this.lastStateChangeTime,
      reason: evidence.primaryReason,
      evidence,
      features,
    };
  }

  private extractFeatures(current: SensorReading): ExtractedFeatures {
    const now = current.timestamp;
    
    // Find past readings at target intervals
    const findPast = (minutesAgo: number): SensorReading => {
      const targetTime = now - minutesAgo * 60 * 1000;
      let closest = this.history[0];
      let minDiff = Math.abs(closest.timestamp - targetTime);
      for (const r of this.history) {
        const diff = Math.abs(r.timestamp - targetTime);
        if (diff < minDiff) {
          minDiff = diff;
          closest = r;
        }
      }
      return closest;
    };

    const r1m = findPast(1);
    const r5m = findPast(5);
    const r10m = findPast(10);
    const r20m = findPast(20);

    const delta1m = current.indoorTemp - r1m.indoorTemp;
    const delta5m = current.indoorTemp - r5m.indoorTemp;
    const delta10m = current.indoorTemp - r10m.indoorTemp;
    const delta20m = current.indoorTemp - r20m.indoorTemp;

    // Rate in °C / hour based on 5-minute derivative for noise smoothing
    const dtHours5m = Math.max(0.016, (now - r5m.timestamp) / (3600 * 1000));
    const tempRate = delta5m / dtHours5m;

    // Acceleration (°C / hour²)
    const pastRate10m = (r5m.indoorTemp - r10m.indoorTemp) / Math.max(0.016, (r5m.timestamp - r10m.timestamp) / (3600 * 1000));
    const tempAccel = (tempRate - pastRate10m) / dtHours5m;

    // Outdoor rate
    const outdoorRate = (current.outdoorTemp - r10m.outdoorTemp) / Math.max(0.016, (now - r10m.timestamp) / (3600 * 1000));

    // Baseline calculation
    if (this.learnedBaselineTemp === null) {
      this.learnedBaselineTemp = current.indoorTemp;
    }

    // Expected temperature via learned building thermal model
    const tempGradient = current.outdoorTemp - current.indoorTemp;
    const hvacImpact = current.hvacState === 'heating' ? this.learnedHvacGain : (current.hvacState === 'cooling' ? -this.learnedHvacGain : 0);
    const expectedRate = (this.learnedConductance * tempGradient) + hvacImpact;
    const expectedTemp = current.indoorTemp + (expectedRate * (5 / 60));
    const thermalResidual = (current.indoorTemp + (tempRate * (5 / 60))) - expectedTemp;

    // Humidity features
    let indoorAbsHumidity: number | undefined;
    let outdoorAbsHumidity: number | undefined;
    let absHumidityDiff: number | undefined;
    let dewPoint: number | undefined;
    let absHumidityDelta5m: number | undefined;

    if (current.indoorHumidity !== undefined) {
      indoorAbsHumidity = calculateAbsoluteHumidity(current.indoorTemp, current.indoorHumidity);
      dewPoint = calculateDewPoint(current.indoorTemp, current.indoorHumidity);
      if (r5m.indoorHumidity !== undefined) {
        const pastAH = calculateAbsoluteHumidity(r5m.indoorTemp, r5m.indoorHumidity);
        absHumidityDelta5m = indoorAbsHumidity - pastAH;
      }
    }

    if (current.outdoorHumidity !== undefined) {
      outdoorAbsHumidity = calculateAbsoluteHumidity(current.outdoorTemp, current.outdoorHumidity);
      if (indoorAbsHumidity !== undefined) {
        absHumidityDiff = indoorAbsHumidity - outdoorAbsHumidity;
      }
    }

    // Comparative features
    let refTempDiff: number | undefined;
    let refRateDiff: number | undefined;

    if (current.referenceTemp !== undefined) {
      refTempDiff = current.indoorTemp - current.referenceTemp;
      const refRate5m = (current.referenceTemp - r5m.referenceTemp!) / dtHours5m;
      refRateDiff = tempRate - refRate5m;
    }

    const date = new Date(now);
    const timeOfDay = date.getHours() + date.getMinutes() / 60;

    return {
      timestamp: now,
      indoorTemp: current.indoorTemp,
      outdoorTemp: current.outdoorTemp,
      tempDiff: current.indoorTemp - current.outdoorTemp,
      delta1m,
      delta5m,
      delta10m,
      delta20m,
      tempRate,
      tempAccel,
      outdoorRate,
      expectedTemp,
      thermalResidual,
      indoorAbsHumidity,
      outdoorAbsHumidity,
      absHumidityDiff,
      dewPoint,
      absHumidityDelta5m,
      refTempDiff,
      refRateDiff,
      hvacActive: current.hvacState === 'heating' || current.hvacState === 'cooling',
      hvacState: current.hvacState,
      occupancy: current.occupancy,
      timeOfDay,
    };
  }

  private updateChangePoint(features: ExtractedFeatures): void {
    // Page-Hinkley test on residual and rate of change
    // Detects when the observed slope deviates abruptly from normal fluctuations
    const delta = -features.thermalResidual; // positive if cooling faster than expected
    this.cusumValue = Math.max(0, this.cusumValue + delta - 0.15);
    this.cusumMin = Math.min(this.cusumMin, this.cusumValue);

    const threshold = this.config.changePointSensitivity * 1.5;
    if (this.cusumValue - this.cusumMin > threshold) {
      this.changePointActive = true;
    } else {
      this.changePointActive = false;
    }
  }

  private evaluateEvidence(features: ExtractedFeatures, reading: SensorReading): EvidenceBreakdown {
    const reasons: string[] = [];
    
    // Gradient direction: is outdoor colder or warmer?
    const isOutdoorColder = features.tempDiff > 0;
    const gradientMagnitude = Math.abs(features.tempDiff);
    
    // Positive Evidence 1: Rapid temperature deviation in direction of outdoor air
    let rapidCooling = 0;
    if (isOutdoorColder) {
      // Expect negative tempRate when window is open
      if (features.tempRate < -0.8) {
        rapidCooling = Math.min(1.0, Math.abs(features.tempRate) / 3.0);
        if (rapidCooling > 0.6) {
          reasons.push(`Rapid indoor temperature drop of ${Math.abs(features.tempRate).toFixed(1)}°C/h towards outdoor air`);
        }
      }
    } else {
      // Outdoor is warmer (e.g. hot summer day)
      if (features.tempRate > 0.8) {
        rapidCooling = Math.min(1.0, features.tempRate / 3.0);
        if (rapidCooling > 0.6) {
          reasons.push(`Rapid indoor temperature rise of ${features.tempRate.toFixed(1)}°C/h from hot outdoor air`);
        }
      }
    }

    // Positive Evidence 2: Sustained thermal gradient
    let thermalGradientSustained = 0;
    if (gradientMagnitude >= this.config.minIndoorOutdoorDiffForOpen) {
      thermalGradientSustained = Math.min(1.0, (gradientMagnitude - 1.5) / 6.0);
    } else {
      reasons.push(`Indoor and outdoor temperatures are very close (Δ${gradientMagnitude.toFixed(1)}°C), dampening thermal signal`);
    }

    // Positive Evidence 3: Local divergence from reference room
    let localDivergence = 0;
    if (features.refRateDiff !== undefined) {
      if (isOutdoorColder && features.refRateDiff < -0.6) {
        localDivergence = Math.min(1.0, Math.abs(features.refRateDiff) / 2.0);
        reasons.push(`Target room is cooling ${Math.abs(features.refRateDiff).toFixed(1)}°C/h faster than adjacent reference room`);
      } else if (!isOutdoorColder && features.refRateDiff > 0.6) {
        localDivergence = Math.min(1.0, features.refRateDiff / 2.0);
        reasons.push(`Target room is warming faster than reference room`);
      }
    }

    // Positive Evidence 4: Humidity matches outdoor air exchange
    let humidityMatches = 0;
    if (features.indoorAbsHumidity !== undefined && features.outdoorAbsHumidity !== undefined && features.absHumidityDelta5m !== undefined) {
      const outdoorAHDiff = features.outdoorAbsHumidity - features.indoorAbsHumidity;
      // If outdoor AH is lower than indoor AH (typical in winter), absolute humidity should fall
      if (outdoorAHDiff < -0.5 && features.absHumidityDelta5m < -0.1) {
        humidityMatches = Math.min(1.0, Math.abs(features.absHumidityDelta5m) / 0.8);
        reasons.push(`Absolute humidity dropped by ${Math.abs(features.absHumidityDelta5m).toFixed(2)} g/m³, consistent with dry outdoor air infiltration`);
      } else if (outdoorAHDiff > 0.5 && features.absHumidityDelta5m > 0.1) {
        humidityMatches = Math.min(1.0, features.absHumidityDelta5m / 0.8);
        reasons.push(`Absolute humidity shifted towards higher outdoor moisture level`);
      }
    }

    // Positive Evidence 5: Change point
    const changePointTriggered = this.changePointActive ? 0.9 : 0.0;
    if (this.changePointActive) {
      reasons.push(`Thermal change-point detected: sudden inflection in room heat balance`);
    }

    // Negative Evidence 1: Heating turned off recently (< 15 mins)
    let heatingTurnedOffRecently = 0;
    const minutesSinceHvacChange = (reading.timestamp - this.lastHvacStateChangeTime) / 60000;
    if (minutesSinceHvacChange < 15 && this.previousHvacState === 'idle' && reading.hvacState === 'idle') {
      heatingTurnedOffRecently = Math.max(0, 1.0 - (minutesSinceHvacChange / 15));
      reasons.push(`Heating recently cycled off (${Math.round(minutesSinceHvacChange)}m ago); expected normal decay`);
    }

    // Negative Evidence 2: Outdoor cannot explain cooling (e.g. outdoor is warm, but room is cooling)
    let outdoorCannotExplainCooling = 0;
    if (features.tempRate < -0.6 && features.outdoorTemp > features.indoorTemp + 1.0) {
      outdoorCannotExplainCooling = 1.0;
      reasons.push(`Outdoor air is warmer (${features.outdoorTemp.toFixed(1)}°C) than room (${features.indoorTemp.toFixed(1)}°C); cooling cannot be caused by window opening`);
    }

    // Negative Evidence 3: Multi-room global drop (reference room dropped at virtually the exact same rate)
    let multiRoomGlobalDrop = 0;
    if (features.refRateDiff !== undefined && Math.abs(features.refRateDiff) < 0.2 && Math.abs(features.tempRate) > 0.5) {
      multiRoomGlobalDrop = 0.8;
      reasons.push(`Reference room exhibits identical temperature trajectory; change is house-wide, not window-specific`);
    }

    // Negative Evidence 4: Anomaly too brief (< 1.5 min duration)
    const anomalyTooBrief = this.samplesCount < 3 ? 0.9 : 0.0;

    // Negative Evidence 5: Internal moisture source (shower/cooking: humidity jumps drastically while temp stays warm)
    let internalMoistureSource = 0;
    if (features.absHumidityDelta5m !== undefined && features.absHumidityDelta5m > 1.2 && features.tempRate >= -0.2) {
      internalMoistureSource = 0.95;
      reasons.push(`Sudden indoor moisture spike without thermal cooling; indicates shower or cooking, not window open`);
    }

    // Weighted positive aggregation
    let posScore = 0;
    let totalWeight = 0;

    posScore += rapidCooling * this.config.weightRate;
    totalWeight += this.config.weightRate;

    posScore += (Math.abs(features.thermalResidual) > 0.4 ? Math.min(1.0, Math.abs(features.thermalResidual) / 1.5) : 0) * this.config.weightResidual;
    totalWeight += this.config.weightResidual;

    posScore += changePointTriggered * this.config.weightChangePoint;
    totalWeight += this.config.weightChangePoint;

    if (features.indoorAbsHumidity !== undefined) {
      posScore += humidityMatches * this.config.weightHumidity;
      totalWeight += this.config.weightHumidity;
    }

    if (features.refRateDiff !== undefined) {
      posScore += localDivergence * this.config.weightReferenceRoom;
      totalWeight += this.config.weightReferenceRoom;
    }

    const rawPos = posScore / Math.max(0.1, totalWeight);

    // Apply thermal gradient gate: if gradient is minimal, attenuate confidence
    const gradientMultiplier = thermalGradientSustained < 0.2 ? 0.35 : Math.min(1.0, thermalGradientSustained + 0.3);
    const gatedPos = rawPos * gradientMultiplier;

    // Negative deduction
    const maxNegPenalty = Math.max(
      heatingTurnedOffRecently * 0.7,
      outdoorCannotExplainCooling * 1.0,
      multiRoomGlobalDrop * 0.75,
      anomalyTooBrief * 0.9,
      internalMoistureSource * 0.9
    );

    const finalConfidence = Math.max(0.0, Math.min(1.0, gatedPos - maxNegPenalty));

    // Construct primary human-readable diagnostic sentence
    let primaryReason = '';
    if (finalConfidence >= this.config.openConfidenceThreshold) {
      primaryReason = `Rapid thermal departure from baseline (${features.thermalResidual > 0 ? '+' : ''}${features.thermalResidual.toFixed(1)}°C residual, rate ${features.tempRate.toFixed(1)}°C/h); gradient Δ${gradientMagnitude.toFixed(1)}°C to outdoor air.`;
      if (humidityMatches > 0.4) {
        primaryReason += ` Absolute humidity confirms outdoor air exchange.`;
      }
    } else if (finalConfidence <= this.config.closeConfidenceThreshold) {
      if (maxNegPenalty > 0.5) {
        primaryReason = reasons.find(r => r.includes('cannot be caused') || r.includes('cycled off') || r.includes('identical') || r.includes('shower')) || 'Thermal behavior matches expected closed room dynamics.';
      } else {
        primaryReason = `Thermal trajectory aligns with learned equilibrium baseline (residual ${features.thermalResidual.toFixed(2)}°C). Window inferred closed.`;
      }
    } else {
      primaryReason = `Intermediate confidence (${Math.round(finalConfidence * 100)}%): subtle thermal perturbation detected, waiting for sustained persistence.`;
    }

    return {
      rapidCoolingFasterThanExpected: rapidCooling,
      thermalGradientSustained,
      localDivergenceFromRefRoom: localDivergence,
      humidityMatchesOutdoorAir: humidityMatches,
      changePointTriggered,
      heatingTurnedOffRecently,
      outdoorCannotExplainCooling,
      multiRoomGlobalDrop,
      anomalyTooBrief,
      internalMoistureSource,
      rawScore: rawPos,
      finalConfidence,
      reasons,
      primaryReason,
    };
  }

  private updateBaseline(reading: SensorReading, features: ExtractedFeatures, confidence: number): void {
    // CRITICAL DESIGN RULE:
    // Do NOT continuously adapt baseline when window is suspected open (confidence > 0.35),
    // or else the system will learn that an open window is the new normal!
    if (confidence > 0.35 || this.currentState) {
      return;
    }

    // Adaptive exponential smoothing on conductance and equilibrium
    const gradient = reading.outdoorTemp - reading.indoorTemp;
    if (Math.abs(gradient) > 2.0 && !features.hvacActive) {
      // In free-floating conditions, update conductance estimate:
      // tempRate = Conductance * (T_out - T_in)
      const measuredConductance = features.tempRate / gradient;
      if (measuredConductance > 0.01 && measuredConductance < 0.4) {
        this.learnedConductance = (1 - this.config.baselineLearningRate) * this.learnedConductance + (this.config.baselineLearningRate * measuredConductance);
      }
    }

    // Update rolling baseline temp
    if (this.learnedBaselineTemp !== null) {
      this.learnedBaselineTemp = (1 - this.config.baselineLearningRate) * this.learnedBaselineTemp + (this.config.baselineLearningRate * reading.indoorTemp);
    }
  }

  private updateHysteresis(timestamp: number, confidence: number): void {
    const openThreshold = this.config.openConfidenceThreshold;
    const closeThreshold = this.config.closeConfidenceThreshold;
    const openDurationMs = this.config.openPersistenceMinutes * 60 * 1000;
    const closeDurationMs = this.config.closePersistenceMinutes * 60 * 1000;

    if (!this.currentState) {
      // Currently CLOSED -> Check condition to transition to OPEN
      if (confidence >= openThreshold) {
        if (!this.highConfidenceStartTime) {
          this.highConfidenceStartTime = timestamp;
        } else if (timestamp - this.highConfidenceStartTime >= openDurationMs) {
          this.currentState = true;
          this.lastStateChangeTime = timestamp;
          this.highConfidenceStartTime = null;
        }
      } else {
        this.highConfidenceStartTime = null;
      }
    } else {
      // Currently OPEN -> Check condition to transition to CLOSED
      if (confidence <= closeThreshold) {
        if (!this.lowConfidenceStartTime) {
          this.lowConfidenceStartTime = timestamp;
        } else if (timestamp - this.lowConfidenceStartTime >= closeDurationMs) {
          this.currentState = false;
          this.lastStateChangeTime = timestamp;
          this.lowConfidenceStartTime = null;
        }
      } else {
        this.lowConfidenceStartTime = null;
      }
    }
  }

  private evaluateReadiness(reading: SensorReading): ModelReadiness {
    const durationMinutes = (reading.timestamp - (this.firstTimestamp || reading.timestamp)) / 60000;
    if (this.samplesCount < 10 || durationMinutes < 15) {
      return 'Insufficient data';
    }
    if (durationMinutes < 60 || this.samplesCount < 30) {
      return 'Learning';
    }
    if (Math.abs(reading.indoorTemp - reading.outdoorTemp) < 1.0) {
      return 'Low confidence';
    }
    return 'Ready';
  }

  private evaluateQuality(reading: SensorReading): 'High' | 'Medium' | 'Degraded' | 'Minimal' {
    const hasHumidity = reading.indoorHumidity !== undefined && reading.outdoorHumidity !== undefined;
    const hasRef = reading.referenceTemp !== undefined;
    const hasHvac = reading.hvacState !== undefined;

    if (hasHumidity && hasRef && hasHvac) return 'High';
    if (hasHumidity || hasRef) return 'Medium';
    if (reading.indoorTemp !== undefined && reading.outdoorTemp !== undefined) return 'Degraded';
    return 'Minimal';
  }
}
