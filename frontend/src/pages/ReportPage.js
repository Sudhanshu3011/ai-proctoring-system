// src/pages/ReportPage.js — ProctorAI Premium

import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { reportAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import IntegrityReport from '../components/IntegrityReport';
import GazeHeatmap from '../components/GazeHeatmap';
import { colors, fonts, radius, shadow, statusConfig } from '../styles/theme';
import { btn } from '../styles/styles';

const S = {
  page: { minHeight: '100vh', background: colors.gray50, fontFamily: fonts.ui, color: colors.gray900 },

  navbar: {
    background: colors.white, borderBottom: `1px solid ${colors.gray200}`,
    padding: '0 28px', height: '58px',
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    position: 'sticky', top: 0, zIndex: 10,
    boxShadow: '0 1px 0 #e2e6ef, 0 2px 8px rgba(10,22,40,0.04)',
  },
  navLogo: {
    width: '34px', height: '34px',
    background: 'linear-gradient(135deg, #0a1628 0%, #122040 100%)',
    borderRadius: radius.md,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    boxShadow: '0 2px 8px rgba(10,22,40,0.20)',
  },

  body: { maxWidth: '880px', margin: '0 auto', padding: '32px 24px' },

  // Report header — solid smooth gradient, single glow, no grid
  reportHeader: {
    background: 'linear-gradient(145deg, #0a1628 0%, #0f2244 50%, #162d58 100%)',
    borderRadius: radius.xl, padding: '26px 30px', marginBottom: '18px',
    position: 'relative', overflow: 'hidden', boxShadow: shadow.lg,
  },
  headerGlow: {
    position: 'absolute', top: '-30px', right: '-30px', width: '180px', height: '180px',
    background: 'radial-gradient(circle, rgba(249,115,22,0.14) 0%, transparent 70%)',
    pointerEvents: 'none',
  },
  metaGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', position: 'relative' },
  metaLabel: { fontSize: '10px', fontWeight: 700, color: 'rgba(255,255,255,0.40)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '4px' },
  metaValue: { fontFamily: fonts.display, fontSize: '17px', fontWeight: 600, color: colors.white, marginBottom: '3px' },
  metaSub: { fontSize: '12px', color: 'rgba(255,255,255,0.45)' },

  statCards: { display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: '12px', marginBottom: '18px' },
  statCard: (col) => ({
    background: colors.white, border: `1px solid ${colors.gray200}`,
    borderRadius: radius.lg, padding: '14px 16px',
    textAlign: 'center', boxShadow: shadow.xs,
    borderTop: `3px solid ${col}`,
  }),
  statVal: (col) => ({ fontFamily: fonts.mono, fontSize: '21px', fontWeight: 700, color: col, lineHeight: 1, marginBottom: '5px' }),
  statLbl: { fontSize: '10px', fontWeight: 700, color: colors.gray400, textTransform: 'uppercase', letterSpacing: '0.06em' },

  sectionCard: {
    background: colors.white, border: `1px solid ${colors.gray200}`,
    borderRadius: radius.lg, padding: '20px 22px', boxShadow: shadow.xs, marginBottom: '14px',
  },
  sectionTitle: {
    fontSize: '10px', fontWeight: 700, color: colors.gray400,
    textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: '16px',
    display: 'flex', alignItems: 'center', gap: '8px',
  },
  sectionRule: { flex: 1, height: '1px', background: colors.gray200 },

  violRow: (high) => ({
    display: 'grid', gridTemplateColumns: '80px 1fr 80px 48px',
    gap: '10px', alignItems: 'center',
    padding: '8px 12px', borderRadius: radius.sm, marginBottom: '4px',
    background: high ? colors.dangerLight : colors.gray50,
    border: `1px solid ${high ? colors.dangerBorder : colors.gray100}`,
    fontSize: '12px',
  }),
  violType: (high) => ({ fontWeight: 600, color: high ? colors.dangerMid : colors.gray700, fontSize: '12px' }),
  weightBadge: (high) => ({
    textAlign: 'center', borderRadius: '99px', padding: '2px 8px',
    background: high ? '#fecaca' : colors.gray200,
    color: high ? colors.dangerMid : colors.gray500,
    fontSize: '10px', fontWeight: 700, fontFamily: fonts.mono,
    border: `1px solid ${high ? colors.dangerBorder : colors.gray300}`,
  }),
};

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
    if (!sessionId) { setError('No session ID provided.'); setLoad(false); return; }
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
      const gen = await fetch(`/api/v1/reports/generate/${sessionId}`, { method: 'POST', headers: { Authorization: `Bearer ${token}` } });
      if (!gen.ok) throw new Error('Generation failed');
      const res = await fetch(`/api/v1/reports/${sessionId}/download`, { headers: { Authorization: `Bearer ${token}` } });
      if (!res.ok) throw new Error(`Download failed: ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `report_${sessionId.slice(0, 8)}.pdf`;
      a.click(); URL.revokeObjectURL(url);
    } catch (e) { alert('Download failed: ' + e.message); }
    finally { setDlLoad(false); }
  };

  if (loading) return (
    <div style={{ minHeight: '100vh', background: colors.gray50, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '12px' }}>
      <div style={{ width: 34, height: 34, border: `3px solid ${colors.gray200}`, borderTopColor: colors.accent, borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
      <div style={{ fontSize: '13px', color: colors.gray500 }}>Loading report…</div>
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );

  if (error) return (
    <div style={{ minHeight: '100vh', background: colors.gray50, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px' }}>
      <div style={{ ...S.sectionCard, maxWidth: '420px', textAlign: 'center', padding: '48px' }}>
        <div style={{ color: colors.dangerMid, fontSize: '14px', fontWeight: 600, marginBottom: '16px' }}>{error}</div>
        <button style={btn.secondary} onClick={() => navigate('/dashboard')}>Back to Dashboard</button>
      </div>
    </div>
  );

  const risk = data?.risk_assessment || {};
  const level = risk.risk_level || 'SAFE';
  const score = risk.final_score || 0;
  const prob = risk.cheat_probability || 0;
  const viols = data?.violations || [];
  const mstats = data?.module_stats || {};
  const cfg = statusConfig[level] || statusConfig.SAFE;

  return (
    <div style={S.page}>
      <nav style={S.navbar}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={S.navLogo}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L4 6v6c0 5.5 3.6 10.3 8 12 4.4-1.7 8-6.5 8-12V6L12 2z" fill="white" opacity=".95" />
            </svg>
          </div>
          <span style={{ fontFamily: fonts.display, fontSize: '15px', fontWeight: 700, color: colors.gray900 }}>Exam Report</span>
          <span style={{ background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}`, borderRadius: '99px', padding: '2px 10px', fontSize: '11px', fontWeight: 700 }}>
            {cfg.label}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {isAdmin ? (
            <button className="btn-primary" style={{ fontSize: '12px', padding: '8px 16px' }} onClick={handleDownload} disabled={dlLoad}>
              {dlLoad ? 'Generating…' : 'Download PDF'}
            </button>
          ) : (
            <span style={{ fontSize: '11px', color: colors.gray400 }}>Admin access required for download</span>
          )}
          <button style={{ ...btn.secondary, fontSize: '12px', padding: '7px 14px' }}
            onClick={() => navigate(isAdmin ? '/admin' : '/dashboard')}>
            Back
          </button>
        </div>
      </nav>

      <div style={S.body}>
        {/* Header card */}
        <div style={S.reportHeader}>
          <div style={S.headerGlow} />
          <div style={S.metaGrid}>
            <div>
              <div style={S.metaLabel}>Candidate</div>
              <div style={S.metaValue}>{data?.candidate?.name || '—'}</div>
              <div style={S.metaSub}>{data?.candidate?.email}</div>
            </div>
            <div>
              <div style={S.metaLabel}>Exam</div>
              <div style={S.metaValue}>{data?.exam?.title || '—'}</div>
              <div style={S.metaSub}>
                {data?.exam?.started_at ? new Date(data.exam.started_at * 1000).toLocaleString() : '—'}
              </div>
            </div>
          </div>
        </div>

        {/* Metric cards */}
        <div style={S.statCards}>
          {[
            { l: 'Risk Score', v: `${score.toFixed(1)}`, u: '/100', col: cfg.color },
            { l: 'Risk Level', v: cfg.label, u: '', col: cfg.color },
            { l: 'Cheat Prob.', v: `${(prob * 100).toFixed(1)}`, u: '%', col: prob > 0.75 ? colors.dangerMid : prob > 0.4 ? colors.warningMid : colors.successMid },
            { l: 'Violations', v: viols.length, u: '', col: colors.gray700 },
          ].map(({ l, v, u, col }) => (
            <div key={l} style={S.statCard(col)}>
              <div style={S.statVal(col)}>
                {v}<span style={{ fontSize: '12px', color: colors.gray400, fontWeight: 400 }}>{u}</span>
              </div>
              <div style={S.statLbl}>{l}</div>
            </div>
          ))}
        </div>

        {/* Module breakdown */}
        {Object.keys(mstats).length > 0 && (
          <div style={S.sectionCard}>
            <div style={S.sectionTitle}>Module Breakdown <div style={S.sectionRule} /></div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(110px,1fr))', gap: '10px' }}>
              {Object.entries(mstats).map(([mod, s]) => (
                <div key={mod} style={{ background: colors.gray50, border: `1px solid ${colors.gray200}`, borderRadius: radius.md, padding: '12px', textAlign: 'center' }}>
                  <div style={{ fontFamily: fonts.mono, fontSize: '22px', fontWeight: 700, color: colors.gray900 }}>{s.violation_count}</div>
                  <div style={{ fontSize: '10px', color: colors.gray500, textTransform: 'capitalize', fontWeight: 600, marginTop: '3px' }}>{mod}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Gaze heatmap */}
        {data?.gaze_summary && (
          <div style={S.sectionCard}>
            <div style={S.sectionTitle}>Gaze Analysis <div style={S.sectionRule} /></div>
            <GazeHeatmap gazeData={data.gaze_summary} />
          </div>
        )}

        {/* Violation timeline */}
        <div style={S.sectionCard}>
          <div style={S.sectionTitle}>
            Violation Timeline
            <div style={S.sectionRule} />
            <span style={{
              background: viols.length > 0 ? colors.dangerLight : colors.successLight,
              color: viols.length > 0 ? colors.dangerMid : colors.successMid,
              border: `1px solid ${viols.length > 0 ? colors.dangerBorder : colors.successBorder}`,
              borderRadius: '99px', padding: '1px 8px', fontSize: '10px',
            }}>{viols.length} events</span>
          </div>
          {viols.length === 0 ? (
            <div style={{ color: colors.successMid, fontSize: '13px', fontWeight: 600 }}>No violations recorded</div>
          ) : (
            <div style={{ maxHeight: '380px', overflowY: 'auto' }}>
              <div style={{ display: 'flex', gap: '8px', padding: '4px 12px 8px', fontSize: '10px', fontWeight: 700, color: colors.gray400, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                <span style={{ width: '80px' }}>Time</span>
                <span style={{ flex: 1 }}>Type</span>
                <span style={{ width: '80px' }}>Confidence</span>
                <span style={{ width: '48px' }}>Weight</span>
              </div>
              {viols.map((v, i) => {
                const ts = v.timestamp ? new Date(v.timestamp * 1000).toLocaleTimeString() : '—';
                const high = (v.weight || 0) >= 30;
                return (
                  <div key={i} style={S.violRow(high)}>
                    <span style={{ fontFamily: fonts.mono, fontSize: '10px', color: colors.gray400 }}>{ts}</span>
                    <span style={S.violType(high)}>{v.violation_type}</span>
                    <span style={{ fontFamily: fonts.mono, fontSize: '10px', color: colors.gray400 }}>{((v.confidence || 0) * 100).toFixed(0)}%</span>
                    <span style={S.weightBadge(high)}>w:{v.weight}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {data?.integrity_assessment && <IntegrityReport assessment={data.integrity_assessment} />}

        <p style={{ color: colors.gray400, fontSize: '11px', textAlign: 'center', marginTop: '24px', lineHeight: 1.6 }}>
          This report was generated by ProctorAI. All detections should be reviewed by a human invigilator before any disciplinary action is taken.
        </p>
      </div>
    </div>
  );
}