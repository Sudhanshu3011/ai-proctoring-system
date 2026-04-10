// src/components/RiskMeter.js
import { colors, fonts } from '../styles/theme';
import { statusConfig } from '../styles/theme';

// ── Styles ────────────────────────────────────────────────────────
const S = {
  root: {
    display: 'flex',
    alignItems: 'center',
    gap: '14px',
  },
  label: {
    fontSize: '10px',
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginBottom: '3px',
    fontFamily: fonts.ui,
  },
  desc: {
    fontSize: '11px',
    color: colors.gray500,
    lineHeight: 1.4,
    fontFamily: fonts.ui,
  },
};

// Fixed arc using stroke-dasharray — no distortion at 50%
export default function RiskMeter({ score, level }) {
  const cfg = statusConfig[level] || statusConfig.SAFE;
  const pct = Math.min(100, Math.max(0, score || 0));
  const r = 50;
  const cx = 68;
  const cy = 70;
  const circumf = 2 * Math.PI * r;
  const arcLength = circumf * (270 / 360);
  const fillLen = arcLength * (pct / 100);
  const startDeg = 135;

  const DESCS = {
    SAFE: 'No suspicious activity detected.',
    WARNING: 'Some irregularities have been noted.',
    HIGH: 'High risk — administrator has been alerted.',
    CRITICAL: 'Critical level — exam may be terminated.',
  };

  return (
    <div style={S.root}>
      <svg width="136" height="92" viewBox="0 0 136 92" overflow="visible">
        {/* Track */}
        <circle cx={cx} cy={cy} r={r} fill="none"
          stroke={colors.gray200} strokeWidth="9" strokeLinecap="round"
          strokeDasharray={`${arcLength} ${circumf - arcLength}`}
          transform={`rotate(${startDeg} ${cx} ${cy})`}
        />
        {/* Fill */}
        {pct > 0 && (
          <circle cx={cx} cy={cy} r={r} fill="none"
            stroke={cfg.color} strokeWidth="9" strokeLinecap="round"
            strokeDasharray={`${fillLen} ${circumf - fillLen}`}
            transform={`rotate(${startDeg} ${cx} ${cy})`}
            style={{ transition: 'stroke-dasharray 0.6s ease, stroke 0.4s' }}
          />
        )}
        {/* Threshold ticks */}
        {[30, 60, 85].map((t) => {
          const a = (startDeg + (t / 100) * 270) * (Math.PI / 180);
          const x1 = cx + (r - 7) * Math.cos(a);
          const y1 = cy + (r - 7) * Math.sin(a);
          const x2 = cx + (r + 1) * Math.cos(a);
          const y2 = cy + (r + 1) * Math.sin(a);
          return <line key={t} x1={x1} y1={y1} x2={x2} y2={y2} stroke={colors.gray300} strokeWidth="1.5" />;
        })}
        {/* Score */}
        <text x={cx} y={cy + 7} textAnchor="middle"
          style={{ fill: colors.gray900, fontSize: '22px', fontWeight: 700, fontFamily: fonts.mono }}>
          {pct.toFixed(0)}
        </text>
        <text x={cx} y={cy + 22} textAnchor="middle"
          style={{ fill: colors.gray400, fontSize: '9px', fontFamily: fonts.ui }}>
          / 100
        </text>
        {/* Range labels */}
        <text x="16" y="90" style={{ fill: colors.gray400, fontSize: '9px', fontFamily: fonts.mono }}>0</text>
        <text x="112" y="90" style={{ fill: colors.gray400, fontSize: '9px', fontFamily: fonts.mono }}>100</text>
      </svg>

      <div>
        <div style={{ ...S.label, color: cfg.color }}>{cfg.label}</div>
        <div style={S.desc}>{DESCS[level] || ''}</div>
      </div>
    </div>
  );
}