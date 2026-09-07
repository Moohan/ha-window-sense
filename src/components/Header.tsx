import React from 'react';
import { 
  AppWindow, 
  Activity, 
  Settings, 
  Download, 
  Layers, 
  CheckCircle2, 
  AlertCircle,
  HelpCircle
} from 'lucide-react';
import { InferredState, ModelReadiness } from '../types';

interface HeaderProps {
  activeTab: 'replay' | 'lovelace' | 'evidence' | 'benchmark' | 'tuning' | 'export';
  setActiveTab: (tab: 'replay' | 'lovelace' | 'evidence' | 'benchmark' | 'tuning' | 'export') => void;
  currentState: InferredState | null;
  selectedRoom: string;
  setSelectedRoom: (room: string) => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  setActiveTab,
  currentState,
  selectedRoom,
  setSelectedRoom,
}) => {
  const isOpen = currentState?.isOpen ?? false;
  const confidence = currentState?.confidence ?? 0;
  const readiness = currentState?.readiness ?? 'Learning';

  const readinessBadge = (state: ModelReadiness) => {
    switch (state) {
      case 'Ready':
        return <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800 border border-emerald-200">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 animate-pulse"></span>
          Ready
        </span>;
      case 'Learning':
        return <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-800 border border-amber-200">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
          Learning
        </span>;
      case 'Low confidence':
        return <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
          Low Confidence
        </span>;
      default:
        return <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-100 text-slate-700 border border-slate-200">
          Insufficient Data
        </span>;
    }
  };

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-30 shadow-xs">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between py-3.5 gap-3">
          {/* Logo & Title */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-blue-600 text-white flex items-center justify-center shadow-xs">
              <AppWindow className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-semibold text-slate-900 tracking-tight">
                  Inferred Window Detection
                </h1>
                <span className="text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-600 font-mono font-medium border border-slate-200">
                  Home Assistant Integration
                </span>
              </div>
              <p className="text-xs text-slate-500">
                Local statistical anomaly model & thermodynamic evidence fusion
              </p>
            </div>
          </div>

          {/* Room Selector & State Pill */}
          <div className="flex items-center flex-wrap gap-2.5">
            <div className="flex items-center gap-1.5 bg-slate-100 p-1 rounded-lg border border-slate-200 text-xs">
              <span className="text-slate-500 pl-1.5 font-medium">Room:</span>
              <select 
                value={selectedRoom}
                onChange={(e) => setSelectedRoom(e.target.value)}
                className="bg-white text-slate-800 font-medium px-2 py-1 rounded border border-slate-200 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
                id="room-selector-dropdown"
              >
                <option value="Bedroom">Master Bedroom</option>
                <option value="Living Room">Living Room</option>
                <option value="Kitchen">Kitchen</option>
                <option value="Office">Home Office</option>
              </select>
            </div>

            {readinessBadge(readiness)}

            {/* Live State Badge */}
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border font-medium text-xs transition-all ${
              isOpen 
                ? 'bg-amber-500/10 text-amber-700 border-amber-300' 
                : 'bg-emerald-500/10 text-emerald-800 border-emerald-300'
            }`}>
              <div className={`w-2 h-2 rounded-full ${isOpen ? 'bg-amber-500 animate-ping' : 'bg-emerald-500'}`} />
              <span>
                Window is <strong>{isOpen ? 'OPEN' : 'CLOSED'}</strong>
              </span>
              <span className="opacity-60 text-[11px] font-mono">({confidence}%)</span>
            </div>
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="flex items-center gap-1 border-t border-slate-100 pt-1 -mb-px overflow-x-auto text-xs font-medium scrollbar-none">
          <button
            id="tab-replay"
            onClick={() => setActiveTab('replay')}
            className={`flex items-center gap-1.5 px-3 py-2.5 border-b-2 whitespace-nowrap transition-colors ${
              activeTab === 'replay'
                ? 'border-blue-600 text-blue-700 font-semibold'
                : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            Live Lab & Replay
          </button>

          <button
            id="tab-lovelace"
            onClick={() => setActiveTab('lovelace')}
            className={`flex items-center gap-1.5 px-3 py-2.5 border-b-2 whitespace-nowrap transition-colors ${
              activeTab === 'lovelace'
                ? 'border-blue-600 text-blue-700 font-semibold'
                : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300'
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            Home Assistant Cards
          </button>

          <button
            id="tab-evidence"
            onClick={() => setActiveTab('evidence')}
            className={`flex items-center gap-1.5 px-3 py-2.5 border-b-2 whitespace-nowrap transition-colors ${
              activeTab === 'evidence'
                ? 'border-blue-600 text-blue-700 font-semibold'
                : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300'
            }`}
          >
            <HelpCircle className="w-3.5 h-3.5" />
            Diagnostics & Explainability
          </button>

          <button
            id="tab-benchmark"
            onClick={() => setActiveTab('benchmark')}
            className={`flex items-center gap-1.5 px-3 py-2.5 border-b-2 whitespace-nowrap transition-colors ${
              activeTab === 'benchmark'
                ? 'border-blue-600 text-blue-700 font-semibold'
                : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300'
            }`}
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            Scenario Benchmarks (11 Tests)
          </button>

          <button
            id="tab-tuning"
            onClick={() => setActiveTab('tuning')}
            className={`flex items-center gap-1.5 px-3 py-2.5 border-b-2 whitespace-nowrap transition-colors ${
              activeTab === 'tuning'
                ? 'border-blue-600 text-blue-700 font-semibold'
                : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300'
            }`}
          >
            <Settings className="w-3.5 h-3.5" />
            Hysteresis & Model Tuning
          </button>

          <button
            id="tab-export"
            onClick={() => setActiveTab('export')}
            className={`flex items-center gap-1.5 px-3 py-2.5 border-b-2 whitespace-nowrap transition-colors ${
              activeTab === 'export'
                ? 'border-blue-600 text-blue-700 font-semibold'
                : 'border-transparent text-slate-600 hover:text-slate-900 hover:border-slate-300'
            }`}
          >
            <Download className="w-3.5 h-3.5" />
            HA Integration Code (.py)
          </button>
        </div>
      </div>
    </header>
  );
};
