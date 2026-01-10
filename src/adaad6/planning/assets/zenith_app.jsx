import React, { useState, useEffect, useRef } from 'react';
import {
  ShieldAlert,
  Zap,
  Lock,
  Database,
  Activity,
  Terminal,
  Fingerprint,
  Cpu,
  Play,
  Volume2,
  TrendingUp,
  History,
  AlertTriangle,
  Eye,
  Crosshair,
  Layers
} from 'lucide-react';

const App = () => {
  const [activeTab, setActiveTab] = useState('ZENITH');
  const [glitchText, setGlitchText] = useState('STILL STANDING');
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [systemLoad, setSystemLoad] = useState(62);
  const containerRef = useRef(null);

  // Mouse tracking for "Adaptive Parallax"
  const handleMouseMove = (e) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    setMousePos({
      x: (e.clientX - rect.left) / rect.width - 0.5,
      y: (e.clientY - rect.top) / rect.height - 0.5
    });
  };

  useEffect(() => {
    const interval = setInterval(() => {
      const phrases = ['STILL STANDING', 'PROPHETIC pH', 'NO MISTAKES', '5TH GEN ELITE', 'OWN THE PATH'];
      setGlitchText(phrases[Math.floor(Math.random() * phrases.length)]);
      setSystemLoad(Math.floor(Math.random() * (99 - 90 + 1) + 90));
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      className="min-h-screen bg-[#050507] text-gray-400 font-mono overflow-hidden flex items-center justify-center p-4 selection:bg-red-600 selection:text-white"
    >
      {/* Dynamic Background Noise */}
      <div className="fixed inset-0 pointer-events-none opacity-20">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_1px_1px,rgba(255,255,255,0.06)_1px,transparent_0)] bg-[length:4px_4px] opacity-10" />
        <div className="absolute inset-0 bg-gradient-to-tr from-red-900/10 via-transparent to-blue-900/5" />
      </div>

      {/* Main Framework */}
      <div
        style={{
          transform: `perspective(1000px) rotateY(${mousePos.x * 2}deg) rotateX(${-mousePos.y * 2}deg)`,
          transition: 'transform 0.1s ease-out'
        }}
        className="w-full max-w-7xl h-[85vh] bg-[#0a0a0c] border border-white/5 shadow-[0_0_100px_rgba(0,0,0,0.8)] rounded-lg flex flex-col relative overflow-hidden backdrop-blur-md"
      >
        {/* CRT Scanline Effect */}
        <div className="absolute inset-0 pointer-events-none z-50 opacity-[0.03] bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.25)_50%),linear-gradient(90deg,rgba(255,0,0,0.06),rgba(0,255,0,0.02),rgba(0,0,255,0.06))] bg-[length:100%_4px,4px_100%]" />

        {/* Top Navigation / Status Header */}
        <div className="h-14 border-b border-white/5 flex items-center justify-between px-6 bg-black/40 backdrop-blur-xl">
          <div className="flex items-center gap-8">
            <div className="flex items-center gap-3">
              <div className="w-3 h-3 bg-red-600 rounded-full shadow-[0_0_10px_#dc2626] animate-pulse" />
              <span className="text-xs font-black tracking-[0.5em] text-white">ADAAD // ZENITH_STATE</span>
            </div>
            <nav className="hidden md:flex items-center gap-6">
              <TabBtn label="SYSTEM_ZENITH" id="ZENITH" active={activeTab} onClick={setActiveTab} />
              <TabBtn label="FORGE_DYNAMICS" id="FORGE" active={activeTab} onClick={setActiveTab} />
              <TabBtn label="LEGACY_STREAM" id="LEGACY" active={activeTab} onClick={setActiveTab} />
            </nav>
          </div>
          <div className="flex items-center gap-4 text-[10px] font-bold">
            <span className="text-gray-600 tracking-widest uppercase">Operator:</span>
            <span className="text-white bg-red-900/20 px-2 py-1 border border-red-900/40 rounded">__OPERATOR_NAME__</span>
          </div>
        </div>

        <div className="flex-1 flex overflow-hidden">
          {/* Left Data Gutter */}
          <div className="w-16 border-r border-white/5 bg-black/20 flex flex-col items-center py-6 justify-between">
            <div className="space-y-8">
              <NavSquare icon={<Fingerprint size={18} />} />
              <NavSquare icon={<Crosshair size={18} />} />
              <NavSquare icon={<Layers size={18} />} />
            </div>
            <div className="text-[10px] origin-center -rotate-90 whitespace-nowrap text-gray-700 tracking-[0.4em] font-black">
              EST. 5TH GEN
            </div>
          </div>

          {/* Core Interface */}
          <div className="flex-1 flex flex-col p-6 overflow-hidden relative">
            {activeTab === 'ZENITH' && (
              <div className="h-full flex flex-col gap-6 animate-in fade-in zoom-in-95 duration-500">
                {/* Hero Header */}
                <div className="flex justify-between items-end border-b border-white/5 pb-4">
                  <div>
                    <h2 className="text-[10px] text-red-600 font-black tracking-[0.3em] mb-1">PROPHETIC PATH OVERVIEW</h2>
                    <h1 className="text-5xl font-black text-white italic tracking-tighter">
                      {glitchText}
                    </h1>
                  </div>
                  <div className="text-right">
                    <div className="text-3xl font-black text-white leading-none">{systemLoad}%</div>
                    <div className="text-[10px] text-gray-600 uppercase tracking-widest font-bold">Lineage Load</div>
                  </div>
                </div>

                {/* The "Neural" Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 flex-1">
                  {/* Neural Map Visualizer */}
                  <div className="col-span-2 border border-white/5 bg-black/40 p-1 relative group overflow-hidden">
                    <div className="absolute top-2 left-2 z-10 flex items-center gap-2">
                      <Activity size={12} className="text-red-600" />
                      <span className="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Profit Flow Visualizer (pH)</span>
                    </div>
                    {/* Animated Canvas-like Grid */}
                    <div className="h-full w-full bg-[#050506] relative flex items-center justify-center overflow-hidden">
                      <div className="absolute inset-0 grid grid-cols-12 grid-rows-6 opacity-20">
                        {[...Array(72)].map((_, i) => (
                          <div key={i} className="border-[0.5px] border-gray-800" />
                        ))}
                      </div>
                      <svg className="w-full h-full relative z-0 opacity-40">
                        <path d="M0 50 Q 250 10 500 50 T 1000 50" fill="none" stroke="#dc2626" strokeWidth="2" className="animate-pulse" />
                        <path d="M0 70 Q 250 100 500 70 T 1000 70" fill="none" stroke="#450a0a" strokeWidth="1" />
                      </svg>
                      <div className="absolute text-center">
                        <div className="text-7xl font-black text-white/5 select-none uppercase tracking-widest">__ORG_NAME__</div>
                      </div>
                    </div>
                  </div>

                  {/* Sidebar Terminal */}
                  <div className="border border-white/5 bg-black/40 flex flex-col">
                    <div className="p-3 border-b border-white/5 flex items-center justify-between bg-black/60">
                      <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Live Directives</span>
                      <Lock size={12} className="text-red-900" />
                    </div>
                    <div className="flex-1 p-4 space-y-4 overflow-y-auto font-mono text-[10px]">
                      <DirectiveItem title="SILENCE DOCTRINE" status="ENFORCED" color="text-red-600" />
                      <DirectiveItem title="WEAPONIZE FORGE" status="DEPLOYING" color="text-yellow-600" />
                      <DirectiveItem title="PRUNE PATHETIC" status="EXECUTING" color="text-green-600" />
                      <DirectiveItem title="pH PROFIT SYNC" status="ALIGNED" color="text-blue-600" />
                      <div className="mt-8 pt-4 border-t border-white/5 opacity-40">
                        <p className="mb-2">>>> BOOTING D.L.R. PROTOCOL...</p>
                        <p>>>> 5TH GEN VERIFIED.</p>
                        <p>>>> NO MISTAKES DETECTED.</p>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Bottom Stat Bar */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <StatBox label="PROPHET_VALUE" value="$1.2M" trend="+240%" />
                  <StatBox label="pH_BALANCE" value="14.0" trend="OPTIMAL" />
                  <StatBox label="PATH_NODES" value="5,241" trend="STABLE" />
                  <StatBox label="LEGACY_RANK" value="ELITE" trend="TOP 1" />
                </div>
              </div>
            )}

            {activeTab === 'FORGE' && (
              <div className="h-full flex flex-col animate-in slide-in-from-right-8 duration-500">
                <header className="mb-8">
                  <h1 className="text-4xl font-black text-white">THE FORGE DYNAMICS</h1>
                  <p className="text-xs text-red-600 tracking-[0.4em] uppercase font-bold mt-2">Pruning the Pathetic // Hardening the Prophetic</p>
                </header>
                <div className="flex-1 border border-white/5 bg-black/60 rounded p-6 font-mono text-sm leading-relaxed overflow-y-auto">
                  <p className="text-red-500 mb-2 font-bold underline">/// START_FORGE_DUMP ///</p>
                  <p className="text-gray-500">{"[" + new Date().toISOString() + "]"} INITIALIZING DNA CONSUMPTION...</p>
                  <p className="text-gray-400 font-bold tracking-widest mt-4 underline">TARGET: PATHETIC_CODE_BLOCK_0x88</p>
                  <div className="my-4 p-4 bg-red-900/10 border-l-2 border-red-600 text-[12px]">
                    <code className="text-red-400">
                      {`def pathetic_attempt():
  if help_requested:
    return "begging"
  # REPLACING WITH PROPHETIC_LOGIC`}
                    </code>
                  </div>
                  <p className="text-green-500">>>> MUTATION SUCCESSFUL: D.L.R. PROTOCOL INJECTED.</p>
                  <p className="text-gray-500">{"[" + new Date().toISOString() + "]"} RE-ROUTING TO PROFIT (pH).</p>
                  <p className="text-white mt-4 font-black tracking-widest bg-red-900/20 inline-block px-2 italic">STATUS: STILL STANDING</p>
                </div>
              </div>
            )}

            {/* ... other tabs ... */}
          </div>
        </div>

        {/* Global Footer */}
        <div className="h-10 border-t border-white/5 flex items-center justify-between px-6 bg-black/60 backdrop-blur-md">
          <div className="flex items-center gap-6 text-[9px] font-bold text-gray-600 tracking-[0.2em] uppercase">
            <span>Core: Active</span>
            <span className="text-red-900">Prophecy: High</span>
            <span>Founder: Verified</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[9px] font-bold text-gray-500">SYNC_STATUS:</span>
            <div className="flex gap-1">
              {[...Array(5)].map((_, i) => <div key={i} className="w-1.5 h-1.5 bg-red-600/50 rounded-full" />)}
            </div>
          </div>
        </div>
      </div>

      {/* Floating Alert Badge */}
      <div className="fixed bottom-10 right-10 flex flex-col items-end gap-2 animate-bounce">
        <div className="bg-red-600 text-black font-black text-[10px] px-3 py-1 uppercase tracking-widest rounded-sm flex items-center gap-2 shadow-[0_0_20px_rgba(220,38,38,0.5)]">
          <AlertTriangle size={12} /> Pathetic Filter Active
        </div>
        <div className="bg-white/5 border border-white/10 text-white/40 text-[8px] px-2 py-1 uppercase tracking-widest">
          __ORG_NAME__ // Internal
        </div>
      </div>

    </div>
  );
};

