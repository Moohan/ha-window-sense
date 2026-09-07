import React from 'react';
import { 
  ShieldCheck, 
  AlertTriangle, 
  TrendingDown, 
  Wind, 
  Home, 
  Flame, 
  Clock, 
  Sparkles,
  Layers,
  ThermometerSnowflake
} from 'lucide-react';
import { InferredState } from '../types';

interface EvidenceExplainerProps {
  currentState: InferredState | null;
}

export const EvidenceExplainer: React.FC<EvidenceExplainerProps> = ({ currentState }) => {
  const evidence = currentState?.evidence;
  const features = currentState?.features;

  if (!evidence || !features) {
    return (
      <div className="bg-white rounded-xl p-8 text-center text-slate-500 border border-slate-200">
        No state processed yet. Play a replay scenario to view evidence breakdown.
      </div>
    );
  }

  const positiveSignals = [
    {
      title: 'Rapid Cooling Rate',
      weight: '25%',
      score: evidence.rapidCoolingFasterThanExpected,
      desc: `Rate of change (${features.tempRate.toFixed(1)}°C/h) exceeds normal building drift.`,
      icon: <TrendingDown className="w-4 h-4 text-blue-600" />,
    },
    {
      title: 'Thermal Residual Anomaly',
      weight: '35%',
      score: Math.abs(features.thermalResidual) > 0.3 ? Math.min(1.0, Math.abs(features.thermalResidual) / 1.5) : 0,
      desc: `Deviation (${features.thermalResidual.toFixed(2)}°C) from learned room equilibrium baseline.`,
      icon: <ThermometerSnowflake className="w-4 h-4 text-indigo-600" />,
    },
    {
      title: 'Indoor/Outdoor Thermal Gradient',
      weight: 'Multiplier',
      score: evidence.thermalGradientSustained,
      desc: `Temperature difference (Δ${features.tempDiff.toFixed(1)}°C) provides thermodynamic driving force.`,
      icon: <Wind className="w-4 h-4 text-sky-600" />,
    },
    {
      title: 'Absolute Moisture Infiltration',
      weight: '15%',
      score: evidence.humidityMatchesOutdoorAir,
      desc: `Indoor absolute humidity shifted towards outdoor ambient moisture level.`,
      icon: <Sparkles className="w-4 h-4 text-teal-600" />,
    },
    {
      title: 'Adjacent Room Rate Divergence',
      weight: '10%',
      score: evidence.localDivergenceFromRefRoom,
      desc: `Room temperature rate is diverging from reference room baseline.`,
      icon: <Home className="w-4 h-4 text-emerald-600" />,
    },
    {
      title: 'Change-Point Inflection',
      weight: '15%',
      score: evidence.changePointTriggered,
      desc: `Page-Hinkley cumulative sum triggered a sudden trajectory inflection.`,
      icon: <AlertTriangle className="w-4 h-4 text-amber-600" />,
    },
  ];

  const negativeSignals = [
    {
      title: 'Heating Cycled Off Recently',
      score: evidence.heatingTurnedOffRecently,
      desc: 'HVAC turned off recently (<15m); natural cooling curve is expected.',
      active: evidence.heatingTurnedOffRecently > 0.1,
    },
    {
      title: 'Outdoor Air Cannot Cause Cooling',
      score: evidence.outdoorCannotExplainCooling,
      desc: 'Outdoor is warmer than indoor, yet room is cooling (e.g. A/C cooling).',
      active: evidence.outdoorCannotExplainCooling > 0.1,
    },
    {
      title: 'Global House-Wide Drop',
      score: evidence.multiRoomGlobalDrop,
      desc: 'Reference room also cooling at the exact same rate; indicates thermostat setback, not open window.',
      active: evidence.multiRoomGlobalDrop > 0.1,
    },
    {
      title: 'Internal Moisture Source (Shower/Steam)',
      score: evidence.internalMoistureSource,
      desc: 'Moisture spiked with warm temperature; indicates shower/cooking, not cold draft.',
      active: evidence.internalMoistureSource > 0.1,
    },
    {
      title: 'Anomaly Too Brief / Noise',
      score: evidence.anomalyTooBrief,
      desc: 'Transient temperature spike under 2 minutes.',
      active: evidence.anomalyTooBrief > 0.1,
    },
  ];

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Top Explanation Card */}
      <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">
              Continuous Evidence Fusion
            </span>
            <h2 className="text-lg font-bold text-slate-900 mt-0.5">
              Explainable Anomaly Model Architecture
            </h2>
            <p className="text-xs text-slate-500 mt-1 max-w-2xl">
              Rather than hard thresholds, multiple physical and comparative signals are weighted into a normalized probability score (0.0 – 1.0) with negative evidence suppression.
            </p>
          </div>

          <div className="flex items-center gap-4 bg-slate-50 p-3.5 rounded-xl border border-slate-200">
            <div>
              <span className="text-[11px] text-slate-500 block">Final Confidence</span>
              <span className="text-2xl font-bold text-purple-700">
                {Math.round(evidence.finalConfidence * 100)}%
              </span>
            </div>
            <div className="border-l border-slate-200 pl-4">
              <span className="text-[11px] text-slate-500 block">Inferred State</span>
              <span className={`text-base font-bold ${currentState.isOpen ? 'text-amber-600' : 'text-emerald-700'}`}>
                {currentState.isOpen ? 'WINDOW OPEN' : 'WINDOW CLOSED'}
              </span>
            </div>
          </div>
        </div>

        {/* Narrative Reason */}
        <div className="mt-4 p-3.5 bg-blue-50/60 rounded-lg border border-blue-200 text-xs text-blue-900 leading-relaxed font-medium">
          <strong>Synthesized Diagnostic Reason:</strong> "{evidence.primaryReason}"
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Positive Evidence Column */}
        <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div className="flex items-center gap-2">
              <div className="p-1.5 bg-blue-100 text-blue-700 rounded-lg">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <h3 className="text-sm font-bold text-slate-900">
                Positive Evidence Factors
              </h3>
            </div>
            <span className="text-xs font-mono text-slate-500">
              Raw Score: {(evidence.rawScore * 100).toFixed(0)}%
            </span>
          </div>

          <div className="space-y-3.5">
            {positiveSignals.map((sig, idx) => (
              <div key={idx} className="space-y-1 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-slate-800 flex items-center gap-1.5">
                    {sig.icon}
                    {sig.title}
                    <span className="text-[10px] font-normal text-slate-400">({sig.weight})</span>
                  </span>
                  <span className="font-mono font-bold text-slate-700">
                    {(sig.score * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                  <div
                    className="h-full bg-blue-600 rounded-full transition-all duration-300"
                    style={{ width: `${Math.min(100, sig.score * 100)}%` }}
                  />
                </div>
                <p className="text-[11px] text-slate-500">
                  {sig.desc}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Negative Evidence & Feature Table Column */}
        <div className="space-y-6">
          {/* Negative Evidence */}
          <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs space-y-4">
            <div className="flex items-center justify-between border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2">
                <div className="p-1.5 bg-rose-100 text-rose-700 rounded-lg">
                  <AlertTriangle className="w-4 h-4" />
                </div>
                <h3 className="text-sm font-bold text-slate-900">
                  Negative Evidence / False Positive Suppression
                </h3>
              </div>
              <span className="text-xs text-slate-400">Prevents nuisance alerts</span>
            </div>

            <div className="space-y-2.5">
              {negativeSignals.map((neg, idx) => (
                <div 
                  key={idx} 
                  className={`p-3 rounded-lg border text-xs transition-colors ${
                    neg.active 
                      ? 'bg-rose-50 border-rose-200 text-rose-950' 
                      : 'bg-slate-50 border-slate-200 text-slate-600'
                  }`}
                >
                  <div className="flex items-center justify-between font-semibold">
                    <span>{neg.title}</span>
                    <span className="font-mono">{neg.active ? `Penalty -${(neg.score * 100).toFixed(0)}%` : 'Dormant'}</span>
                  </div>
                  <p className="text-[11px] mt-0.5 opacity-80">
                    {neg.desc}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Rolling Extracted Features Snapshot */}
          <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs space-y-3">
            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider pb-2 border-b border-slate-100">
              Sliding Rolling Features (Section 4 Spec)
            </h3>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                <span className="text-slate-500 block text-[11px]">Δ 1 min</span>
                <span className="font-mono font-semibold text-slate-900">
                  {features.delta1m > 0 ? '+' : ''}{features.delta1m.toFixed(2)} °C
                </span>
              </div>
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                <span className="text-slate-500 block text-[11px]">Δ 5 min</span>
                <span className="font-mono font-semibold text-slate-900">
                  {features.delta5m > 0 ? '+' : ''}{features.delta5m.toFixed(2)} °C
                </span>
              </div>
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                <span className="text-slate-500 block text-[11px]">Δ 10 min</span>
                <span className="font-mono font-semibold text-slate-900">
                  {features.delta10m > 0 ? '+' : ''}{features.delta10m.toFixed(2)} °C
                </span>
              </div>
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                <span className="text-slate-500 block text-[11px]">Δ 20 min</span>
                <span className="font-mono font-semibold text-slate-900">
                  {features.delta20m > 0 ? '+' : ''}{features.delta20m.toFixed(2)} °C
                </span>
              </div>
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                <span className="text-slate-500 block text-[11px]">Temp Acceleration</span>
                <span className="font-mono font-semibold text-slate-900">
                  {features.tempAccel > 0 ? '+' : ''}{features.tempAccel.toFixed(2)} °C/h²
                </span>
              </div>
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                <span className="text-slate-500 block text-[11px]">Outdoor Rate</span>
                <span className="font-mono font-semibold text-slate-900">
                  {features.outdoorRate > 0 ? '+' : ''}{features.outdoorRate.toFixed(2)} °C/h
                </span>
              </div>
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                <span className="text-slate-500 block text-[11px]">Indoor Dew Point</span>
                <span className="font-mono font-semibold text-slate-900">
                  {features.dewPoint !== undefined ? `${features.dewPoint.toFixed(1)} °C` : '--'}
                </span>
              </div>
              <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200">
                <span className="text-slate-500 block text-[11px]">HVAC Context</span>
                <span className="font-mono font-semibold text-slate-900 capitalize">
                  {features.hvacState || 'idle'}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
