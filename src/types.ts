export interface SensorReading {
  timestamp: number; // Unix epoch ms
  indoorTemp: number; // °C
  outdoorTemp: number; // °C
  indoorHumidity?: number; // % RH
  outdoorHumidity?: number; // % RH
  referenceTemp?: number; // °C
  referenceHumidity?: number; // % RH
  co2?: number; // ppm
  hvacState?: 'off' | 'heating' | 'cooling' | 'idle';
  heatingPower?: number; // % or W
  occupancy?: boolean;
}

export interface ExtractedFeatures {
  timestamp: number;
  indoorTemp: number;
  outdoorTemp: number;
  tempDiff: number; // indoor - outdoor
  delta1m: number;
  delta5m: number;
  delta10m: number;
  delta20m: number;
  tempRate: number; // °C / hour
  tempAccel: number; // °C / hour²
  outdoorRate: number; // °C / hour
  
  // Baseline & Residual
  expectedTemp: number;
  thermalResidual: number; // actual - expected
  
  // Humidity
  indoorAbsHumidity?: number; // g/m³
  outdoorAbsHumidity?: number; // g/m³
  absHumidityDiff?: number;
  dewPoint?: number; // °C
  absHumidityDelta5m?: number;
  
  // Comparative (reference room)
  refTempDiff?: number; // indoor - ref
  refRateDiff?: number; // indoor rate - ref rate
  
  // Contextual
  hvacActive: boolean;
  hvacState?: string;
  occupancy?: boolean;
  timeOfDay: number; // hour (0-23.99)
}

export interface EvidenceBreakdown {
  // Positive evidence [0, 1]
  rapidCoolingFasterThanExpected: number;
  thermalGradientSustained: number;
  localDivergenceFromRefRoom: number;
  humidityMatchesOutdoorAir: number;
  changePointTriggered: number;
  
  // Negative evidence [0, 1]
  heatingTurnedOffRecently: number;
  outdoorCannotExplainCooling: number;
  multiRoomGlobalDrop: number;
  anomalyTooBrief: number;
  internalMoistureSource: number;
  
  rawScore: number;
  finalConfidence: number; // 0.0 - 1.0
  reasons: string[];
  primaryReason: string;
}

export type ModelReadiness = 'Learning' | 'Ready' | 'Low confidence' | 'Insufficient data';

export interface AlgorithmConfig {
  openConfidenceThreshold: number; // e.g. 0.80
  openPersistenceMinutes: number; // e.g. 3 min
  closeConfidenceThreshold: number; // e.g. 0.25
  closePersistenceMinutes: number; // e.g. 10 min
  
  baselineLearningRate: number; // e.g. 0.05
  thermalInertiaFactor: number; // e.g. 0.85
  changePointSensitivity: number; // e.g. 1.2
  minIndoorOutdoorDiffForOpen: number; // e.g. 2.0 °C
  
  // Sensor weights
  weightResidual: number;
  weightRate: number;
  weightChangePoint: number;
  weightHumidity: number;
  weightReferenceRoom: number;
}

export interface InferredState {
  isOpen: boolean;
  confidence: number; // 0 - 100%
  readiness: ModelReadiness;
  detectionQuality: 'High' | 'Medium' | 'Degraded' | 'Minimal';
  thermalAnomaly: number; // °C residual
  temperatureRate: number; // °C / hr
  indoorTemp: number;
  outdoorTemp: number;
  tempDiff: number;
  humiditySignal: string;
  referenceRoomSignal: string;
  hvacSignal: string;
  modelAgeDays: number;
  samplesAvailable: number;
  lastStateChange: number; // timestamp
  reason: string;
  evidence: EvidenceBreakdown;
  features: ExtractedFeatures;
}

export interface TestScenario {
  id: string;
  title: string;
  category: 'True Positive' | 'False Positive Candidate' | 'Edge Case';
  description: string;
  durationMinutes: number;
  windowOpenPeriods: Array<{ startMin: number; endMin: number }>;
  generateData: () => SensorReading[];
}

export interface ScenarioEvaluation {
  scenarioId: string;
  truePositives: number;
  falsePositives: number;
  falseNegatives: number;
  trueNegatives: number;
  detectionLatencySeconds: number | null;
  closingLatencySeconds: number | null;
  passed: boolean;
  notes: string;
}
