import React, { useState, useEffect, useRef } from 'react';
import { 
  Play, 
  Pause, 
  RotateCcw, 
  SkipForward, 
  Zap, 
  Sliders, 
  Thermometer, 
  Droplets, 
  Flame, 
  CheckCircle,
  AlertTriangle
} from 'lucide-react';
import { 
  AlgorithmConfig, 
  InferredState, 
  SensorReading, 
  TestScenario 
} from '../types';
import { WindowInferenceEngine } from '../engine/algorithm';
import { TEST_SCENARIOS } from '../engine/scenarios';
import { SignalVisualizer } from './SignalVisualizer';
import { calculateAbsoluteHumidity } from '../engine/physics';

interface ReplayLabProps {
  config: AlgorithmConfig;
  currentState: InferredState | null;
  onStateUpdate: (state: InferredState) => void;
  selectedRoom: string;
}

export const ReplayLab: React.FC<ReplayLabProps> = ({
  config,
  onStateUpdate,
  selectedRoom,
}) => {
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('winter_cold_shock');
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(2); // 1x, 2x, 5x, 20x
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [scenarioReadings, setScenarioReadings] = useState<SensorReading[]>([]);
  const [processedStates, setProcessedStates] = useState<InferredState[]>([]);
  
  // Interactive manual injection overrides
  const [manualTempDrop, setManualTempDrop] = useState<number>(0);
  const [manualHumidityDrop, setManualHumidityDrop] = useState<number>(0);

  const engineRef = useRef<WindowInferenceEngine>(new WindowInferenceEngine(config));
  const timerRef = useRef<number | null>(null);

  const scenario = TEST_SCENARIOS.find((s) => s.id === selectedScenarioId) || TEST_SCENARIOS[0];

  // Load and pre-process scenario data
  const loadScenario = (sc: TestScenario) => {
    setIsPlaying(false);
    if (timerRef.current) clearInterval(timerRef.current);
    
    const readings = sc.generateData();
    setScenarioReadings(readings);

    // Run engine through all readings to pre-calculate time-series trajectory
    const engine = new WindowInferenceEngine(config);
    engineRef.current = engine;
    const states: InferredState[] = [];
    
    for (const r of readings) {
      states.push(engine.processReading(r));
    }
    
    setProcessedStates(states);
    setCurrentStep(0);
    if (states.length > 0) {
      onStateUpdate(states[0]);
    }
  };

  useEffect(() => {
    loadScenario(scenario);
  }, [selectedScenarioId, config]);

  // Handle Play/Pause timer
  useEffect(() => {
    if (isPlaying) {
      const intervalMs = Math.max(25, 400 / playbackSpeed);
      timerRef.current = window.setInterval(() => {
        setCurrentStep((prev) => {
          if (prev >= scenarioReadings.length - 1) {
            setIsPlaying(false);
            return prev;
          }
          const next = prev + 1;
          if (processedStates[next]) {
            onStateUpdate(processedStates[next]);
          }
          return next;
        });
      }, intervalMs);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isPlaying, playbackSpeed, scenarioReadings.length, processedStates]);

  const handleScrub = (index: number) => {
    const clamped = Math.max(0, Math.min(scenarioReadings.length - 1, index));
    setCurrentStep(clamped);
    if (processedStates[clamped]) {
      onStateUpdate(processedStates[clamped]);
    }
  };

  const handleStepForward = () => {
    handleScrub(currentStep + 1);
  };

  const handleReset = () => {
    setIsPlaying(false);
    handleScrub(0);
  };

  const handleRunAll = () => {
    setIsPlaying(false);
    handleScrub(scenarioReadings.length - 1);
  };

  const currentState = processedStates[currentStep] || null;
  const currentReading = scenarioReadings[currentStep] || null;

  // Prepare chart series
  const chartData = scenarioReadings.map((r, i) => {
    const state = processedStates[i];
    const isGroundTruthOpen = scenario.windowOpenPeriods.some(
      (p) => i >= p.startMin && i < p.endMin
    );

    const inAH = r.indoorHumidity !== undefined ? calculateAbsoluteHumidity(r.indoorTemp, r.indoorHumidity) : undefined;
    const outAH = r.outdoorHumidity !== undefined ? calculateAbsoluteHumidity(r.outdoorTemp, r.outdoorHumidity) : undefined;

    return {
      timeMin: i,
      indoorTemp: r.indoorTemp,
      outdoorTemp: r.outdoorTemp,
      baselineTemp: state?.features?.expectedTemp,
      referenceTemp: r.referenceTemp,
      indoorRH: r.indoorHumidity,
      outdoorRH: r.outdoorHumidity,
      indoorAH: inAH ? parseFloat(inAH.toFixed(2)) : undefined,
      outdoorAH: outAH ? parseFloat(outAH.toFixed(2)) : undefined,
      tempRate: state?.temperatureRate || 0,
      thermalResidual: state?.thermalAnomaly || 0,
      confidence: state?.confidence || 0,
      inferredOpen: state?.isOpen ? 1 : 0,
      actualOpen: isGroundTruthOpen ? 1 : 0,
      changePoint: state?.evidence?.changePointTriggered ? 1 : 0,
    };
  });

  return (
    <div className="space-y-6">
      {/* Top Controls: Scenario Selector & Playback Deck */}
      <div className="bg-white rounded-xl p-4 sm:p-5 border border-slate-200 shadow-xs space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex-1">
            <label className="block text-xs font-semibold text-slate-700 uppercase tracking-wider mb-1.5">
              Select Test Scenario / Real-World Thermal Replay
            </label>
            <select
              value={selectedScenarioId}
              onChange={(e) => setSelectedScenarioId(e.target.value)}
              className="w-full bg-slate-50 border border-slate-300 rounded-lg px-3 py-2 text-sm font-medium text-slate-800 focus:ring-2 focus:ring-blue-500 focus:outline-none"
              id="scenario-select"
            >
              <optgroup label="True Positive Events (Window Opens)">
                {TEST_SCENARIOS.filter((s) => s.category === 'True Positive').map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.title}
                  </option>
                ))}
              </optgroup>
              <optgroup label="False Positive Candidates (Disturbance / Noise)">
                {TEST_SCENARIOS.filter((s) => s.category === 'False Positive Candidate').map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.title}
                  </option>
                ))}
              </optgroup>
              <optgroup label="Edge Cases (Sensor Faults & Recovery)">
                {TEST_SCENARIOS.filter((s) => s.category === 'Edge Case').map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.title}
                  </option>
                ))}
              </optgroup>
            </select>
          </div>

          {/* Scenario Category Pill & Description */}
          <div className="lg:max-w-md bg-slate-50 rounded-lg p-3 border border-slate-200 text-xs">
            <div className="flex items-center gap-2 mb-1">
              <span className={`px-2 py-0.5 rounded text-[11px] font-semibold ${
                scenario.category === 'True Positive'
                  ? 'bg-blue-100 text-blue-800'
                  : scenario.category === 'False Positive Candidate'
                  ? 'bg-purple-100 text-purple-800'
                  : 'bg-slate-200 text-slate-800'
              }`}>
                {scenario.category}
              </span>
              <span className="text-slate-500 font-mono">
                Duration: {scenario.durationMinutes} min
              </span>
            </div>
            <p className="text-slate-600 leading-relaxed">
              {scenario.description}
            </p>
          </div>
        </div>

        {/* Playback Transport Bar */}
        <div className="pt-2 border-t border-slate-100 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsPlaying(!isPlaying)}
              id="btn-play-pause"
              className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold shadow-xs transition-colors ${
                isPlaying
                  ? 'bg-amber-600 hover:bg-amber-700 text-white'
                  : 'bg-blue-600 hover:bg-blue-700 text-white'
              }`}
            >
              {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
              {isPlaying ? 'Pause' : 'Play Replay'}
            </button>

            <button
              onClick={handleStepForward}
              disabled={isPlaying || currentStep >= scenarioReadings.length - 1}
              className="flex items-center gap-1 px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-medium transition-colors disabled:opacity-50"
              title="Step +1 minute forward"
            >
              <SkipForward className="w-3.5 h-3.5" />
              Step +1m
            </button>

            <button
              onClick={handleReset}
              className="flex items-center gap-1 px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-medium transition-colors"
              title="Reset to beginning"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset
            </button>

            <button
              onClick={handleRunAll}
              className="flex items-center gap-1 px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-medium transition-colors"
              title="Skip to end of simulation"
            >
              <Zap className="w-3.5 h-3.5 text-amber-600" />
              Instant End
            </button>
          </div>

          {/* Speed Selector */}
          <div className="flex items-center gap-1 bg-slate-100 p-1 rounded-lg border border-slate-200 text-xs">
            <span className="text-slate-500 px-1 font-medium">Speed:</span>
            {[1, 2, 5, 20].map((spd) => (
              <button
                key={spd}
                onClick={() => setPlaybackSpeed(spd)}
                className={`px-2 py-0.5 rounded font-mono font-medium transition-colors ${
                  playbackSpeed === spd
                    ? 'bg-white text-blue-700 shadow-xs font-bold'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                {spd}x
              </button>
            ))}
          </div>

          {/* Timeline Scrubber */}
          <div className="flex items-center gap-3 flex-1 min-w-[240px]">
            <span className="text-xs font-mono text-slate-500 min-w-[48px]">
              T = {currentStep}m
            </span>
            <input
              type="range"
              min={0}
              max={scenarioReadings.length - 1}
              value={currentStep}
              onChange={(e) => handleScrub(Number(e.target.value))}
              className="flex-1 accent-blue-600 cursor-pointer h-2 bg-slate-200 rounded-lg"
              id="replay-time-scrubber"
            />
            <span className="text-xs font-mono text-slate-500 min-w-[48px] text-right">
              {scenarioReadings.length - 1}m
            </span>
          </div>
        </div>
      </div>

      {/* Real-time Telemetry KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className={`p-3.5 rounded-xl border shadow-xs ${
          currentState?.isOpen 
            ? 'bg-amber-500/10 border-amber-300' 
            : 'bg-white border-slate-200'
        }`}>
          <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wide block">
            Window Sensor
          </span>
          <div className="mt-1 flex items-center gap-2">
            <div className={`w-3 h-3 rounded-full ${currentState?.isOpen ? 'bg-amber-500 animate-ping' : 'bg-emerald-500'}`} />
            <span className={`text-base font-bold ${currentState?.isOpen ? 'text-amber-800' : 'text-slate-900'}`}>
              {currentState?.isOpen ? 'OPEN' : 'CLOSED'}
            </span>
          </div>
          <span className="text-[10px] text-slate-400 mt-1 block">
            binary_sensor.{selectedRoom.toLowerCase().replace(' ', '_')}_window
          </span>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wide block">
            Confidence Score
          </span>
          <div className="mt-1 flex items-baseline gap-1">
            <span className="text-xl font-bold text-purple-700">
              {currentState?.confidence ?? 0}%
            </span>
          </div>
          <div className="w-full bg-slate-100 rounded-full h-1.5 mt-2 overflow-hidden">
            <div 
              className={`h-full transition-all ${
                (currentState?.confidence ?? 0) >= 80 ? 'bg-amber-500' : 'bg-purple-600'
              }`}
              style={{ width: `${currentState?.confidence ?? 0}%` }}
            />
          </div>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wide block">
            Thermal Residual
          </span>
          <div className="mt-1 flex items-baseline gap-1">
            <span className={`text-lg font-bold ${
              (currentState?.thermalAnomaly ?? 0) < -0.4 ? 'text-blue-600' : 'text-slate-800'
            }`}>
              {(currentState?.thermalAnomaly ?? 0) > 0 ? '+' : ''}
              {currentState?.thermalAnomaly ?? 0}°C
            </span>
          </div>
          <span className="text-[10px] text-slate-500 mt-1 block">
            Deviation vs learned baseline
          </span>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wide block">
            Temp Rate (dT/dt)
          </span>
          <div className="mt-1 flex items-baseline gap-1">
            <span className="text-lg font-bold text-slate-800">
              {currentState?.temperatureRate ?? 0}°C/h
            </span>
          </div>
          <span className="text-[10px] text-slate-500 mt-1 block">
            5-min derivative
          </span>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wide block">
            Indoor / Outdoor
          </span>
          <div className="mt-1 text-sm font-semibold text-slate-800">
            {currentReading?.indoorTemp ?? '--'}°C / {currentReading?.outdoorTemp ?? '--'}°C
          </div>
          <span className="text-[10px] text-slate-500 mt-1 block">
            Gradient: Δ{currentState?.tempDiff ?? 0}°C
          </span>
        </div>

        <div className="bg-white p-3.5 rounded-xl border border-slate-200 shadow-xs">
          <span className="text-[11px] font-medium text-slate-500 uppercase tracking-wide block">
            Absolute Humidity
          </span>
          <div className="mt-1 text-sm font-semibold text-teal-800">
            {currentState?.features?.indoorAbsHumidity?.toFixed(1) ?? '--'} g/m³
          </div>
          <span className="text-[10px] text-slate-500 mt-1 block">
            Out AH: {currentState?.features?.outdoorAbsHumidity?.toFixed(1) ?? '--'} g/m³
          </span>
        </div>
      </div>

      {/* Human-readable Reason Banner */}
      <div className="bg-slate-50 rounded-xl p-4 border border-slate-200 flex items-start gap-3 shadow-xs">
        <div className="p-2 bg-blue-100 text-blue-700 rounded-lg shrink-0 mt-0.5">
          <Thermometer className="w-4 h-4" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-700 uppercase tracking-wide">
              Diagnostic Reason (Home Assistant Attribute)
            </span>
            <span className="text-xs text-slate-500 font-mono">
              Detection Quality: <strong>{currentState?.detectionQuality}</strong>
            </span>
          </div>
          <p className="text-sm text-slate-800 font-medium mt-1">
            "{currentState?.reason}"
          </p>
        </div>
      </div>

      {/* Multi-Signal Visualization Section */}
      <SignalVisualizer
        chartData={chartData}
        currentStepIndex={currentStep}
        config={config}
        scenario={scenario}
        onScrub={handleScrub}
      />
    </div>
  );
};
