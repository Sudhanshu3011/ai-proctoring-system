// src/components/RiskMeter.js
import React from 'react';

export default function RiskMeter({ score, level }) {
  const colors = {
    SAFE:'#10b981', WARNING:'#f59e0b', HIGH:'#ef4444', CRITICAL:'#dc2626'
  };
  const col   = colors[level] || '#10b981';
  const pct   = Math.min(100, score);
  // Arc from 135° to 405° (270° sweep)
  const r     = 52;
  const cx    = 70; const cy = 70;
  const toRad = d => (d * Math.PI) / 180;
  const arc   = (pct) => {
    const angle = 135 + (pct / 100) * 270;
    const rad   = toRad(angle);
    return {
      x: cx + r * Math.cos(rad),
      y: cy + r * Math.sin(rad),
    };
  };
  const start   = arc(0);
  const end     = arc(pct);
  const large   = pct > 50 ? 1 : 0;
  const startR  = toRad(135);
  const endFull = toRad(405);
  const sx = cx + r * Math.cos(startR);
  const sy = cy + r * Math.sin(startR);
  const ex = cx + r * Math.cos(endFull);
  const ey = cy + r * Math.sin(endFull);

  return (
    <div style={{ display:'flex', alignItems:'center', gap:'14px' }}>
      <svg width="140" height="90" viewBox="0 0 140 90">
        {/* Track */}
        <path
          d={`M ${sx} ${sy} A ${r} ${r} 0 1 1 ${ex} ${ey}`}
          fill="none" stroke="#1e2d45" strokeWidth="10"
          strokeLinecap="round"
        />
        {/* Fill */}
        {pct > 0 && (
          <path
            d={`M ${start.x} ${start.y} A ${r} ${r} 0 ${large} 1 ${end.x} ${end.y}`}
            fill="none" stroke={col} strokeWidth="10"
            strokeLinecap="round"
            style={{ transition:'all 0.6s ease' }}
          />
        )}
        {/* Score text */}
        <text x={cx} y={cy + 6} textAnchor="middle"
          style={{ fill:'white', fontSize:'20px', fontFamily:'Syne', fontWeight:800 }}>
          {score.toFixed(0)}
        </text>
        <text x={cx} y={cy + 22} textAnchor="middle"
          style={{ fill:'#64748b', fontSize:'9px', fontFamily:'DM Mono' }}>
          / 100
        </text>
        {/* Min/Max labels */}
        <text x="14" y="88" style={{ fill:'#64748b', fontSize:'9px', fontFamily:'DM Mono' }}>0</text>
        <text x="118" y="88" style={{ fill:'#64748b', fontSize:'9px', fontFamily:'DM Mono' }}>100</text>
      </svg>
      <div>
        <div style={{
          fontFamily:'Syne', fontWeight:700, fontSize:'14px',
          color: col, marginBottom:'4px',
        }}>
          {level}
        </div>
        <div style={{ fontSize:'10px', color:'var(--muted)', lineHeight:1.6 }}>
          {level === 'SAFE'     && 'No suspicious activity'}
          {level === 'WARNING'  && 'Some irregularities noted'}
          {level === 'HIGH'     && 'High risk — admin alerted'}
          {level === 'CRITICAL' && 'Critical — may terminate'}
        </div>
      </div>
    </div>
  );
}