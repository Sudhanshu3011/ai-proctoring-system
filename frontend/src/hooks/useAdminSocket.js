// src/hooks/useAdminSocket.js
// WebSocket hook for admin live monitoring dashboard

import { useEffect, useRef, useState, useCallback } from 'react';

const WS_BASE = 'ws://localhost:8000';

export function useAdminSocket() {
  const ws              = useRef(null);
  const reconnectTimer  = useRef(null);

  const [connected,  setConnected]  = useState(false);
  const [sessions,   setSessions]   = useState([]);
  const [summary,    setSummary]    = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);

  const connect = useCallback(() => {
    const token = localStorage.getItem('token');
    if (!token) return;

    const socket = new WebSocket(
      `${WS_BASE}/ws/admin/live?token=${token}`
    );
    ws.current = socket;

    socket.onopen = () => {
      setConnected(true);
      console.log('[AdminWS] Connected');
      // Clear any pending reconnect
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };

    socket.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === 'SESSION_UPDATE') {
          setSessions(msg.sessions || []);
          setSummary(msg.summary   || null);
          setLastUpdate(new Date());
        }
      } catch (e) {
        console.warn('[AdminWS] Parse error', e);
      }
    };

    socket.onclose = (evt) => {
      setConnected(false);
      console.log('[AdminWS] Disconnected — reconnecting in 5s');
      // Auto-reconnect unless intentionally closed
      if (evt.code !== 1000 && evt.code !== 4001 && evt.code !== 4003) {
        reconnectTimer.current = setTimeout(connect, 5000);
      }
    };

    socket.onerror = (err) => {
      console.error('[AdminWS] Error', err);
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (ws.current) ws.current.close(1000);
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };
  }, [connect]);

  const terminateSession = useCallback((sessionId) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({
        type: 'TERMINATE', session_id: sessionId,
      }));
    }
  }, []);

  return {
    connected, sessions, summary, lastUpdate,
    terminateSession,
  };
}