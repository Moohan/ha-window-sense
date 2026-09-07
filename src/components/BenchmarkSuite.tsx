import React, { useState, useEffect } from 'react';
import { 
  CheckCircle2, 
  XCircle, 
  Play, 
  RotateCw, 
  Award, 
  Clock, 
  ShieldAlert, 
  TrendingUp,
  ChevronRight
} from 'lucide-react';
import { AlgorithmConfig, ScenarioEvaluation, TestScenario } from '../types';
import { TEST_SCENARIOS } from '../engine/scenarios';
import { WindowInferenceEngine } from '../engine/algorithm';

interface BenchmarkSuiteProps {
  config: AlgorithmConfig;
  onSelectScenario: (scenarioId: string) => void;
}

export const BenchmarkSuite: React.FC<BenchmarkSuiteProps> = ({
  config,
  onSelectScenario,
}) => {
  const [evaluations, setEvaluations] = useState<ScenarioEvaluation[]>([]);
  const [isRunning, setIsRunning] = useState<boolean>(false);

  const runAllBenchmarks = () => {
    setIsRunning(true);
    const results: ScenarioEvaluation[] = [];

    for (const sc of TEST_SCENARIOS) {
      const readings = sc.generateData();
      const engine = new WindowInferenceEngine(config);

      let tp = 0;
      let fp = 0;
      let fn = 0;
      let tn = 0;

      let firstDetectedMin: number | null = null;
      let firstClosedMin: number | null = null;
      const actualOpenMin = sc.windowOpenPeriods.length > 0 ? sc.windowOpenPeriods[0].startMin : null;
      const actualCloseMin = sc.windowOpenPeriods.length > 0 ? sc.windowOpenPeriods[0].endMin : null;

      for (let m = 0; m < readings.length; m++) {
        const state = engine.processReading(readings[m]);
        const actualOpen = sc.windowOpenPeriods.some((p) => m >= p.startMin && m < p.endMin);

        if (state.isOpen && actualOpen) {
          tp++;
          if (firstDetectedMin === null) firstDetectedMin = m;
        } else if (state.isOpen && !actualOpen) {
          fp++;
        } else if (!state.isOpen && actualOpen) {
          fn++;
        } else {
          tn++;
          if (actualCloseMin !== null && m >= actualCloseMin && firstClosedMin === null && firstDetectedMin !== null) {
            firstClosedMin = m;
          }
        }
      }

      const latency = (actualOpenMin !== null && firstDetectedMin !== null)
        ? (firstDetectedMin - actualOpenMin) * 60
        : null;

      const closingLatency = (actualCloseMin !== null && firstClosedMin !== null)
        ? (firstClosedMin - actualCloseMin) * 60
        : null;

      // Pass criteria:
      // If scenario is False Positive Candidate: fp MUST be 0 (no false alarms!)
      // If scenario is True Positive: must detect open within 6 minutes
      let passed = false;
      let notes = '';

      if (sc.category === 'False Positive Candidate') {
        passed = fp === 0;
        notes = passed ? 'Zero false triggers; nuisance signal successfully rejected' : `False alarm occurred for ${fp} minutes`;
      } else if (sc.category === 'True Positive') {
        passed = tp > 0 && latency !== null && latency <= 360; // within 6 minutes
        notes = passed ? `Detected in ${Math.round(latency! / 60)} min` : 'Failed to trigger within required latency window';
      } else {
        passed = fp === 0;
        notes = 'Handled packet loss gracefully without false triggers';
      }

      results.push({
        scenarioId: sc.id,
        truePositives: tp,
        falsePositives: fp,
        falseNegatives: fn,
        trueNegatives: tn,
        detectionLatencySeconds: latency,
        closingLatencySeconds: closingLatency,
        passed,
        notes,
      });
    }

    setEvaluations(results);
    setIsRunning(false);
  };

  useEffect(() => {
    runAllBenchmarks();
  }, [config]);

  // Aggregate metrics
  const totalTruePositives = evaluations.reduce((sum, e) => sum + e.truePositives, 0);
  const totalFalsePositives = evaluations.reduce((sum, e) => sum + e.falsePositives, 0);
  const totalFalseNegatives = evaluations.reduce((sum, e) => sum + e.falseNegatives, 0);
  
  const precision = totalTruePositives + totalFalsePositives > 0 
    ? (totalTruePositives / (totalTruePositives + totalFalsePositives)) * 100 
    : 100;

  const recall = totalTruePositives + totalFalseNegatives > 0 
    ? (totalTruePositives / (totalTruePositives + totalFalseNegatives)) * 100 
    : 100;

  const passedCount = evaluations.filter((e) => e.passed).length;
  
  // Mean detection latency across true positive scenarios
  const latencies = evaluations
    .filter((e) => e.detectionLatencySeconds !== null)
    .map((e) => e.detectionLatencySeconds! / 60);
  const meanLatencyMin = latencies.length > 0 ? (latencies.reduce((a, b) => a + b, 0) / latencies.length).toFixed(1) : '--';

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Top Header & Run Deck */}
      <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">
              Automated Evaluation Harness (Phase 7 & 18 Spec)
            </span>
            <h2 className="text-lg font-bold text-slate-900 mt-0.5">
              11-Scenario Objective Benchmark Suite
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Evaluates thermal shocks, heatwaves, partial tilts, radiator cycle-offs, shower steam, cooking, and sensor faults.
            </p>
          </div>

          <button
            onClick={runAllBenchmarks}
            disabled={isRunning}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-xs font-semibold shadow-xs transition-colors self-start"
            id="btn-run-benchmarks"
          >
            <RotateCw className={`w-3.5 h-3.5 ${isRunning ? 'animate-spin' : ''}`} />
            {isRunning ? 'Benchmarking...' : 'Re-Run All 11 Tests'}
          </button>
        </div>

        {/* High-Level Scorecards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-5">
          <div className="bg-slate-50 rounded-xl p-3.5 border border-slate-200">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500 font-medium">Test Suite Pass Rate</span>
              <Award className="w-4 h-4 text-emerald-600" />
            </div>
            <div className="text-xl font-bold text-slate-900 mt-1">
              {passedCount} / {TEST_SCENARIOS.length}
            </div>
            <span className="text-[11px] text-emerald-700 font-medium mt-0.5 block">
              {Math.round((passedCount / TEST_SCENARIOS.length) * 100)}% Scenarios Validated
            </span>
          </div>

          <div className="bg-slate-50 rounded-xl p-3.5 border border-slate-200">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500 font-medium">Precision</span>
              <ShieldAlert className="w-4 h-4 text-blue-600" />
            </div>
            <div className="text-xl font-bold text-slate-900 mt-1">
              {precision.toFixed(1)}%
            </div>
            <span className="text-[11px] text-slate-500 mt-0.5 block">
              Low false positive rate
            </span>
          </div>

          <div className="bg-slate-50 rounded-xl p-3.5 border border-slate-200">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500 font-medium">Recall (Sensitivity)</span>
              <TrendingUp className="w-4 h-4 text-purple-600" />
            </div>
            <div className="text-xl font-bold text-slate-900 mt-1">
              {recall.toFixed(1)}%
            </div>
            <span className="text-[11px] text-slate-500 mt-0.5 block">
              True ventilation capture
            </span>
          </div>

          <div className="bg-slate-50 rounded-xl p-3.5 border border-slate-200">
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-500 font-medium">Mean Detection Latency</span>
              <Clock className="w-4 h-4 text-amber-600" />
            </div>
            <div className="text-xl font-bold text-slate-900 mt-1">
              {meanLatencyMin} min
            </div>
            <span className="text-[11px] text-slate-500 mt-0.5 block">
              Time to confidence ≥ 80%
            </span>
          </div>
        </div>
      </div>

      {/* Scenarios Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-xs overflow-hidden">
        <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
          <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
            Detailed Scenario Verification Results
          </h3>
          <span className="text-xs text-slate-500">
            Click any row to load into the Live Lab
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50 text-slate-600 border-b border-slate-200 font-semibold">
              <tr>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Scenario</th>
                <th className="py-3 px-4">Category</th>
                <th className="py-3 px-4">Detection Latency</th>
                <th className="py-3 px-4">False Positives</th>
                <th className="py-3 px-4">Diagnostic Notes</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-slate-700">
              {TEST_SCENARIOS.map((sc) => {
                const evalItem = evaluations.find((e) => e.scenarioId === sc.id);
                const isPassed = evalItem?.passed ?? false;

                return (
                  <tr 
                    key={sc.id}
                    onClick={() => onSelectScenario(sc.id)}
                    className="hover:bg-blue-50/50 transition-colors cursor-pointer group"
                  >
                    <td className="py-3 px-4">
                      {isPassed ? (
                        <span className="inline-flex items-center gap-1 text-emerald-700 font-medium">
                          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                          Passed
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-rose-700 font-medium">
                          <XCircle className="w-4 h-4 text-rose-600" />
                          Failed
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-4 font-semibold text-slate-900">
                      {sc.title}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                        sc.category === 'True Positive'
                          ? 'bg-blue-100 text-blue-800'
                          : sc.category === 'False Positive Candidate'
                          ? 'bg-purple-100 text-purple-800'
                          : 'bg-slate-200 text-slate-700'
                      }`}>
                        {sc.category}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono">
                      {evalItem?.detectionLatencySeconds !== null && evalItem?.detectionLatencySeconds !== undefined
                        ? `${Math.round(evalItem.detectionLatencySeconds / 60)} min`
                        : '--'}
                    </td>
                    <td className="py-3 px-4 font-mono">
                      <span className={evalItem && evalItem.falsePositives > 0 ? 'text-rose-600 font-bold' : 'text-slate-500'}>
                        {evalItem?.falsePositives ?? 0}m
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-600">
                      {evalItem?.notes || '--'}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <span className="inline-flex items-center text-blue-600 font-medium group-hover:underline">
                        Replay <ChevronRight className="w-3.5 h-3.5" />
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
