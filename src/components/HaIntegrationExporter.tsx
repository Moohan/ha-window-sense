import React, { useState } from 'react';
import { 
  FileCode, 
  Copy, 
  Check, 
  Download, 
  FolderCheck, 
  Terminal, 
  ExternalLink,
  Layers
} from 'lucide-react';
import { HA_COMPONENT_FILES, HaFile } from '../engine/haExportCode';

export const HaIntegrationExporter: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<HaFile>(HA_COMPONENT_FILES[0]);
  const [copied, setCopied] = useState<boolean>(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(selectedFile.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownloadFile = () => {
    const blob = new Blob([selectedFile.code], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = selectedFile.filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6 max-w-6xl mx-auto">
      {/* Top Banner */}
      <div className="bg-white rounded-xl p-5 border border-slate-200 shadow-xs">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">
              Phase 3 & Section 13 Implementation
            </span>
            <h2 className="text-lg font-bold text-slate-900 mt-0.5">
              Home Assistant Custom Component Codebase
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Production-ready Python integration for Home Assistant. Implements `DataUpdateCoordinator`, `BinarySensorEntity`, UI `config_flow`, and the local hybrid inference algorithm.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-semibold rounded-lg border border-slate-300 transition-colors"
              id="copy-current-file-btn"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? 'Copied File!' : 'Copy Current File'}
            </button>
            <button
              onClick={handleDownloadFile}
              className="inline-flex items-center gap-1.5 px-3.5 py-2 bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold rounded-lg shadow-xs transition-colors"
              id="download-file-btn"
            >
              <Download className="w-3.5 h-3.5" />
              Download {selectedFile.filename}
            </button>
          </div>
        </div>

        {/* Installation Instructions */}
        <div className="mt-4 pt-4 border-t border-slate-100 grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
            <span className="font-bold text-slate-800 block mb-1">1. Copy to Home Assistant</span>
            <p className="text-slate-600">
              Create folder <code className="bg-white px-1.5 py-0.5 rounded border text-slate-800 font-mono">custom_components/inferred_window</code> in your HA config directory.
            </p>
          </div>
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
            <span className="font-bold text-slate-800 block mb-1">2. Restart Home Assistant</span>
            <p className="text-slate-600">
              Restart Home Assistant to discover the new integration manifest.
            </p>
          </div>
          <div className="bg-slate-50 p-3 rounded-lg border border-slate-200">
            <span className="font-bold text-slate-800 block mb-1">3. Add via UI Config Flow</span>
            <p className="text-slate-600">
              Go to <strong>Settings → Devices & Services → Add Integration</strong> and search for <em>Inferred Window Detection</em>.
            </p>
          </div>
        </div>
      </div>

      {/* Code Browser */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Left: File Tree */}
        <div className="bg-white rounded-xl border border-slate-200 shadow-xs p-4 space-y-2">
          <div className="text-xs font-bold text-slate-700 uppercase tracking-wider pb-2 border-b border-slate-100 flex items-center justify-between">
            <span>Component Files</span>
            <span className="font-mono text-[11px] text-slate-400">7 files</span>
          </div>

          <div className="space-y-1">
            {HA_COMPONENT_FILES.map((f) => (
              <button
                key={f.filename}
                onClick={() => setSelectedFile(f)}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-colors text-left ${
                  selectedFile.filename === f.filename
                    ? 'bg-blue-50 text-blue-700 font-semibold border border-blue-200'
                    : 'text-slate-700 hover:bg-slate-100 border border-transparent'
                }`}
              >
                <span className="flex items-center gap-2 font-mono truncate">
                  <FileCode className="w-4 h-4 shrink-0 text-slate-500" />
                  {f.filename}
                </span>
              </button>
            ))}
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500">
            <strong>Target Path:</strong>
            <p className="font-mono text-slate-700 text-[10px] break-all mt-0.5">
              {selectedFile.path}
            </p>
          </div>
        </div>

        {/* Right: Code Viewer */}
        <div className="lg:col-span-3 bg-slate-950 rounded-xl border border-slate-800 shadow-lg overflow-hidden flex flex-col">
          <div className="bg-slate-900 px-4 py-3 border-b border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full bg-rose-500" />
              <span className="w-3 h-3 rounded-full bg-amber-500" />
              <span className="w-3 h-3 rounded-full bg-emerald-500" />
              <span className="text-xs font-mono text-slate-300 ml-2">
                {selectedFile.path}
              </span>
            </div>
            <span className="text-xs text-slate-400">
              {selectedFile.description}
            </span>
          </div>

          <div className="p-4 overflow-x-auto max-h-[600px] font-mono text-xs text-slate-200 leading-relaxed scrollbar-thin scrollbar-thumb-slate-800">
            <pre>
              <code>{selectedFile.code}</code>
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};
