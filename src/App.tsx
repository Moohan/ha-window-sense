import React, { useState } from 'react';
import { Header } from './components/Header';
import { ReplayLab } from './components/ReplayLab';
import { LovelacePreview } from './components/LovelacePreview';
import { EvidenceExplainer } from './components/EvidenceExplainer';
import { BenchmarkSuite } from './components/BenchmarkSuite';
import { TuningModal } from './components/TuningModal';
import { HaIntegrationExporter } from './components/HaIntegrationExporter';
import { AlgorithmConfig, InferredState } from './types';
import { DEFAULT_CONFIG } from './engine/algorithm';

export default function App() {
  const [activeTab, setActiveTab] = useState<'replay' | 'lovelace' | 'evidence' | 'benchmark' | 'tuning' | 'export'>('replay');
  const [selectedRoom, setSelectedRoom] = useState<string>('Bedroom');
  const [config, setConfig] = useState<AlgorithmConfig>(DEFAULT_CONFIG);
  const [currentState, setCurrentState] = useState<InferredState | null>(null);

  const handleSelectScenarioFromBenchmark = (scenarioId: string) => {
    setActiveTab('replay');
    // The scenario selector in ReplayLab will pick up or user can review in the lab
  };

  return (
    <div className="min-h-screen bg-slate-100/70 text-slate-900 flex flex-col font-sans antialiased">
      <Header
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        currentState={currentState}
        selectedRoom={selectedRoom}
        setSelectedRoom={setSelectedRoom}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activeTab === 'replay' && (
          <ReplayLab
            config={config}
            currentState={currentState}
            onStateUpdate={setCurrentState}
            selectedRoom={selectedRoom}
          />
        )}

        {activeTab === 'lovelace' && (
          <LovelacePreview
            currentState={currentState}
            selectedRoom={selectedRoom}
          />
        )}

        {activeTab === 'evidence' && (
          <EvidenceExplainer
            currentState={currentState}
          />
        )}

        {activeTab === 'benchmark' && (
          <BenchmarkSuite
            config={config}
            onSelectScenario={handleSelectScenarioFromBenchmark}
          />
        )}

        {activeTab === 'tuning' && (
          <TuningModal
            config={config}
            onChangeConfig={setConfig}
          />
        )}

        {activeTab === 'export' && (
          <HaIntegrationExporter />
        )}
      </main>

      {/* Persistent Footer */}
      <footer className="bg-white border-t border-slate-200 py-4 text-xs text-slate-500 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span>Local Thermodynamic Inference Engine · No Cloud ML Required</span>
          </div>
          <div className="flex items-center gap-4 text-slate-400">
            <span>Home Assistant 2026 Compatible</span>
            <span>device_class: window</span>
            <span>Version 1.0.0</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
