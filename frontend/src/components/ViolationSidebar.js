// src/components/ViolationSidebar.js
// Violation log shown BELOW the webcam in the right sidebar — not over the video

import React, { useState, useEffect, useRef } from 'react';

const VIOLATION_META = {
  FACE_ABSENT: { label: 'Face Not Detected', cat: 'Camera', col: '#d97706' },
  MULTI_FACE: { label: 'Multiple Faces Detected', cat: 'Camera', col: '#dc2626' },
  FACE_MISMATCH: { label: 'Identity Mismatch', cat: 'Identity', col: '#dc2626' },
  LOOKING_AWAY: { label: 'Looking Away', cat: 'Attention', col: '#d97706' },
  PHONE_DETECTED: { label: 'Phone Detected', cat: 'Objects', col: '#dc2626' },
  BOOK_DETECTED: { label: 'Book / Notes Detected', cat: 'Objects', col: '#dc2626' },
  HEADPHONE_DETECTED: { label: 'Headphones Detected', cat: 'Objects', col: '#dc2626' },
  SPEECH_BURST: { label: 'Speaking Detected', cat: 'Audio', col: '#d97706' },
  SUSTAINED_SPEECH: { label: 'Sustained Speech', cat: 'Audio', col: '#dc2626' },
  MULTI_SPEAKER: { label: 'Multiple Voices', cat: 'Audio', col: '#dc2626' },
  WHISPER: { label: 'Whispering Detected', cat: 'Audio', col: '#d97706' },
  TAB_SWITCH: { label: 'Tab Switch', cat: 'Browser', col: '#dc2626' },
  WINDOW_BLUR: { label: 'Window Focus Lost', cat: 'Browser', col: '#d97706' },
  FULLSCREEN_EXIT: { label: 'Fullscreen Exited', cat: 'Browser', col: '#dc2626' },
  COPY_PASTE: { label: 'Copy / Paste', cat: 'Browser', col: '#dc2626' },
  LIVENESS_NO_BLINK: { label: 'No Blink Detected', cat: 'Liveness', col: '#d97706' },
  LIVENESS_HEAD_FROZEN: { label: 'No Head Movement', cat: 'Liveness', col: '#d97706' },
  LIVENESS_STATIC_FRAME: { label: 'Static Image Detected', cat: 'Liveness', col: '#dc2626' },
};

const SEV = {
  WARNING: { bg: '#fffbeb', bdr: '#fcd34d', txt: '#92400e' },
  HIGH: { bg: '#fef2f2', bdr: '#fca5a5', txt: '#991b1b' },
  CRITICAL: { bg: '#fef2f2', bdr: '#f87171', txt: '#7f1d1d' },
};

function ViolationRow({ item }) {
  const meta = VIOLATION_META[item.vtype] || { label: item.vtype, cat: 'System', col: '#374151' };
  const sev = SEV[item.severity] || SEV.WARNING;
  const ago = Math.floor((Date.now() - item.timestamp) / 1000);

  return (
    <div style={{
      background: sev.bg,
      border: `1px solid ${sev.bdr}`,
      borderLeft: `3px solid ${meta.col}`,
      borderRadius: '6px',
      padding: '8px 10px',
      animation: 'fadeIn 0.2s ease',
    }}>
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        alignItems: 'flex-start', gap: '6px',
      }}>
        <div style={{ flex: 1 }}>
          {/* Category */}
          <div style={{
            fontSize: '9px', fontWeight: 700, color: meta.col,
            textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '2px',
          }}>
            {meta.cat}
          </div>
          {/* Label */}
          <div style={{ fontSize: '12px', fontWeight: 700, color: '#111', lineHeight: 1.2 }}>
            {meta.label}
          </div>
          {/* Message */}
          {item.message && (
            <div style={{ fontSize: '11px', color: '#374151', marginTop: '3px', lineHeight: 1.4 }}>
              {item.message}
            </div>
          )}
          {/* Action */}
          {item.action && (
            <div style={{
              fontSize: '10px', color: meta.col, fontWeight: 600, marginTop: '3px',
            }}>
              {item.action}
            </div>
          )}
        </div>
        {/* Time */}
        <div style={{ fontSize: '9px', color: '#9ca3af', flexShrink: 0 }}>
          {ago < 5 ? 'now' : `${ago}s`}
        </div>
      </div>
    </div>
  );
}

export default function ViolationSidebar({ messages }) {
  const [items, setItems] = useState([]);
  const timers = useRef({});
  const listRef = useRef(null);

  useEffect(() => {
    if (!messages || messages.length === 0) return;
    const last = messages[messages.length - 1];
    if (!last) return;

    let item = null;

    if (last.type === 'VIOLATION_DETAIL') {
      item = {
        id: `${last.vtype}-${Date.now()}`,
        vtype: last.vtype,
        severity: last.severity || 'WARNING',
        message: last.message || '',
        action: last.action || '',
        confidence: last.confidence || 1.0,
        timestamp: Date.now(),
      };
    }

    if (last.type === 'LIVENESS_ISSUE') {
      const map = {
        NO_BLINK: 'LIVENESS_NO_BLINK',
        HEAD_FROZEN: 'LIVENESS_HEAD_FROZEN',
        STATIC_FRAME: 'LIVENESS_STATIC_FRAME',
      };
      item = {
        id: `liveness-${last.issue_type}-${Date.now()}`,
        vtype: map[last.issue_type] || 'FACE_ABSENT',
        severity: last.severity || 'WARNING',
        message: last.message || '',
        action: '',
        confidence: last.confidence || 1.0,
        timestamp: Date.now(),
      };
    }

    if (!item) return;

    // Replace same vtype if already present, then prepend (newest first)
    setItems(prev => {
      const filtered = prev.filter(p => p.vtype !== item.vtype);
      return [item, ...filtered].slice(0, 8);  // max 8 entries
    });

    // Auto-remove after 30 seconds
    if (timers.current[item.vtype]) clearTimeout(timers.current[item.vtype]);
    timers.current[item.vtype] = setTimeout(() => {
      setItems(prev => prev.filter(p => p.id !== item.id));
    }, 30000);

    // Scroll to top when new item added
    if (listRef.current) listRef.current.scrollTop = 0;

  }, [messages]);

  if (items.length === 0) {
    return (
      <div style={{ padding: '12px', textAlign: 'center' }}>
        <div style={{
          fontSize: '11px', color: '#9ca3af', lineHeight: 1.6,
        }}>
          No violations recorded
        </div>
      </div>
    );
  }

  return (
    <div ref={listRef} style={{
      display: 'flex', flexDirection: 'column', gap: '6px',
      overflowY: 'auto', maxHeight: '100%', padding: '2px',
    }}>
      <style>{`@keyframes fadeIn{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:translateY(0)}}`}</style>
      {items.map(item => (
        <ViolationRow key={item.id} item={item} />
      ))}
    </div>
  );
}