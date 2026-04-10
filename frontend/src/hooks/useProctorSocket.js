// src/hooks/useProctorSocket.js — UPDATED
// Handles VIOLATION_DETAIL and LIVENESS_ISSUE message types

import { useEffect, useRef, useState, useCallback } from 'react';

const WS_BASE = 'ws://localhost:8000';

export function useProctorSocket(sessionId) {
  const ws = useRef(null);
  const [connected, setConnected] = useState(false);
  const [riskData, setRiskData] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [wsMessages, setWsMessages] = useState([]);  // raw messages for ViolationPanel
  const [terminated, setTerminated] = useState(false);


  useEffect(() => {
    if (!sessionId) return;

    const socket = new WebSocket(`${WS_BASE}/ws/monitor/${sessionId}`);
    ws.current = socket;

    socket.onopen = () => { setConnected(true); console.log('[WS] Connected'); };
    socket.onclose = () => { setConnected(false); console.log('[WS] Disconnected'); };

    socket.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);

        if (msg.type === 'RISK_UPDATE') {
          setRiskData(msg);
        }

        // Legacy ALERT → still push to alerts for backward compat
        if (msg.type === 'ALERT') {
          setAlerts(prev => [...prev.slice(-9), {
            id: Date.now(),
            message: msg.message,
            level: msg.level,
          }]);
        }

        // New specific violation messages → send to ViolationPanel
        if (msg.type === 'VIOLATION_DETAIL' || msg.type === 'LIVENESS_ISSUE') {
          setWsMessages(prev => [...prev.slice(-19), msg]);
        }

        if (msg.type === 'TERMINATE') {
          setTerminated(true);
        }

      } catch (e) {
        console.warn('[WS] Parse error', e);
      }
    };

    return () => socket.close();
  }, [sessionId]);

  const sendFrame = useCallback((b64) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: 'FRAME', data: b64 }));
    }
  }, []);

  const sendBrowserEvent = useCallback((event) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: 'BROWSER', data: { event } }));
    }
  }, []);

  const sendAudio = useCallback((violation, prob) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type: 'AUDIO', data: { violation, prob } }));
    }
  }, []);

  return {
    connected, riskData, alerts, wsMessages, terminated,
    sendFrame, sendBrowserEvent, sendAudio,
  };
}