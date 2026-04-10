// src/components/ViolationAlert.js — light theme
import React from 'react';

const CONFIG = {
  WARNING: { bg: 'var(--warn-lt)', border: 'var(--warn-bd)', color: 'var(--warn)' },
  HIGH: { bg: 'var(--high-lt)', border: 'var(--high-bd)', color: 'var(--high)' },
  CRITICAL: { bg: 'var(--high-lt)', border: 'var(--high-bd)', color: 'var(--critical)' },
  SAFE: { bg: 'var(--safe-lt)', border: 'var(--safe-bd)', color: 'var(--safe)' },
};
export default function ViolationAlert({ alert }) {
  const c = CONFIG[alert.level] || CONFIG.WARNING;
  return (
    <div style={{
      background: c.bg, border: `1px solid ${c.border}`,
      borderLeft: `3px solid ${c.color}`,
      borderRadius: '6px', padding: '8px 12px',
      animation: 'slideIn 0.2s ease',
    }}>
      <div style={{ fontSize: '11px', color: 'var(--text2)', lineHeight: 1.5 }}>
        {alert.message}
      </div>
    </div>
  );
}