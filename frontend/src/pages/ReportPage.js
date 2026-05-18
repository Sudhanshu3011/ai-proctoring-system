import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { reportAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import GazeHeatmap from '../components/GazeHeatmap';
import IntegrityReport from '../components/IntegrityReport';

// ── Design tokens (navy + orange — no external CSS vars needed) ──
const C = {
  navy: '#1e3a5f',
  navyMid: '#2d5282',
  navyLt: '#ebf4ff',
  navyBd: '#bfdbfe',
  orange: '#ea580c',
  orangeLt: '#fff7ed',
  orangeBd: '#fed7aa',
  white: '#ffffff',
  gray50: '#fafafa',
  gray100: '#f4f4f5',
  gray200: '#e4e4e7',
  gray300: '#d4d4d8',
  gray400: '#a1a1aa',
  gray500: '#71717a',
  gray600: '#52525b',
  gray700: '#3f3f46',
  gray900: '#18181b',
  safe: '#059669',
  safeLt: '#ecfdf5',
  safeBd: '#a7f3d0',
  safeMid: '#16a34a',
  warn: '#d97706',
  warnLt: '#fffbeb',
  warnBd: '#fde68a',
  danger: '#dc2626',
  dangerLt: '#fff1f2',
  dangerBd: '#fecdd3',
};

const LEVEL_COL = { SAFE: C.safeMid, WARNING: C.warn, HIGH: C.danger, CRITICAL: '#991b1b' };
const LEVEL_BG = { SAFE: C.safeLt, WARNING: C.warnLt, HIGH: C.dangerLt, CRITICAL: '#fef2f2' };

// ── All styles ────────────────────────────────────────────────────
const S = {
  page: {
    minHeight: '100vh',
    background: `linear-gradient(160deg, ${C.navy} 0%, #0f2340 100%)`,
    fontFamily: "'DM Sans', 'Helvetica Neue', sans-serif",
    color: C.gray900,
  },
  navbar: {
    background: `rgba(30,58,95,0.96)`,
    backdropFilter: 'blur(8px)',
    borderBottom: `1px solid rgba(255,255,255,0.1)`,
    padding: '0 28px', height: '56px',
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    position: 'sticky', top: 0, zIndex: 50,
  },
  navBrand: { display: 'flex', alignItems: 'center', gap: '10px' },
  navLogo: {
    width: 32, height: 32, borderRadius: '8px',
    background: C.orange, display: 'flex',
    alignItems: 'center', justifyContent: 'center',
  },
  navTitle: {
    fontFamily: "'DM Serif Display', Georgia, serif",
    fontSize: '16px', color: C.white, letterSpacing: '-0.02em',
  },
  navActions: { display: 'flex', alignItems: 'center', gap: '8px' },
  dlBtn: {
    background: C.orange, color: C.white,
    border: 'none', borderRadius: '7px',
    padding: '7px 16px', fontSize: '12px', fontWeight: 700,
    cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '6px',
    boxShadow: '0 2px 6px rgba(234,88,12,0.35)',
  },
  backBtn: {
    background: 'rgba(255,255,255,0.12)', color: C.white,
    border: '1px solid rgba(255,255,255,0.2)', borderRadius: '7px',
    padding: '7px 14px', fontSize: '12px', fontWeight: 500,
    cursor: 'pointer',
  },
  body: { maxWidth: '900px', margin: '0 auto', padding: '28px 20px 56px' },
  // Hero score card (admin+student)
  hero: {
    background: `linear-gradient(135deg, ${C.navy} 0%, ${C.navyMid} 100%)`,
    border: `1px solid rgba(255,255,255,0.12)`,
    borderRadius: '14px', padding: '24px 28px',
    marginBottom: '20px', color: C.white,
    display: 'flex', alignItems: 'center', gap: '28px',
    flexWrap: 'wrap',
  },
  heroScore: {
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: '56px', fontWeight: 700, color: C.white, lineHeight: 1,
  },
  heroLabel: {
    fontSize: '12px', color: 'rgba(255,255,255,0.55)',
    textTransform: 'uppercase', letterSpacing: '0.07em', marginTop: '4px'
  },
  heroDivider: { width: 1, height: 60, background: 'rgba(255,255,255,0.15)', flexShrink: 0 },
  heroPill: (level) => ({
    display: 'inline-block',
    background: level === 'SAFE' ? 'rgba(16,185,129,0.2)'
      : level === 'WARNING' ? 'rgba(217,119,6,0.2)'
        : level === 'HIGH' ? 'rgba(220,38,38,0.2)'
          : 'rgba(153,27,27,0.3)',
    border: `1px solid ${level === 'SAFE' ? 'rgba(16,185,129,0.4)' :
      level === 'WARNING' ? 'rgba(217,119,6,0.4)' :
        'rgba(220,38,38,0.4)'}`,
    color: level === 'SAFE' ? '#6ee7b7'
      : level === 'WARNING' ? '#fcd34d'
        : '#fca5a5',
    borderRadius: '99px', padding: '4px 14px',
    fontSize: '12px', fontWeight: 700, letterSpacing: '0.04em',
    marginBottom: '8px', display: 'inline-block',
  }),
  // Info cards
  metaGrid: {
    display: 'grid', gridTemplateColumns: '1fr 1fr',
    gap: '16px', marginBottom: '16px',
  },
  infoCard: {
    background: C.white, border: `1px solid ${C.gray200}`,
    borderRadius: '10px', padding: '16px 20px',
    boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
  },
  infoLabel: {
    fontSize: '10px', fontWeight: 700, color: C.gray400,
    textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '5px',
  },
  infoVal: {
    fontFamily: "'DM Serif Display', Georgia, serif",
    fontSize: '15px', fontWeight: 400, color: C.gray900,
    letterSpacing: '-0.02em', marginBottom: '2px',
  },
  infoSub: { fontSize: '12px', color: C.gray500 },
  // Stat strip
  statStrip: {
    display: 'grid', gridTemplateColumns: 'repeat(4,1fr)',
    gap: '10px', marginBottom: '20px',
  },
  statCard: (hi) => ({
    background: C.white, border: `1px solid ${hi ? C.orangeBd : C.gray200}`,
    borderTop: `3px solid ${hi ? C.orange : C.gray200}`,
    borderRadius: '10px', padding: '14px 16px', textAlign: 'center',
    boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
  }),
  statVal: (col) => ({
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: '22px', fontWeight: 700, color: col || C.gray900, lineHeight: 1,
  }),
  statLbl: {
    fontSize: '10px', fontWeight: 600, color: C.gray400,
    textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: '5px',
  },
  // Section cards
  section: {
    background: C.white, border: `1px solid ${C.gray200}`,
    borderRadius: '10px', padding: '18px 20px',
    boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
    marginBottom: '16px',
  },
  sectionTitle: {
    fontSize: '11px', fontWeight: 700, color: C.gray400,
    textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '14px',
    paddingBottom: '8px', borderBottom: `1px solid ${C.gray100}`,
  },
  // Module bars
  modRow: { display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' },
  modLabel: { fontSize: '12px', color: C.gray600, width: '72px', flexShrink: 0 },
  modTrack: { flex: 1, height: 6, background: C.gray100, borderRadius: '99px', overflow: 'hidden' },
  modFill: (v) => ({
    height: '100%',
    width: `${Math.min(100, v || 0)}%`,
    background: (v || 0) > 60 ? C.danger : (v || 0) > 30 ? C.warn : C.safeMid,
    borderRadius: '99px', transition: 'width 0.6s ease',
  }),
  modVal: {
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: '11px', color: C.gray400, width: '32px', textAlign: 'right',
  },
  // Violation timeline
  timelineWrap: { maxHeight: '460px', overflowY: 'auto' },
  timelineRow: (high) => ({
    display: 'flex', gap: '12px', alignItems: 'flex-start',
    padding: '8px 0',
    borderBottom: `1px solid ${C.gray100}`,
  }),
  tlTime: {
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: '11px', color: C.gray400,
    width: '60px', flexShrink: 0, paddingTop: '2px',
  },
  tlDot: (level) => ({
    width: 10, height: 10, borderRadius: '50%', flexShrink: 0, marginTop: '4px',
    background: level === 'HIGH' || level === 'CRITICAL' ? C.danger : C.warn,
  }),
  tlType: (high) => ({
    fontWeight: 700, fontSize: '13px',
    color: high ? C.danger : C.gray900,
    marginBottom: '2px',
  }),
  tlMeta: {
    fontSize: '11px', color: C.gray500, display: 'flex', gap: '12px', flexWrap: 'wrap',
  },
  tlWt: (high) => ({
    fontFamily: "'IBM Plex Mono', monospace",
    fontSize: '10px', fontWeight: 700,
    color: high ? C.orange : C.gray400,
    background: high ? C.orangeLt : C.gray100,
    border: `1px solid ${high ? C.orangeBd : C.gray200}`,
    borderRadius: '99px', padding: '2px 8px',
  }),
  // Student-only info box
  viewOnlyBanner: {
    background: C.navyLt, border: `1px solid ${C.navyBd}`,
    borderLeft: `3px solid ${C.navy}`,
    borderRadius: '8px', padding: '10px 14px',
    fontSize: '12px', color: C.navyMid,
    display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px',
  },
};

// ── Helpers ───────────────────────────────────────────────────────
const fmtTime = (ts) => {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
};
const fmtDate = (ts) => {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
};

// ── Sub-components ────────────────────────────────────────────────
function ModuleBreakdown({ risk }) {
  const modules = [
    ['Face', risk?.face_score],
    ['Pose', risk?.pose_score],
    ['Objects', risk?.object_score],
    ['Audio', risk?.audio_score],
    ['Browser', risk?.browser_score],
  ];
  return (
    <div>
      {modules.map(([label, val]) => (
        <div key={label} style={S.modRow}>
          <span style={S.modLabel}>{label}</span>
          <div style={S.modTrack}><div style={S.modFill(val)} /></div>
          <span style={S.modVal}>{((val || 0)).toFixed(0)}</span>
        </div>
      ))}
    </div>
  );
}

function ViolationTimeline({ violations }) {
  if (!violations?.length) {
    return <div style={{ color: C.safeMid, fontSize: '13px' }}>No violations recorded.</div>;
  }
  return (
    <div style={S.timelineWrap}>
      {/* Column headers */}
      <div style={{
        display: 'flex', gap: '12px',
        fontSize: '10px', fontWeight: 700, color: C.gray400,
        textTransform: 'uppercase', letterSpacing: '0.06em',
        padding: '0 0 6px', borderBottom: `1px solid ${C.gray200}`, marginBottom: '4px'
      }}>
        <span style={{ width: '60px', flexShrink: 0 }}>Time</span>
        <span style={{ width: 10, flexShrink: 0 }} />
        <span style={{ flex: 1 }}>Violation</span>
        <span>Module</span>
        <span style={{ width: '40px', textAlign: 'right' }}>Wt.</span>
      </div>
      {violations.map((v, i) => {
        const high = v.weight >= 20;
        const vt = v.violation_type?.replace(/_/g, ' ').toLowerCase() || '—';
        return (
          <div key={i} style={S.timelineRow(high)}>
            <span style={S.tlTime}>{fmtTime(v.timestamp)}</span>
            <div style={S.tlDot(high ? 'HIGH' : 'WARNING')} />
            <div style={{ flex: 1 }}>
              <div style={S.tlType(high)}>{vt}</div>
              {v.description && (
                <div style={{ fontSize: '10px', color: C.gray400, marginTop: '1px' }}>
                  {v.description}
                </div>
              )}
            </div>
            <span style={{
              fontSize: '11px', color: C.gray500,
              background: C.gray50, padding: '2px 8px',
              border: `1px solid ${C.gray200}`, borderRadius: '4px',
              flexShrink: 0, fontSize: '10px'
            }}>
              {v.source_module || '—'}
            </span>
            <span style={S.tlWt(high)}>w:{v.weight}</span>
          </div>
        );
      })}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────
export default function ReportPage() {
  const [sp] = useSearchParams();
  const sessionId = sp.get('session');
  const navigate = useNavigate();
  const { user } = useAuth();

  const [data, setData] = useState(null);
  const [loading, setLoad] = useState(true);
  const [error, setError] = useState('');
  const [dlLoad, setDlLoad] = useState(false);

  const isAdmin = user?.role === 'admin';

  useEffect(() => {
    if (!sessionId) { setError('No session ID.'); setLoad(false); return; }
    reportAPI.get(sessionId)
      .then(r => setData(r.data))
      .catch(e => setError(e.response?.data?.detail || 'Failed to load report.'))
      .finally(() => setLoad(false));
  }, [sessionId]);

  const handleDownload = async () => {
    if (!isAdmin) return;
    setDlLoad(true);
    try {
      const token = localStorage.getItem('token');
      // Ensure PDF is generated first
      await fetch(`/api/v1/reports/generate/${sessionId}`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}` },
      });
      const res = await fetch(`/api/v1/reports/${sessionId}/download`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Download failed (${res.status})`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `report_${sessionId.slice(0, 8)}.pdf`;
      a.click(); URL.revokeObjectURL(url);
    } catch (e) { alert('Download failed: ' + e.message); }
    finally { setDlLoad(false); }
  };

  // Loading spinner
  if (loading) return (
    <div style={{ ...S.page, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{
        width: 36, height: 36,
        border: '3px solid rgba(255,255,255,0.2)', borderTopColor: C.orange,
        borderRadius: '50%', animation: 'spin 0.8s linear infinite'
      }} />
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );

  // Error state
  if (error) return (
    <div style={{
      ...S.page, display: 'flex', alignItems: 'center',
      justifyContent: 'center', padding: '24px'
    }}>
      <div style={{
        background: C.white, borderRadius: '12px', padding: '40px',
        maxWidth: '400px', width: '100%', textAlign: 'center',
        boxShadow: '0 20px 60px rgba(0,0,0,0.3)'
      }}>
        <div style={{ color: C.danger, fontSize: '13px', marginBottom: '16px' }}>{error}</div>
        <button style={S.backBtn} onClick={() => navigate(isAdmin ? '/admin' : '/dashboard')}>
          Go Back
        </button>
      </div>
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );

  const risk = data?.risk_assessment || {};
  const level = risk.risk_level || 'SAFE';
  const score = risk.final_score || 0;
  const prob = risk.cheat_probability || 0;
  const viols = data?.violations || [];

  return (
    <div style={S.page}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;600&display=swap');
        @keyframes spin{to{transform:rotate(360deg)}}
        ::-webkit-scrollbar{width:4px;height:4px}
        ::-webkit-scrollbar-track{background:#f4f4f5}
        ::-webkit-scrollbar-thumb{background:#d4d4d8;border-radius:99px}
      `}</style>

      {/* Navbar */}
      <nav style={S.navbar}>
        <div style={S.navBrand}>
          <div style={S.navLogo}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L4 6v6c0 5.5 3.6 10.3 8 12 4.4-1.7 8-6.5 8-12V6L12 2z" fill="white" />
            </svg>
          </div>
          <span style={S.navTitle}>Exam Report</span>
          <span style={{
            background: 'rgba(234,88,12,0.2)', color: C.orange,
            border: '1px solid rgba(234,88,12,0.3)', borderRadius: '99px',
            padding: '2px 10px', fontSize: '10px', fontWeight: 700,
            textTransform: 'uppercase', letterSpacing: '0.05em', marginLeft: '8px'
          }}>
            {isAdmin ? 'Admin' : 'Student View'}
          </span>
        </div>
        <div style={S.navActions}>
          {/* Admin only download */}
          {isAdmin && (
            <button style={S.dlBtn} onClick={handleDownload} disabled={dlLoad}>
              {dlLoad ? 'Generating…' : '↓ Download PDF'}
            </button>
          )}
          <button style={S.backBtn}
            onClick={() => navigate(isAdmin ? '/admin' : '/dashboard')}>
            ← Back
          </button>
        </div>
      </nav>

      <div style={S.body}>

        {/* Hero risk card */}
        <div style={S.hero}>
          <div>
            <div style={S.heroPill(level)}>{level}</div>
            <div style={S.heroScore}>{score.toFixed(1)}</div>
            <div style={S.heroLabel}>Risk Score / 100</div>
          </div>
          <div style={S.heroDivider} />
          <div style={{ flex: 1 }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(130px,1fr))', gap: '16px' }}>
              {[
                {
                  l: 'Cheat Probability', v: `${(prob * 100).toFixed(1)}%`,
                  col: prob > 0.75 ? '#fca5a5' : prob > 0.4 ? '#fcd34d' : '#6ee7b7'
                },
                { l: 'Violations Total', v: viols.length, col: C.white },
                { l: 'Duration', v: `${(data?.exam?.duration_min || 0).toFixed(0)}m`, col: C.white },
                { l: 'Session', v: sessionId?.slice(0, 8) + '…', col: 'rgba(255,255,255,0.5)' },
              ].map(({ l, v, col }) => (
                <div key={l}>
                  <div style={{
                    fontFamily: "'IBM Plex Mono', monospace",
                    fontSize: '20px', fontWeight: 700, color: col
                  }}>{v}</div>
                  <div style={{
                    fontSize: '10px', color: 'rgba(255,255,255,0.5)',
                    textTransform: 'uppercase', letterSpacing: '0.06em', marginTop: '3px'
                  }}>
                    {l}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Student view-only banner */}
        {!isAdmin && (
          <div style={S.viewOnlyBanner}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <circle cx="12" cy="12" r="10" stroke={C.navy} strokeWidth="2" />
              <path d="M12 8v4m0 4h.01" stroke={C.navy} strokeWidth="2" strokeLinecap="round" />
            </svg>
            <span>
              This report is <strong>view-only</strong>. Contact your invigilator for a copy.
            </span>
          </div>
        )}

        {/* Candidate + Exam info */}
        <div style={S.metaGrid}>
          <div style={S.infoCard}>
            <div style={S.infoLabel}>Candidate</div>
            <div style={S.infoVal}>{data?.candidate?.name || '—'}</div>
            <div style={S.infoSub}>{data?.candidate?.email || ''}</div>
          </div>
          <div style={S.infoCard}>
            <div style={S.infoLabel}>Exam</div>
            <div style={S.infoVal}>{data?.exam?.title || '—'}</div>
            <div style={S.infoSub}>{fmtDate(data?.exam?.started_at)}</div>
          </div>
        </div>

        {/* Module breakdown (admin only) */}
        {isAdmin && (
          <div style={S.section}>
            <div style={S.sectionTitle}>Module Scores</div>
            <ModuleBreakdown risk={risk} />
          </div>
        )}

        {/* Violation timeline — shown to everyone */}
        <div style={S.section}>
          <div style={{
            display: 'flex', justifyContent: 'space-between',
            alignItems: 'center', marginBottom: '14px',
            paddingBottom: '8px', borderBottom: `1px solid ${C.gray100}`
          }}>
            <div style={S.sectionTitle} className="m0">
              Violation Timeline
            </div>
            <span style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: '12px', fontWeight: 700,
              background: viols.length > 0 ? C.orangeLt : C.safeLt,
              color: viols.length > 0 ? C.orange : C.safeMid,
              border: `1px solid ${viols.length > 0 ? C.orangeBd : C.safeBd}`,
              borderRadius: '99px', padding: '2px 10px'
            }}>
              {viols.length} violation{viols.length !== 1 ? 's' : ''}
            </span>
          </div>
          <ViolationTimeline violations={viols} />
        </div>

        {/* Gaze heatmap — admin only */}
        {isAdmin && data?.gaze_summary && (
          <div style={S.section}>
            <div style={S.sectionTitle}>Gaze Analysis</div>
            <GazeHeatmap gazeData={data.gaze_summary} />
          </div>
        )}

        {/* Integrity assessment — admin only */}
        {isAdmin && data?.integrity_assessment && (
          <IntegrityReport assessment={data.integrity_assessment} />
        )}

        {/* Disclaimer */}
        <p style={{
          color: 'rgba(255,255,255,0.3)', fontSize: '11px',
          textAlign: 'center', marginTop: '24px', lineHeight: 1.7
        }}>
          This report was generated by the ProctorAI system.
          All detections must be reviewed by a qualified invigilator before any action is taken.
        </p>
      </div>

      <style>{`.m0{margin-bottom:0!important}`}</style>
    </div>
  );
}