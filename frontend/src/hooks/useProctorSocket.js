// src/hooks/useProctorSocket.js
// Manages WebSocket connection to /ws/monitor/{session_id}

import { useEffect, useRef, useState, useCallback } from 'react';

const WS_BASE = 'ws://localhost:8000';

export function useProctorSocket(sessionId) {
  const ws          = useRef(null);
  const [connected, setConnected]   = useState(false);
  const [riskData,  setRiskData]    = useState(null);
  const [alerts,    setAlerts]      = useState([]);
  const [terminated,setTerminated]  = useState(false);

  useEffect(() => {
    if (!sessionId) return;

    const socket = new WebSocket(`${WS_BASE}/ws/monitor/${sessionId}`);
    ws.current = socket;

    socket.onopen = () => {
      setConnected(true);
      console.log('[WS] Connected to proctor stream');
    };

    socket.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);

        if (msg.type === 'RISK_UPDATE') {
          setRiskData(msg);
        }
        if (msg.type === 'ALERT') {
          setAlerts(prev => [...prev.slice(-4), {
            id: Date.now(), message: msg.message, level: msg.level
          }]);
        }
        if (msg.type === 'TERMINATE') {
          setTerminated(true);
        }
      } catch (e) {
        console.warn('[WS] Parse error', e);
      }
    };

    socket.onclose = () => {
      setConnected(false);
      console.log('[WS] Disconnected');
    };

    return () => socket.close();
  }, [sessionId]);

  const sendFrame = useCallback((base64Frame) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: 'FRAME', data: base64Frame }));
    }
  }, []);

  const sendBrowserEvent = useCallback((event) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: 'BROWSER', data: { event } }));
    }
  }, []);

  const sendAudio = useCallback((violation, prob) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({
        type: 'AUDIO', data: { violation, prob }
      }));
    }
  }, []);

  return {
    connected, riskData, alerts, terminated,
    sendFrame, sendBrowserEvent, sendAudio,
  };
}