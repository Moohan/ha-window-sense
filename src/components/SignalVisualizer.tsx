import React from 'react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ReferenceArea,
} from 'recharts';
import { AlgorithmConfig, InferredState, TestScenario } from '../types';

const TypedReferenceArea = ReferenceArea as unknown as React.ComponentType<any>;

interface ChartPoint {
  timeMin: number;
  indoorTemp: number;
  outdoorTemp: number;
  baselineTemp?: number;
  referenceTemp?: number;
  indoorRH?: number;
  outdoorRH?: number;
  indoorAH?: number;
  outdoorAH?: number;
  tempRate: number;
  thermalResidual: number;
  confidence: number;
  inferredOpen: number; // 0 or 1
  actualOpen: number; // 0 or 1
  changePoint: number; // 0 or 1
}

interface SignalVisualizerProps {
  chartData: ChartPoint[];
  currentStepIndex: number;
  config: AlgorithmConfig;
  scenario: TestScenario;
  onScrub?: (index: number) => void;
}

export const SignalVisualizer: React.FC<SignalVisualizerProps> = ({
  chartData,
  currentStepIndex,
  config,
  scenario,
  onScrub,
}) => {
  const currentPoint = chartData[currentStepIndex];

  return (
    <div className="space-y-4">
      {/* Chart 1: Temperature & Baseline */}
      <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-xs">
        <div className="flex flex-wrap items-center justify-between mb-2 gap-2">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">
              Thermal Dynamics & Adaptive Baseline
            </h3>
            <p className="text-xs text-slate-500">
              Indoor temp vs. learned thermal trajectory and outdoor gradient
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs">
            <span className="inline-flex items-center gap-1 text-slate-600">
              <span className="w-2.5 h-2.5 rounded-full bg-blue-600"></span> Indoor Temp
            </span>
            <span className="inline-flex items-center gap-1 text-slate-600">
              <span className="w-2.5 h-2.5 rounded-full bg-indigo-400"></span> Baseline
            </span>
            <span className="inline-flex items-center gap-1 text-slate-600">
              <span className="w-2.5 h-2.5 rounded-full bg-slate-400"></span> Outdoor
            </span>
            <span className="inline-flex items-center gap-1 text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200">
              <span className="w-2 h-2 rounded-full bg-amber-500"></span> True Open Period
            </span>
          </div>
        </div>

        <div className="h-56 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartData}
              onClick={(e) => {
                if (e && e.activeTooltipIndex !== undefined && onScrub) {
                  onScrub(e.activeTooltipIndex);
                }
              }}
              margin={{ top: 5, right: 15, left: -20, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="timeMin"
                unit="m"
                tick={{ fontSize: 11, fill: '#64748b' }}
                stroke="#cbd5e1"
              />
              <YAxis
                unit="°C"
                domain={['auto', 'auto']}
                tick={{ fontSize: 11, fill: '#64748b' }}
                stroke="#cbd5e1"
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#ffffff',
                  borderColor: '#e2e8f0',
                  borderRadius: '0.5rem',
                  fontSize: '12px',
                  boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)',
                }}
                formatter={(val: any, name: any) => [
                  typeof val === 'number' ? `${val.toFixed(2)} °C` : val,
                  name,
                ]}
                labelFormatter={(label) => `Minute ${label}`}
              />

              {/* Shaded actual window open areas from scenario */}
              {scenario.windowOpenPeriods.map((period, i) => (
                <TypedReferenceArea
                  key={`window-period-${i}`}
                  x1={period.startMin}
                  x2={period.endMin}
                  fill="#f59e0b"
                  fillOpacity={0.12}
                  stroke="#d97706"
                  strokeDasharray="2 2"
                />
              ))}

              {/* Scrub cursor line */}
              {currentPoint && (
                <ReferenceLine
                  x={currentPoint.timeMin}
                  stroke="#ef4444"
                  strokeWidth={2}
                  label={{ value: 'T', position: 'top', fill: '#ef4444', fontSize: 10 }}
                />
              )}

              <Line
                type="monotone"
                dataKey="indoorTemp"
                name="Indoor Temp"
                stroke="#2563eb"
                strokeWidth={2.2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="baselineTemp"
                name="Learned Baseline"
                stroke="#818cf8"
                strokeWidth={1.8}
                strokeDasharray="4 4"
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="outdoorTemp"
                name="Outdoor Temp"
                stroke="#64748b"
                strokeWidth={1.5}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="referenceTemp"
                name="Ref Room Temp"
                stroke="#10b981"
                strokeWidth={1.2}
                strokeDasharray="2 2"
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Chart 2: Absolute & Relative Humidity */}
      <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-xs">
        <div className="flex flex-wrap items-center justify-between mb-2 gap-2">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">
              Psychrometric & Absolute Moisture Exchange
            </h3>
            <p className="text-xs text-slate-500">
              Absolute humidity (g/m³) is conserved unless external air infiltrates
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs">
            <span className="inline-flex items-center gap-1 text-teal-700">
              <span className="w-2.5 h-2.5 rounded-full bg-teal-600"></span> Indoor AH (g/m³)
            </span>
            <span className="inline-flex items-center gap-1 text-slate-600">
              <span className="w-2.5 h-2.5 rounded-full bg-slate-400"></span> Outdoor AH (g/m³)
            </span>
            <span className="inline-flex items-center gap-1 text-cyan-600">
              <span className="w-2.5 h-2.5 rounded-full bg-cyan-400"></span> Indoor RH (%)
            </span>
          </div>
        </div>

        <div className="h-44 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartData}
              onClick={(e) => {
                if (e && e.activeTooltipIndex !== undefined && onScrub) {
                  onScrub(e.activeTooltipIndex);
                }
              }}
              margin={{ top: 5, right: 15, left: -20, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="timeMin"
                unit="m"
                tick={{ fontSize: 11, fill: '#64748b' }}
                stroke="#cbd5e1"
              />
              <YAxis
                yAxisId="ah"
                unit="g/m³"
                domain={['auto', 'auto']}
                tick={{ fontSize: 11, fill: '#0f766e' }}
                stroke="#0f766e"
              />
              <YAxis
                yAxisId="rh"
                orientation="right"
                unit="%"
                domain={[0, 100]}
                tick={{ fontSize: 11, fill: '#0891b2' }}
                stroke="#0891b2"
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#ffffff',
                  borderColor: '#e2e8f0',
                  borderRadius: '0.5rem',
                  fontSize: '12px',
                }}
              />

              {currentPoint && (
                <ReferenceLine
                  yAxisId="ah"
                  x={currentPoint.timeMin}
                  stroke="#ef4444"
                  strokeWidth={2}
                />
              )}

              <Line
                yAxisId="ah"
                type="monotone"
                dataKey="indoorAH"
                name="Indoor AH"
                stroke="#0f766e"
                strokeWidth={2}
                dot={false}
              />
              <Line
                yAxisId="ah"
                type="monotone"
                dataKey="outdoorAH"
                name="Outdoor AH"
                stroke="#94a3b8"
                strokeWidth={1.5}
                strokeDasharray="3 3"
                dot={false}
              />
              <Line
                yAxisId="rh"
                type="monotone"
                dataKey="indoorRH"
                name="Indoor RH"
                stroke="#06b6d4"
                strokeWidth={1.5}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Chart 3: Confidence Score & Hysteresis Thresholds */}
      <div className="bg-white rounded-xl p-4 border border-slate-200 shadow-xs">
        <div className="flex flex-wrap items-center justify-between mb-2 gap-2">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">
              Confidence Score, Hysteresis & Binary State
            </h3>
            <p className="text-xs text-slate-500">
              Requires {Math.round(config.openConfidenceThreshold * 100)}% for {config.openPersistenceMinutes}m to Open; ≤{Math.round(config.closeConfidenceThreshold * 100)}% for {config.closePersistenceMinutes}m to Close
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs">
            <span className="inline-flex items-center gap-1 text-purple-700">
              <span className="w-2.5 h-2.5 rounded-full bg-purple-600"></span> Confidence (%)
            </span>
            <span className="inline-flex items-center gap-1 text-amber-700">
              <span className="w-2.5 h-2.5 rounded-full bg-amber-500"></span> Inferred Open
            </span>
          </div>
        </div>

        <div className="h-44 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartData}
              onClick={(e) => {
                if (e && e.activeTooltipIndex !== undefined && onScrub) {
                  onScrub(e.activeTooltipIndex);
                }
              }}
              margin={{ top: 5, right: 15, left: -20, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="timeMin"
                unit="m"
                tick={{ fontSize: 11, fill: '#64748b' }}
                stroke="#cbd5e1"
              />
              <YAxis
                domain={[0, 100]}
                unit="%"
                tick={{ fontSize: 11, fill: '#64748b' }}
                stroke="#cbd5e1"
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#ffffff',
                  borderColor: '#e2e8f0',
                  borderRadius: '0.5rem',
                  fontSize: '12px',
                }}
              />

              {/* Open threshold reference line */}
              <ReferenceLine
                y={config.openConfidenceThreshold * 100}
                stroke="#ef4444"
                strokeDasharray="4 4"
                label={{ value: `Open Thresh (${Math.round(config.openConfidenceThreshold * 100)}%)`, fill: '#ef4444', fontSize: 10 }}
              />
              {/* Close threshold reference line */}
              <ReferenceLine
                y={config.closeConfidenceThreshold * 100}
                stroke="#10b981"
                strokeDasharray="4 4"
                label={{ value: `Close Thresh (${Math.round(config.closeConfidenceThreshold * 100)}%)`, fill: '#10b981', fontSize: 10 }}
              />

              {currentPoint && (
                <ReferenceLine
                  x={currentPoint.timeMin}
                  stroke="#ef4444"
                  strokeWidth={2}
                />
              )}

              <Line
                type="monotone"
                dataKey="confidence"
                name="Confidence (%)"
                stroke="#8b5cf6"
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="stepAfter"
                dataKey={(d) => d.inferredOpen * 85}
                name="Inferred Window Open"
                stroke="#f59e0b"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
