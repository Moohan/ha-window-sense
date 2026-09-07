import React, { useState } from 'react';
import { 
  AppWindow, 
  Gauge, 
  ChevronRight, 
  X, 
  Info, 
  Flame, 
  Droplets, 
  Clock, 
  HelpCircle,
  Copy,
  Check
} from 'lucide-react';
import { InferredState } from '../types';

interface LovelacePreviewProps {
  currentState: InferredState | null;
  selectedRoom: string;
}

export const LovelacePreview: React.FC<LovelacePreviewProps> = ({
  currentState,
  selectedRoom,
}) => {
  const [showMoreInfo, setShowMoreInfo] = useState<boolean>(false);
  const [copiedYaml, setCopiedYaml] = useState<boolean>(false);

  const roomSlug = selectedRoom.toLowerCase().replace(' ', '_');
  const entityId = `binary_sensor.${roomSlug}_window`;
  const confidenceEntityId = `sensor.${roomSlug}_window_confidence`;
  const isOpen = currentState?.isOpen ?? false;
  const confidence = currentState?.confidence ?? 0;

  const lovelaceYaml = `type: vertical-stack
cards:
  - type: tile
    entity: ${entityId}
    name: ${selectedRoom} Window
    icon: mdi:window-closed-variant
    color: ${isOpen ? 'amber' : 'blue'}
    tap_action:
      action: more-info

  - type: tile
    entity: ${confidenceEntityId}
    name: ${selectedRoom} Window Confidence
    icon: mdi:percent
    color: purple

  - type: entities
    title: Window Diagnostic Attributes
    show_header_toggle: false
    entities:
      - entity: ${entityId}
        name: Inferred State
      - entity: ${confidenceEntityId}
        name: Detection Confidence
      - type: attribute
        entity: ${entityId}
        attribute: thermal_anomaly
        name: Thermal Anomaly
      - type: attribute
        entity: ${entityId}
        attribute: temperature_rate
        name: Temperature Rate
      - type: attribute
        entity: ${entityId}
        attribute: reason
        name: Diagnostic Explanation`;

  const handleCopyYaml = () => {
    navigator.clipboard.writeText(lovelaceYaml);
    setCopiedYaml(true);
    setTimeout(() => setCopiedYaml(false), 2000);
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Introduction Banner */}
      <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-slate-900">
              Home Assistant Dashboard (Lovelace UI Simulation)
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              Live representation of how entities, tile cards, and more-info modals render in standard Home Assistant.
            </p>
          </div>
          <button
            onClick={handleCopyYaml}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-medium rounded-lg border border-slate-300 transition-colors self-start"
            id="copy-lovelace-yaml"
          >
            {copiedYaml ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
            {copiedYaml ? 'Copied YAML!' : 'Copy Dashboard YAML'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Left Column: Lovelace Tiles & Entities Card */}
        <div className="space-y-4">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider px-1">
            Dashboard Cards Preview
          </div>

          {/* Lovelace Tile Card: Window Binary Sensor */}
          <div 
            onClick={() => setShowMoreInfo(true)}
            className="bg-white rounded-2xl p-4 border border-slate-200 shadow-sm hover:shadow-md hover:border-slate-300 transition-all cursor-pointer group relative overflow-hidden"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3.5">
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center transition-colors ${
                  isOpen 
                    ? 'bg-amber-100 text-amber-600' 
                    : 'bg-blue-50 text-blue-600'
                }`}>
                  <AppWindow className="w-6 h-6" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-slate-900 group-hover:text-blue-600 transition-colors">
                    {selectedRoom} Window
                  </h4>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className={`inline-block w-2 h-2 rounded-full ${isOpen ? 'bg-amber-500 animate-pulse' : 'bg-emerald-500'}`} />
                    <span className="text-xs font-medium text-slate-600">
                      {isOpen ? 'Open' : 'Closed'}
                    </span>
                    <span className="text-[11px] text-slate-400 font-mono">
                      · {confidence}%
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-1 text-slate-400 group-hover:text-slate-600">
                <span className="text-xs">More info</span>
                <ChevronRight className="w-4 h-4" />
              </div>
            </div>

            {/* Quick status pill inside tile */}
            <div className="mt-3 pt-2.5 border-t border-slate-100 text-[11px] text-slate-500 flex items-center justify-between">
              <span className="truncate max-w-[280px]">
                {currentState?.reason || 'Baseline normal'}
              </span>
              <span className="font-mono font-medium text-slate-700 shrink-0">
                {currentState?.temperatureRate ?? 0}°C/h
              </span>
            </div>
          </div>

          {/* Lovelace Tile Card: Confidence Sensor */}
          <div className="bg-white rounded-2xl p-4 border border-slate-200 shadow-sm">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3.5">
                <div className="w-12 h-12 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center">
                  <Gauge className="w-6 h-6" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-slate-900">
                    {selectedRoom} Window Confidence
                  </h4>
                  <div className="text-lg font-bold text-purple-700">
                    {confidence} <span className="text-xs font-normal text-slate-500">%</span>
                  </div>
                </div>
              </div>

              <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                Measurement
              </span>
            </div>
          </div>

          {/* Lovelace Entities Card */}
          <div className="bg-white rounded-2xl p-4 border border-slate-200 shadow-sm space-y-3">
            <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider pb-2 border-b border-slate-100">
              Inferred Diagnostic Entities
            </h4>

            <div className="space-y-2.5 text-xs">
              <div className="flex items-center justify-between py-1">
                <span className="text-slate-600">Model Readiness</span>
                <span className="font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                  {currentState?.readiness || 'Ready'}
                </span>
              </div>

              <div className="flex items-center justify-between py-1 border-t border-slate-100">
                <span className="text-slate-600">Thermal Anomaly (Residual)</span>
                <span className="font-mono font-semibold text-slate-800">
                  {(currentState?.thermalAnomaly ?? 0) > 0 ? '+' : ''}
                  {currentState?.thermalAnomaly ?? 0} °C
                </span>
              </div>

              <div className="flex items-center justify-between py-1 border-t border-slate-100">
                <span className="text-slate-600">Indoor / Outdoor Gradient</span>
                <span className="font-mono font-semibold text-slate-800">
                  Δ{currentState?.tempDiff ?? 0} °C
                </span>
              </div>

              <div className="flex items-center justify-between py-1 border-t border-slate-100">
                <span className="text-slate-600">Absolute Humidity Signal</span>
                <span className="font-mono text-slate-700">
                  {currentState?.humiditySignal}
                </span>
              </div>

              <div className="flex items-center justify-between py-1 border-t border-slate-100">
                <span className="text-slate-600">Reference Room Rate Difference</span>
                <span className="font-mono text-slate-700">
                  {currentState?.referenceRoomSignal}
                </span>
              </div>

              <div className="flex items-center justify-between py-1 border-t border-slate-100">
                <span className="text-slate-600">HVAC Operation Signal</span>
                <span className="capitalize font-medium text-slate-700">
                  {currentState?.hvacSignal}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Home Assistant More-Info Dialog Simulation */}
        <div>
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider px-1 mb-2">
            More-Info Entity Dialog
          </div>

          <div className="bg-white rounded-2xl border border-slate-300 shadow-md p-5 space-y-4">
            <div className="flex items-start justify-between pb-3 border-b border-slate-100">
              <div className="flex items-center gap-3">
                <div className={`p-2.5 rounded-xl ${isOpen ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'}`}>
                  <AppWindow className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-base font-bold text-slate-900">
                    {selectedRoom} Window
                  </h3>
                  <p className="text-xs text-slate-500 font-mono">
                    {entityId}
                  </p>
                </div>
              </div>
              <span className={`px-2.5 py-1 rounded-full text-xs font-bold ${
                isOpen ? 'bg-amber-500 text-white' : 'bg-emerald-600 text-white'
              }`}>
                {isOpen ? 'Open' : 'Closed'}
              </span>
            </div>

            {/* Simulated History Bar */}
            <div>
              <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
                <span>State History (Past 2 Hours)</span>
                <span>device_class: window</span>
              </div>
              <div className="h-4 w-full rounded-md overflow-hidden flex border border-slate-200">
                <div className="bg-emerald-500 h-full w-[45%]" title="Closed" />
                <div className="bg-amber-500 h-full w-[35%]" title="Open" />
                <div className="bg-emerald-500 h-full w-[20%]" title="Closed" />
              </div>
              <div className="flex justify-between text-[10px] text-slate-400 mt-1 font-mono">
                <span>2h ago</span>
                <span>1h ago</span>
                <span>Now</span>
              </div>
            </div>

            {/* Diagnostic Reason Box in HA style */}
            <div className="bg-slate-50 rounded-xl p-3.5 border border-slate-200">
              <div className="text-xs font-semibold text-slate-700 mb-1 flex items-center gap-1.5">
                <Info className="w-3.5 h-3.5 text-blue-600" />
                Inference Reason (attribute: reason)
              </div>
              <p className="text-xs text-slate-700 leading-relaxed font-serif italic">
                "{currentState?.reason}"
              </p>
            </div>

            {/* Full extra_state_attributes Table */}
            <div>
              <div className="text-xs font-semibold text-slate-700 mb-2">
                All State Attributes
              </div>
              <div className="bg-slate-50 rounded-xl p-3 border border-slate-200 text-xs font-mono space-y-1.5 text-slate-600">
                <div className="flex justify-between">
                  <span className="text-slate-500">device_class:</span>
                  <span className="text-slate-900 font-semibold">window</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">confidence:</span>
                  <span className="text-slate-900">{currentState?.confidence}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">detection_quality:</span>
                  <span className="text-slate-900">{currentState?.detectionQuality}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">thermal_anomaly:</span>
                  <span className="text-slate-900">{currentState?.thermalAnomaly} °C</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">temperature_rate:</span>
                  <span className="text-slate-900">{currentState?.temperatureRate} °C/h</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">indoor_temperature:</span>
                  <span className="text-slate-900">{currentState?.indoorTemp} °C</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">outdoor_temperature:</span>
                  <span className="text-slate-900">{currentState?.outdoorTemp} °C</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">temperature_difference:</span>
                  <span className="text-slate-900">{currentState?.tempDiff} °C</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">readiness:</span>
                  <span className="text-slate-900">{currentState?.readiness}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">samples_available:</span>
                  <span className="text-slate-900">{currentState?.samplesAvailable}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
