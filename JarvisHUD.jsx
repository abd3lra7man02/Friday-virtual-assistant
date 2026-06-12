import React, { useState, useEffect, useRef } from 'react';
import { Mic, HardDrive, CheckSquare, Calendar } from 'lucide-react';

const JarvisHUD = () => {
  const [isListening, setIsListening] = useState(false);
  const [systemStatus, setSystemStatus] = useState('IDLE');
  const [transcript, setTranscript] = useState([]);
  
  const wsRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioPlayerRef = useRef(new Audio());

  // Initialize WebSocket
  useEffect(() => {
    wsRef.current = new WebSocket('ws://localhost:8000/ws/friday');
    
    wsRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.status === 'processing') {
        setSystemStatus(data.message.toUpperCase());
      } else if (data.status === 'user_input') {
        setTranscript(prev => [...prev, { role: 'user', text: data.text }]);
      } else if (data.status === 'agent_reply') {
        setTranscript(prev => [...prev, { role: 'system', text: data.text }]);
      } else if (data.status === 'audio_ready') {
        // Play the base64 audio received from Edge-TTS
        const audioSrc = `data:audio/mp3;base64,${data.audio}`;
        audioPlayerRef.current.src = audioSrc;
        audioPlayerRef.current.play();
      } else if (data.status === 'idle') {
        setSystemStatus('IDLE');
      }
    };

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];

      mediaRecorderRef.current.ondataavailable = (event) => {
        if (event.data.size > 0) audioChunksRef.current.push(event.data);
      };

      mediaRecorderRef.current.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          wsRef.current.send(audioBlob);
        }
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorderRef.current.start();
      setIsListening(true);
      setSystemStatus('RECORDING');
    } catch (err) {
      console.error("Mic access denied:", err);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isListening) {
      mediaRecorderRef.current.stop();
      setIsListening(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#050B14] text-cyan-400 font-mono p-6 selection:bg-cyan-900">
      {/* Header */}
      <header className="flex justify-between items-center border-b border-cyan-800/50 pb-4 mb-6">
        <div className="flex items-center gap-4 w-1/3">
          <div className={`w-3 h-3 rounded-full ${systemStatus !== 'IDLE' ? 'bg-red-500 animate-pulse' : 'bg-cyan-500'}`}></div>
          <span className="tracking-widest text-sm">{systemStatus}</span>
        </div>
        <h1 className="text-2xl font-bold tracking-[0.5em] text-cyan-300 w-1/3 text-center">F . R . I . D . A . Y</h1>
        <div className="text-right w-1/3">
          <div className="text-xl">12:37:26 AM EEST</div>
          <div className="text-xs text-cyan-600 uppercase">Fri 12 Jun 2026</div>
        </div>
      </header>

      {/* Main Grid Layout */}
      <div className="grid grid-cols-12 gap-6 h-[80vh]">
        
        {/* Left Column: Transcript & Agenda */}
        <div className="col-span-3 space-y-6 flex flex-col">
          <div className="border border-cyan-900/50 bg-[#0A1120] p-4 flex-grow overflow-hidden flex flex-col">
            <h2 className="text-xs text-cyan-600 mb-4 border-b border-cyan-900 pb-2">// LIVE TRANSCRIPT</h2>
            <div className="space-y-4 text-sm overflow-y-auto flex-grow pr-2 scrollbar-thin scrollbar-thumb-cyan-900">
              {transcript.map((msg, idx) => (
                <div key={idx} className={`${msg.role === 'system' ? 'text-cyan-300' : 'text-gray-500'} leading-relaxed`}>
                  {msg.role === 'system' && <span className="mr-2 text-xs opacity-50">✦</span>}
                  {msg.text}
                </div>
              ))}
            </div>
          </div>

          <div className="border border-cyan-900/50 bg-[#0A1120] p-4 h-48">
            <h2 className="text-xs text-cyan-600 mb-4 border-b border-cyan-900 pb-2 flex items-center gap-2"><Calendar size={14}/> LOCAL AGENDA</h2>
            <ul className="space-y-2 text-sm">
              <li className="flex justify-between"><span className="text-cyan-500">10:00</span> <span>Signals & Systems Lab</span></li>
              <li className="flex justify-between"><span className="text-cyan-500">14:30</span> <span>Hack The Box Practice</span></li>
            </ul>
          </div>
        </div>

        {/* Center Column: The Interactive Orb */}
        <div className="col-span-6 flex flex-col items-center justify-center relative">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-cyan-900/10 via-[#050B14] to-[#050B14] -z-10"></div>
          
          {/* Glowing Orb */}
          <div className={`relative w-64 h-64 rounded-full flex items-center justify-center transition-all duration-500 ${isListening ? 'scale-110' : ''}`}>
            <div className={`absolute inset-0 rounded-full border-4 border-cyan-500/30 ${systemStatus !== 'IDLE' ? 'animate-ping opacity-20' : ''}`}></div>
            <div className="absolute inset-2 rounded-full border border-cyan-400/20 border-dashed animate-[spin_10s_linear_infinite]"></div>
            <div className={`w-32 h-32 rounded-full shadow-[0_0_80px_30px_rgba(34,211,238,0.4)] transition-colors duration-300 ${isListening ? 'bg-red-500/80 shadow-red-500/40' : 'bg-cyan-400'}`}></div>
          </div>

          <div className="mt-12 text-center h-16">
            <div className="text-xl tracking-widest text-cyan-200">{systemStatus}</div>
            <div className="text-sm text-cyan-600 mt-2">Kafr El-Shaikh, Egypt</div>
          </div>

          {/* Push to Talk Button */}
          <button 
            onMouseDown={startRecording}
            onMouseUp={stopRecording}
            onMouseLeave={stopRecording}
            className="mt-4 p-4 rounded-full bg-cyan-950 border border-cyan-800 hover:bg-cyan-900 transition-colors cursor-pointer z-10"
          >
            <Mic size={28} className={isListening ? 'text-red-400' : 'text-cyan-500'} />
          </button>
          <div className="text-xs text-cyan-800 mt-4 uppercase">Hold to transmit</div>
        </div>

        {/* Right Column: System & Tasks */}
        <div className="col-span-3 space-y-6">
          <div className="border border-cyan-900/50 bg-[#0A1120] p-4">
            <h2 className="text-xs text-cyan-600 mb-4 border-b border-cyan-900 pb-2 flex items-center gap-2"><HardDrive size={14}/> // SYSTEM DIAGNOSTICS</h2>
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
                <div className="text-green-400">CONNECTED</div>
              </div>
            </div>
          </div>

          <div className="border border-cyan-900/50 bg-[#0A1120] p-4 h-64">
            <h2 className="text-xs text-cyan-600 mb-4 border-b border-cyan-900 pb-2 flex items-center gap-2"><CheckSquare size={14}/> // ACTIVE PROJECTS</h2>
            <ul className="space-y-3 text-sm">
              <li className="flex items-center gap-3">
                <div className="w-2 h-2 border border-red-500"></div> 
                <div>
                  <div className="text-red-400">IEEE Paper Draft</div>
                  <div className="text-[10px] text-gray-600">Edge Networks</div>
                </div>
              </li>
              <li className="flex items-center gap-3">
                <div className="w-2 h-2 border border-cyan-600"></div> 
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