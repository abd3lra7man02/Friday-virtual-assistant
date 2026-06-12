import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Mic, HardDrive, CheckSquare, Calendar } from 'lucide-react';

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const WS_PROTOCOL = import.meta.env.VITE_WS_PROTOCOL || 'ws';
const WS_HOST = import.meta.env.VITE_WS_HOST || 'localhost:8000';

// Get token from URL query param or localStorage
const getAuthToken = () => {
  const params = new URLSearchParams(window.location.search);
  const token = params.get('token') || localStorage.getItem('friday_token');
  if (token) {
    localStorage.setItem('friday_token', token);
  }
  return token;
};

const WS_URL = `${WS_PROTOCOL}://${WS_HOST}/ws/friday?token=${encodeURIComponent(getAuthToken() || '')}`;

// Cap the in-memory transcript so long sessions don't degrade rendering
const MAX_TRANSCRIPT = 100;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
const JarvisHUD = () => {
  const [isListening, setIsListening]   = useState(false);
  const [systemStatus, setSystemStatus] = useState('IDLE');
  const [transcript, setTranscript]     = useState([]);
  const [wsConnected, setWsConnected]   = useState(false);
  const [location, setLocation]         = useState('Loading...');
  const [currentTime, setCurrentTime]   = useState(new Date());

  const wsRef               = useRef(null);
  const mediaRecorderRef    = useRef(null);
  const audioChunksRef      = useRef([]);
  const audioPlayerRef      = useRef(null);
  const reconnectTimerRef   = useRef(null);
  const intentionalCloseRef = useRef(false);

  // ── Fetch system info (location, etc) ──────────────────────────────────
  useEffect(() => {
    const fetchSystemInfo = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/health`);
        if (response.ok) {
          const data = await response.json();
          // TODO: Backend should return location info
          // For now, using default from config
        }
      } catch (err) {
        console.warn('Failed to fetch system info:', err);
      }
    };

    fetchSystemInfo();
  }, []);

  // ── Live clock ────────────────────────────────────────────────────────────
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const formatTime = (date) =>
    date.toLocaleTimeString('en-US', {
      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true,
    });

  const formatDate = (date) =>
    date.toLocaleDateString('en-US', {
      weekday: 'short', day: '2-digit', month: 'short', year: 'numeric',
    }).toUpperCase();

  // ── WebSocket with auto-reconnect and authentication ────────────────────
  const connectWebSocket = useCallback(() => {
    if (
      wsRef.current &&
      wsRef.current.readyState !== WebSocket.CLOSED &&
      wsRef.current.readyState !== WebSocket.CLOSING
    ) {
      return;
    }

    // Validate token before connecting
    const token = getAuthToken();
    if (!token) {
      console.error('[Friday] No authentication token available');
      setSystemStatus('AUTH ERROR');
      return;
    }

    const urlWithToken = `${WS_PROTOCOL}://${WS_HOST}/ws/friday?token=${encodeURIComponent(token)}`;
    console.log('[Friday] Connecting to', urlWithToken.split('?')[0] + '?token=***');
    
    const ws = new WebSocket(urlWithToken);
    wsRef.current = ws;

    ws.onopen = () => {
      console.log('[Friday] WebSocket connected');
      setWsConnected(true);
      setSystemStatus('IDLE');
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
    };

    ws.onerror = (err) => {
      console.error('[Friday] WebSocket error:', err);
      setWsConnected(false);
      setSystemStatus('CONNECTION ERROR');
    };

    ws.onclose = (event) => {
      console.log(`[Friday] WebSocket closed (code: ${event.code})`);
      setWsConnected(false);
      setSystemStatus('DISCONNECTED');

      if (!intentionalCloseRef.current) {
        reconnectTimerRef.current = setTimeout(connectWebSocket, 3000);
      }
    };

    ws.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch (parseErr) {
        console.error('[Friday] Malformed WS message:', parseErr);
        return;
      }

      switch (data.status) {
        case 'processing':
          setSystemStatus((data.message || 'PROCESSING').toUpperCase());
          break;

        case 'user_input':
          setTranscript(prev => {
            const next = [...prev, { role: 'user', text: data.text }];
            return next.slice(-MAX_TRANSCRIPT);
          });
          break;

        case 'agent_reply':
          setTranscript(prev => {
            const next = [...prev, { role: 'system', text: data.text }];
            return next.slice(-MAX_TRANSCRIPT);
          });
          break;

        case 'audio_ready': {
          if (!audioPlayerRef.current) {
            audioPlayerRef.current = new Audio();
          }
          audioPlayerRef.current.src = `data:audio/mp3;base64,${data.audio}`;
          audioPlayerRef.current.play().catch(err => {
            console.error('[Friday] Audio playback error:', err);
          });
          break;
        }

        case 'idle':
          setSystemStatus('IDLE');
          break;

        case 'error':
          console.error('[Friday] Server error:', data.message);
          setSystemStatus('ERROR');
          setTimeout(() => setSystemStatus('IDLE'), 2000);
          break;

        default:
          break;
      }
    };
  }, []);

  useEffect(() => {
    intentionalCloseRef.current = false;
    connectWebSocket();

    return () => {
      intentionalCloseRef.current = true;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connectWebSocket]);

  // ── Recording ─────────────────────────────────────────────────────────────
  const startRecording = async () => {
    if (!wsConnected || isListening) return;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current   = [];

      mediaRecorderRef.current.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      mediaRecorderRef.current.onstop = () => {
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        
        // Validate blob size
        if (blob.size > 50 * 1024 * 1024) {
          console.error('[Friday] Audio blob too large:', blob.size);
          setSystemStatus('FILE TOO LARGE');
          setTimeout(() => setSystemStatus('IDLE'), 2000);
        } else if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(blob);
        }
        
        stream.getTracks().forEach(t => t.stop());
      };

      mediaRecorderRef.current.start();
      setIsListening(true);
      setSystemStatus('RECORDING');
    } catch (err) {
      console.error('[Friday] Mic access denied:', err);
      setSystemStatus('MIC ERROR');
      setTimeout(() => setSystemStatus('IDLE'), 2000);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isListening) {
      mediaRecorderRef.current.stop();
      setIsListening(false);
    }
  };

  const handlePressStart = (e) => {
    e.preventDefault();
    startRecording();
  };

  const handlePressEnd = (e) => {
    e.preventDefault();
    stopRecording();
  };

  // ── Status indicator helpers ───────────────────────────────────────────────
  const orbColor = !wsConnected
    ? 'bg-yellow-500/60 shadow-yellow-500/30'
    : isListening
    ? 'bg-red-500/80 shadow-red-500/40'
    : 'bg-cyan-400 shadow-[0_0_80px_30px_rgba(34,211,238,0.4)]';

  const statusDot = !wsConnected
    ? 'bg-yellow-500 animate-pulse'
    : systemStatus !== 'IDLE'
    ? 'bg-red-500 animate-pulse'
    : 'bg-cyan-500';

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-[#050B14] text-cyan-400 font-mono p-6 selection:bg-cyan-900">

      {/* ── Header ── */}
      <header className="flex justify-between items-center border-b border-cyan-800/50 pb-4 mb-6">
        <div className="flex items-center gap-4 w-1/3">
          <div className={`w-3 h-3 rounded-full ${statusDot}`}></div>
          <span className="tracking-widest text-sm">
            {wsConnected ? systemStatus : 'CONNECTING…'}
          </span>
        </div>

        <h1 className="text-2xl font-bold tracking-[0.5em] text-cyan-300 w-1/3 text-center">
          F . R . I . D . A . Y
        </h1>

        {/* Live clock */}
        <div className="text-right w-1/3">
          <div className="text-xl">{formatTime(currentTime)}</div>
          <div className="text-xs text-cyan-600">{formatDate(currentTime)}</div>
        </div>
      </header>

      {/* ── Main Grid ── */}
      <div className="grid grid-cols-12 gap-6 h-[80vh]">

        {/* Left: Transcript & Agenda */}
        <div className="col-span-3 space-y-6 flex flex-col">
          <div className="border border-cyan-900/50 bg-[#0A1120] p-4 flex-grow overflow-hidden flex flex-col">
            <h2 className="text-xs text-cyan-600 mb-4 border-b border-cyan-900 pb-2">
              // LIVE TRANSCRIPT
            </h2>
            <div className="space-y-4 text-sm overflow-y-auto flex-grow pr-2 scrollbar-thin scrollbar-thumb-cyan-900">
              {transcript.length === 0 && (
                <div className="text-cyan-800 text-xs italic">Awaiting transmission…</div>
              )}
              {transcript.map((msg, idx) => (
                <div
                  key={idx}
                  className={`${
                    msg.role === 'system' ? 'text-cyan-300' : 'text-gray-500'
                  } leading-relaxed`}
                >
                  {msg.role === 'system' && (
                    <span className="mr-2 text-xs opacity-50">✦</span>
                  )}
                  {msg.text}
                </div>
              ))}
            </div>
          </div>

          <div className="border border-cyan-900/50 bg-[#0A1120] p-4 h-48">
            <h2 className="text-xs text-cyan-600 mb-4 border-b border-cyan-900 pb-2 flex items-center gap-2">
              <Calendar size={14} /> LOCAL AGENDA
            </h2>
            <ul className="space-y-2 text-sm">
              <li className="flex justify-between">
                <span className="text-cyan-500">10:00</span>
                <span>Signals &amp; Systems Lab</span>
              </li>
              <li className="flex justify-between">
                <span className="text-cyan-500">14:30</span>
                <span>Hack The Box Practice</span>
              </li>
            </ul>
          </div>
        </div>

        {/* Centre: Orb */}
        <div className="col-span-6 flex flex-col items-center justify-center relative">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-cyan-900/10 via-[#050B14] to-[#050B14] -z-10"></div>

          <div
            className={`relative w-64 h-64 rounded-full flex items-center justify-center transition-all duration-500 ${
              isListening ? 'scale-110' : ''
            }`}
          >
            <div
              className={`absolute inset-0 rounded-full border-4 border-cyan-500/30 ${
                wsConnected && systemStatus !== 'IDLE' ? 'animate-ping opacity-20' : ''
              }`}
            ></div>
            <div className="absolute inset-2 rounded-full border border-cyan-400/20 border-dashed animate-[spin_10s_linear_infinite]"></div>
            <div className={`w-32 h-32 rounded-full transition-colors duration-300 ${orbColor}`}></div>
          </div>

          <div className="mt-12 text-center h-16">
            <div className="text-xl tracking-widest text-cyan-200">
              {wsConnected ? systemStatus : 'CONNECTING…'}
            </div>
            <div className="text-sm text-cyan-600 mt-2">{location}</div>
          </div>

          {/* Push-to-Talk */}
          <button
            onMouseDown={handlePressStart}
            onMouseUp={handlePressEnd}
            onMouseLeave={handlePressEnd}
            onTouchStart={handlePressStart}
            onTouchEnd={handlePressEnd}
            disabled={!wsConnected}
            aria-label="Hold to record"
            className={`mt-4 p-4 rounded-full border transition-colors z-10 ${
              !wsConnected
                ? 'bg-gray-900 border-gray-700 cursor-not-allowed opacity-50'
                : 'bg-cyan-950 border-cyan-800 hover:bg-cyan-900 cursor-pointer'
            }`}
          >
            <Mic
              size={28}
              className={
                !wsConnected ? 'text-gray-600' : isListening ? 'text-red-400' : 'text-cyan-500'
              }
            />
          </button>
          <div className="text-xs text-cyan-800 mt-4 uppercase">
            {wsConnected ? 'Hold to transmit' : 'Connecting to server…'}
          </div>
        </div>

        {/* Right: Diagnostics & Projects */}
        <div className="col-span-3 space-y-6">
          <div className="border border-cyan-900/50 bg-[#0A1120] p-4">
            <h2 className="text-xs text-cyan-600 mb-4 border-b border-cyan-900 pb-2 flex items-center gap-2">
              <HardDrive size={14} /> // SYSTEM DIAGNOSTICS
            </h2>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-cyan-600 text-xs">MODEL</div>
                <div className="text-lg">LLAMA-3</div>
              </div>
              <div>
                <div className="text-cyan-600 text-xs">MEMORY</div>
                <div className="text-lg">CHROMA DB</div>
              </div>
              <div>
                <div className="text-cyan-600 text-xs">OLLAMA API</div>
                <div className="text-green-400">ONLINE</div>
              </div>
              <div>
                <div className="text-cyan-600 text-xs">FASTAPI</div>
                <div className={wsConnected ? 'text-green-400' : 'text-red-400'}>
                  {wsConnected ? 'CONNECTED' : 'OFFLINE'}
                </div>
              </div>
            </div>
          </div>

          <div className="border border-cyan-900/50 bg-[#0A1120] p-4 h-64">
            <h2 className="text-xs text-cyan-600 mb-4 border-b border-cyan-900 pb-2 flex items-center gap-2">
              <CheckSquare size={14} /> // ACTIVE PROJECTS
            </h2>
            <ul className="space-y-3 text-sm">
              <li className="flex items-center gap-3">
                <div className="w-2 h-2 border border-red-500 flex-shrink-0"></div>
                <div>
                  <div className="text-red-400">IEEE Paper Draft</div>
                  <div className="text-[10px] text-gray-600">Edge Networks</div>
                </div>
              </li>
              <li className="flex items-center gap-3">
                <div className="w-2 h-2 border border-cyan-600 flex-shrink-0"></div>
                <div>
                  <div className="text-cyan-300">ESP32 Facial Recog</div>
                  <div className="text-[10px] text-gray-600">Camera module setup</div>
                </div>
              </li>
            </ul>
          </div>
        </div>

      </div>
    </div>
  );
};

export default JarvisHUD;