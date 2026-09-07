import React from 'react';
import { 
  Sliders, 
  RotateCcw, 
  Check, 
  Sparkles, 
  ShieldCheck, 
  Flame, 
  Wind,
  Layers
} from 'lucide-react';
import { AlgorithmConfig } from '../types';
import { DEFAULT_CONFIG } from '../engine/algorithm';

interface TuningModalProps {
  config: AlgorithmConfig;
  onChangeConfig: (newConfig: AlgorithmConfig) => void;
}

export const TuningModal: React.FC<TuningModalProps> = ({
  config,
  onChangeConfig,
}) => {
  const handleSlider = (key: keyof AlgorithmConfig, value: number) => {
    onChangeConfig({
      ...config,
      [key]: value,
    });
  };

  const applyPreset = (preset: 'balanced' | 'aggressive' | 'conservative') => {
    if (preset === 'balanced') {
      onChangeConfig({ ...DEFAULT_CONFIG });
    } else if (preset === 'aggressive') {
      // High sensitivity for drafty rooms or small window tilts
      onChangeConfig({
        ...DEFAULT_CONFIG,
        openConfidenceThreshold: 0.65,
        openPersistenceMinutes: 2,
        closeConfidenceThreshold: 0.30,
        closePersistenceMinutes: 8,
        changePointSensitivity: 0.9,
        minIndoorOutdoorDiffForOpen: 1.2,
      });
    } else if (preset === 'conservative') {
      // Extremely immune to false alarms (for busy households)
      onChangeConfig({
        ...DEFAULT_CONFIG,
        openConfidenceThreshold: 0.85,
        openPersistenceMinutes: 4,
        closeConfidenceThreshold: 0.20,
        closePersistenceMinutes: 12,
        changePointSensitivity: 1.4,
        minIndoorOutdoorDiffForOpen: 2.5,
      });
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Top Description */}
      <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">
              Phase 8 & Section 8 Tuning Laboratory
            </span>
            <h2 className="text-lg font-bold text-slate-900 mt-0.5">
              Hysteresis & Model Parameter Calibration
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Configure asymmetric persistence windows, thermal inertia coefficients, and evidence weight distributions.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => onChangeConfig({ ...DEFAULT_CONFIG })}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium rounded-lg border border-slate-300 transition-colors"
              id="btn-reset-tuning"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Reset Defaults
            </button>
          </div>
        </div>

        {/* Presets */}
        <div className="flex items-center flex-wrap gap-2 mt-4 pt-4 border-t border-slate-100">
          <span className="text-xs font-semibold text-slate-600 mr-1">Tuning Presets:</span>
          <button
            onClick={() => applyPreset('balanced')}
            className="px-3 py-1 bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 rounded-lg text-xs font-medium transition-colors"
          >
            Residential Standard (Balanced)
          </button>
          <button
            onClick={() => applyPreset('aggressive')}
            className="px-3 py-1 bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200 rounded-lg text-xs font-medium transition-colors"
          >
            Aggressive (High Sensitivity / Trickle Vents)
          </button>
          <button
            onClick={() => applyPreset('conservative')}
            className="px-3 py-1 bg-emerald-50 hover:bg-emerald-100 text-emerald-800 border border-emerald-200 rounded-lg text-xs font-medium transition-colors"
          >
            Conservative (Zero False-Alarm Immunity)
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Hysteresis & State Decision */}
        <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs space-y-5">
          <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
            <div className="p-1.5 bg-amber-100 text-amber-700 rounded-lg">
              <Wind className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">
                Asymmetric Hysteresis Rules
              </h3>
              <p className="text-[11px] text-slate-500">
                Opening requires quick confirmation; closing requires sustained equilibrium.
              </p>
            </div>
          </div>

          {/* Open Threshold */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs">
              <label className="font-semibold text-slate-800">
                Open Confidence Threshold
              </label>
              <span className="font-mono text-blue-600 font-bold">
                {Math.round(config.openConfidenceThreshold * 100)}%
              </span>
            </div>
            <input
              type="range"
              min={0.50}
              max={0.95}
              step={0.05}
              value={config.openConfidenceThreshold}
              onChange={(e) => handleSlider('openConfidenceThreshold', parseFloat(e.target.value))}
              className="w-full accent-blue-600 h-2 bg-slate-200 rounded-lg cursor-pointer"
            />
            <p className="text-[11px] text-slate-500">
              Confidence required before initiating the open persistence countdown.
            </p>
          </div>

          {/* Open Persistence */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs">
              <label className="font-semibold text-slate-800">
                Open Persistence Timer
              </label>
              <span className="font-mono text-blue-600 font-bold">
                {config.openPersistenceMinutes} minutes
              </span>
            </div>
            <input
              type="range"
              min={1}
              max={10}
              step={1}
              value={config.openPersistenceMinutes}
              onChange={(e) => handleSlider('openPersistenceMinutes', parseInt(e.target.value))}
              className="w-full accent-blue-600 h-2 bg-slate-200 rounded-lg cursor-pointer"
            />
            <p className="text-[11px] text-slate-500">
              High confidence must be sustained continuously for this long to declare OPEN.
            </p>
          </div>

          {/* Close Threshold */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs">
              <label className="font-semibold text-slate-800">
                Close Confidence Threshold
              </label>
              <span className="font-mono text-emerald-600 font-bold">
                {Math.round(config.closeConfidenceThreshold * 100)}%
              </span>
            </div>
            <input
              type="range"
              min={0.10}
              max={0.45}
              step={0.05}
              value={config.closeConfidenceThreshold}
              onChange={(e) => handleSlider('closeConfidenceThreshold', parseFloat(e.target.value))}
              className="w-full accent-emerald-600 h-2 bg-slate-200 rounded-lg cursor-pointer"
            />
            <p className="text-[11px] text-slate-500">
              Confidence must drop to or below this level to begin closing timer.
            </p>
          </div>

          {/* Close Persistence */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs">
              <label className="font-semibold text-slate-800">
                Close Persistence Timer
              </label>
              <span className="font-mono text-emerald-600 font-bold">
                {config.closePersistenceMinutes} minutes
              </span>
            </div>
            <input
              type="range"
              min={3}
              max={20}
              step={1}
              value={config.closePersistenceMinutes}
              onChange={(e) => handleSlider('closePersistenceMinutes', parseInt(e.target.value))}
              className="w-full accent-emerald-600 h-2 bg-slate-200 rounded-lg cursor-pointer"
            />
            <p className="text-[11px] text-slate-500">
              Low confidence must remain steady for this duration to confirm window is CLOSED.
            </p>
          </div>
        </div>

        {/* Baseline Model & Physical Thresholds */}
        <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs space-y-5">
          <div className="flex items-center gap-2 border-b border-slate-100 pb-3">
            <div className="p-1.5 bg-blue-100 text-blue-700 rounded-lg">
              <Sliders className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">
                Thermodynamic Model & Change-Point
              </h3>
              <p className="text-[11px] text-slate-500">
                Parameters controlling room learning and anomaly sensitivity.
              </p>
            </div>
          </div>

          {/* Baseline Learning Rate */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs">
              <label className="font-semibold text-slate-800">
                Adaptive Baseline Learning Rate
              </label>
              <span className="font-mono text-slate-700 font-bold">
                {config.baselineLearningRate}
              </span>
            </div>
            <input
              type="range"
              min={0.01}
              max={0.15}
              step={0.01}
              value={config.baselineLearningRate}
              onChange={(e) => handleSlider('baselineLearningRate', parseFloat(e.target.value))}
              className="w-full accent-blue-600 h-2 bg-slate-200 rounded-lg cursor-pointer"
            />
            <p className="text-[11px] text-slate-500">
              Speed at which normal equilibrium is incorporated. Frozen when window is open.
            </p>
          </div>

          {/* Change Point Sensitivity */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs">
              <label className="font-semibold text-slate-800">
                Change-Point Sensitivity (CUSUM)
              </label>
              <span className="font-mono text-slate-700 font-bold">
                {config.changePointSensitivity}
              </span>
            </div>
            <input
              type="range"
              min={0.6}
              max={2.0}
              step={0.1}
              value={config.changePointSensitivity}
              onChange={(e) => handleSlider('changePointSensitivity', parseFloat(e.target.value))}
              className="w-full accent-blue-600 h-2 bg-slate-200 rounded-lg cursor-pointer"
            />
            <p className="text-[11px] text-slate-500">
              Sensitivity of the Page-Hinkley slope deviation detector.
            </p>
          </div>

          {/* Min Indoor/Outdoor Gradient */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs">
              <label className="font-semibold text-slate-800">
                Minimum Indoor/Outdoor Temperature Gradient
              </label>
              <span className="font-mono text-slate-700 font-bold">
                Δ{config.minIndoorOutdoorDiffForOpen} °C
              </span>
            </div>
            <input
              type="range"
              min={0.5}
              max={4.0}
              step={0.5}
              value={config.minIndoorOutdoorDiffForOpen}
              onChange={(e) => handleSlider('minIndoorOutdoorDiffForOpen', parseFloat(e.target.value))}
              className="w-full accent-blue-600 h-2 bg-slate-200 rounded-lg cursor-pointer"
            />
            <p className="text-[11px] text-slate-500">
              When indoor and outdoor temperatures are very close, thermal signal is attenuated.
            </p>
          </div>

          {/* Sensor Weights Preview */}
          <div className="pt-2 border-t border-slate-100">
            <div className="text-xs font-semibold text-slate-700 mb-2">
              Evidence Fusion Weights
            </div>
            <div className="grid grid-cols-3 gap-2 text-[11px]">
              <div className="bg-slate-50 p-2 rounded border border-slate-200">
                <span className="text-slate-500 block">Thermal Residual</span>
                <span className="font-bold text-slate-800 font-mono">35%</span>
              </div>
              <div className="bg-slate-50 p-2 rounded border border-slate-200">
                <span className="text-slate-500 block">dT/dt Rate</span>
                <span className="font-bold text-slate-800 font-mono">25%</span>
              </div>
              <div className="bg-slate-50 p-2 rounded border border-slate-200">
                <span className="text-slate-500 block">Abs Humidity</span>
                <span className="font-bold text-slate-800 font-mono">15%</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