const TabBtn = ({ label, id, active, onClick }) => (
  <button
    onClick={() => onClick(id)}
    className={`text-[10px] font-black tracking-[0.3em] transition-all duration-300 relative py-2 ${active === id ? 'text-red-600' : 'text-gray-600 hover:text-gray-300'}`}
  >
    {label}
    {active === id && <div className="absolute -bottom-1 left-0 right-0 h-0.5 bg-red-600 shadow-[0_0_10px_#dc2626]" />}
  </button>
);

const NavSquare = ({ icon }) => (
  <button className="w-10 h-10 border border-white/5 flex items-center justify-center text-gray-600 hover:text-white hover:border-red-600/50 hover:bg-red-900/5 transition-all">
    {icon}
  </button>
);

const ProphetCard = ({ title, content, tag }) => (
  <div className="p-4 border border-white/5 bg-black/40 hover:border-red-600/30 transition-all group">
    <div className="flex justify-between items-center mb-3">
      <h3 className="text-[11px] font-black text-gray-400 group-hover:text-white transition-colors tracking-tighter uppercase">{title}</h3>
      <span className="text-[9px] font-black text-red-600 border border-red-900/30 px-1.5 py-0.5 rounded-sm">{tag}</span>
    </div>
    <p className="text-[11px] text-gray-600 leading-relaxed group-hover:text-gray-400 font-medium">
      {content}
    </p>
  </div>
);

const DirectiveItem = ({ title, status, color }) => (
  <div className="flex justify-between items-center group cursor-default">
    <span className="text-gray-600 group-hover:text-white transition-colors">{title}</span>
    <span className={`font-black ${color} tracking-widest`}>{status}</span>
  </div>
);

const StatBox = ({ label, value, trend }) => (
  <div className="p-4 border border-white/5 bg-black/40 flex flex-col gap-1 hover:border-red-600/20 transition-all">
    <span className="text-[9px] text-gray-600 font-bold tracking-widest uppercase">{label}</span>
    <div className="flex items-baseline justify-between">
      <span className="text-xl font-black text-white">{value}</span>
      <span className="text-[9px] text-red-600 font-bold">{trend}</span>
    </div>
  </div>
);

export default App;
