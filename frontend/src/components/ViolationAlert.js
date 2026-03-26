// src/components/ViolationAlert.js
import React from 'react';

const CONFIG = {
  WARNING : { icon:'⚠',  bg:'#1c1003', border:'#78350f', color:'#f59e0b' },
  HIGH    : { icon:'🔴', bg:'#1a0505', border:'#7f1d1d', color:'#ef4444' },
  CRITICAL: { icon:'🚨', bg:'#1a0505', border:'#991b1b', color:'#dc2626' },
  SAFE    : { icon:'ℹ',  bg:'#030f0a', border:'#14532d', color:'#10b981' },
};

export default function ViolationAlert({ alert }) {
  const c = CONFIG[alert.level] || CONFIG.WARNING;
  return (
    <div style={{
      background: c.bg,
      border: `1px solid ${c.border}`,
      borderRadius: '6px',
      padding: '8px 10px',
      animation: 'slideIn 0.2s ease',
    }}>
      <div style={{ display:'flex', alignItems:'flex-start', gap:'6px' }}>
        <span style={{ fontSize:'12px', flexShrink:0 }}>{c.icon}</span>
        <span style={{ fontSize:'11px', color: c.color, lineHeight:1.5 }}>
          {alert.message}
        </span>
      </div>
    </div>
  );
}