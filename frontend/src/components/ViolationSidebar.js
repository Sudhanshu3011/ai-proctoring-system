import React, { useState, useEffect, useRef } from 'react';
import { colors, fonts, radius } from '../styles/theme';

const VIOLATION_META = {
  FACE_ABSENT: { label: 'Face Not Detected', cat: 'Camera', col: colors.warningMid },
  MULTI_FACE: { label: 'Multiple Faces Detected', cat: 'Camera', col: colors.dangerMid },
  FACE_MISMATCH: { label: 'Identity Mismatch', cat: 'Identity', col: colors.dangerMid },
  LOOKING_AWAY: { label: 'Looking Away', cat: 'Attention', col: colors.warningMid },
  PHONE_DETECTED: { label: 'Phone Detected', cat: 'Objects', col: colors.dangerMid },
  BOOK_DETECTED: { label: 'Book / Notes Detected', cat: 'Objects', col: colors.dangerMid },
  HEADPHONE_DETECTED: { label: 'Headphones Detected', cat: 'Objects', col: colors.dangerMid },
  SPEECH_BURST: { label: 'Speaking Detected', cat: 'Audio', col: colors.warningMid },
  SUSTAINED_SPEECH: { label: 'Sustained Speech', cat: 'Audio', col: colors.dangerMid },
  MULTI_SPEAKER: { label: 'Multiple Voices', cat: 'Audio', col: colors.dangerMid },
  WHISPER: { label: 'Whispering Detected', cat: 'Audio', col: colors.warningMid },
  TAB_SWITCH: { label: 'Tab Switch', cat: 'Browser', col: colors.dangerMid },
  WINDOW_BLUR: { label: 'Window Focus Lost', cat: 'Browser', col: colors.warningMid },
  FULLSCREEN_EXIT: { label: 'Fullscreen Exited', cat: 'Browser', col: colors.dangerMid },
  COPY_PASTE: { label: 'Copy / Paste', cat: 'Browser', col: colors.dangerMid },
  LIVENESS_NO_BLINK: { label: 'No Blink Detected', cat: 'Liveness', col: colors.warningMid },
  LIVENESS_HEAD_FROZEN: { label: 'No Head Movement', cat: 'Liveness', col: colors.warningMid },
  LIVENESS_STATIC_FRAME: { label: 'Static Image Detected', cat: 'Liveness', col: colors.dangerMid },
};

const SEV_STYLE = {
  WARNING: { bg: colors.warningLight, border: colors.warningBorder },
  HIGH: { bg: colors.dangerLight, border: colors.dangerBorder },
  CRITICAL: { bg: colors.dangerLight, border: colors.dangerBorder },
};

function ViolationRow({ item, index }) {
  const meta = VIOLATION_META[item.vtype] || { label: item.vtype, cat: 'System', col: colors.gray500 };
  const sev = SEV_STYLE[item.severity] || SEV_STYLE.WARNING;
  const ago = Math.floor((Date.now() - item.timestamp) / 1000);

  return (
    <div style={{
      background: sev.bg,
      border: `1px solid ${sev.border}`,
      borderLeft: `3px solid ${meta.col}`,
      borderRadius: radius.md,
      padding: '8px 10px',
      marginBottom: '5px',
    }}>
      {/* Category + time row */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        marginBottom: '2px',
      }}>
        <div style={{
          fontSize: '9px', fontWeight: 700, color: meta.col,
          textTransform: 'uppercase', letterSpacing: '0.05em', fontFamily: fonts.ui,
        }}>
          {meta.cat}
        </div>
        <div style={{ fontSize: '9px', color: colors.gray400, fontFamily: fonts.mono }}>
          {ago < 5 ? 'just now' : `${ago}s ago`}
        </div>
      </div>

      {/* Violation label */}
      <div style={{
        fontSize: '12px', fontWeight: 700, color: colors.gray900, lineHeight: 1.2,
      }}>
        {meta.label}
      </div>

      {/* Message from backend */}
      {item.message && (
        <div style={{
          fontSize: '11px', color: colors.gray600, marginTop: '3px', lineHeight: 1.4,
        }}>
          {item.message}
        </div>
      )}

      {/* Action guidance */}
      {item.action && (
        <div style={{
          fontSize: '10px', color: meta.col, fontWeight: 600, marginTop: '3px',
        }}>
          {item.action}
        </div>
      )}
    </div>
  );
}

export default function ViolationSidebar({ messages }) {
  // items = full chronological log, newest first
  // No deduplication — every violation event is preserved
  const [items, setItems] = useState([]);
  const prevLenRef = useRef(0);

  useEffect(() => {
    if (!messages || messages.length === 0) return;
    // Only process newly added messages (not re-process entire array)
    if (messages.length <= prevLenRef.current) return;

    const newMsgs = messages.slice(prevLenRef.current);
    prevLenRef.current = messages.length;

    const newItems = [];

    for (const msg of newMsgs) {
      if (msg.type === 'VIOLATION_DETAIL') {
        newItems.push({
          id: `vd-${Date.now()}-${Math.random()}`,
          vtype: msg.vtype,
          severity: msg.severity || 'WARNING',
          message: msg.message || '',
          action: msg.action || '',
          confidence: msg.confidence || 1.0,
          timestamp: Date.now(),
        });
      }

      if (msg.type === 'LIVENESS_ISSUE') {
        const map = {
          NO_BLINK: 'LIVENESS_NO_BLINK',
          HEAD_FROZEN: 'LIVENESS_HEAD_FROZEN',
          STATIC_FRAME: 'LIVENESS_STATIC_FRAME',
        };
        newItems.push({
          id: `li-${Date.now()}-${Math.random()}`,
          vtype: map[msg.issue_type] || 'FACE_ABSENT',
          severity: msg.severity || 'WARNING',
          message: msg.message || '',
          action: '',
          confidence: msg.confidence || 1.0,
          timestamp: Date.now(),
        });
      }
    }

    if (newItems.length === 0) return;

    setItems(prev => {
      // Prepend new items (newest first), cap at 50 total entries
      return [...newItems, ...prev].slice(0, 50);
    });
  }, [messages]);

  if (items.length === 0) {
    return (
      <div style={{
        padding: '16px 0', textAlign: 'center',
        fontSize: '12px', color: colors.gray400, lineHeight: 1.6,
      }}>
        No violations recorded
      </div>
    );
  }

  return (
    <div>
      {/* Count header */}
      <div style={{
        fontSize: '10px', color: colors.gray500, marginBottom: '8px',
        display: 'flex', justifyContent: 'space-between',
      }}>
        <span style={{ fontWeight: 600 }}>
          {items.length} violation{items.length !== 1 ? 's' : ''} recorded
        </span>
        {items.length >= 50 && (
          <span style={{ color: colors.dangerMid, fontWeight: 600 }}>
            Showing recent 50
          </span>
        )}
      </div>
      {items.map((item, i) => (
        <ViolationRow key={item.id} item={item} index={i} />
      ))}
    </div>
  );
}