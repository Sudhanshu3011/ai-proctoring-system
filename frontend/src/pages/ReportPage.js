// src/pages/ReportPage.js — style/logic separated, professional theme
import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { reportAPI } from '../services/api';
import { useAuth } from '../context/AuthContext';
import IntegrityReport from '../components/IntegrityReport';
import GazeHeatmap from '../components/GazeHeatmap';
import { colors, fonts, radius, shadow, statusConfig } from '../styles/theme';
import { nav, card, btn, text, table } from '../styles/styles';

// ── Styles ────────────────────────────────────────────────────────
const S = {
  page: {
    minHeight: '100vh', background: colors.gray50,
    fontFamily: fonts.ui, color: colors.gray900,
  },
  navbar: {
    background: colors.white, borderBottom: `1px solid ${colors.gray200}`,
    padding: '0 28px', height: '52px',
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    position: 'sticky', top: 0, zIndex: 10, boxShadow: shadow.xs,
  },
  body: {
    maxWidth: '860px', margin: '0 auto', padding: '32px 24px',
  },
  metaGrid: {
    display: 'grid', gridTemplateColumns: '1fr 1fr',
    gap: '24px', marginBottom: '20px',
  },
  metaLabel: {
    fontSize: '10px', fontWeight: 700, color: colors.gray400,
    textTransform: 'uppercase', letterSpacing: '0.06em',
    marginBottom: '4px', fontFamily: fonts.ui,
  },
  metaValue: {
    fontFamily: fonts.display, fontSize: '16px', fontWeight: 400,
    color: colors.gray900, letterSpacing: '-0.02em', marginBottom: '2px',
  },
  metaSub: {
    fontSize: '12px', color: colors.gray500,
  },
  statCards: {
    display: 'grid', gridTemplateColumns: 'repeat(4,1fr)',
    gap: '10px', marginBottom: '20px',
  },
  statCard: (col) => ({
    background: colors.white, border: `1px solid ${colors.gray200}`,
    borderRadius: radius.lg, padding: '14px 16px', textAlign: 'center',
    boxShadow: shadow.xs,
  }),
  statVal: (col) => ({
    fontFamily: fonts.mono, fontSize: '22px', fontWeight: 700,
    color: col, lineHeight: 1, marginBottom: '4px',
  }),
  statLbl: {
    fontSize: '10px', fontWeight: 600, color: colors.gray400,
    textTransform: 'uppercase', letterSpacing: '0.05em',
  },
  sectionCard: {
    background: colors.white, border: `1px solid ${colors.gray200}`,
    borderRadius: radius.lg, padding: '20px', boxShadow: shadow.xs,
    marginBottom: '16px',
  },
  sectionTitle: {
    fontSize: '10px', fontWeight: 700, color: colors.gray400,
    textTransform: 'uppercase', letterSpacing: '0.06em',
    marginBottom: '14px', fontFamily: fonts.ui,
  },
  violRow: (high) => ({
    display: 'grid', gridTemplateColumns: '72px 1fr 72px 44px',
    gap: '10px', alignItems: 'center',
    padding: '7px 10px', borderRadius: radius.sm, marginBottom: '4px',
    background: high ? colors.dangerLight : colors.gray50,
    border: `1px solid ${high ? colors.dangerBorder : colors.gray100}`,
    fontSize: '12px',
  }),
  violType: (high) => ({
    fontWeight: 600,
    color: high ? colors.dangerMid : colors.gray700,
    fontSize: '12px',
  }),
  weightBadge: (high) => ({
    textAlign: 'center', borderRadius: '99px', padding: '1px 7px',
    background: high ? '#fee2e2' : colors.gray200,
    color: high ? colors.dangerMid : colors.gray600,
    fontSize: '10px', fontWeight: 700, fontFamily: fonts.mono,
  }),
  adminNote: {
    display: 'flex', alignItems: 'center', gap: '8px',
    background: colors.gray50, border: `1px solid ${colors.gray200}`,
    borderRadius: radius.md, padding: '8px 14px',
    fontSize: '12px', color: colors.gray500, marginTop: '-8px', marginBottom: '16px',
  },
};

// ── Component ─────────────────────────────────────────────────────
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
      const gen = await fetch(`/api/v1/reports/generate/${sessionId}`, {
        method: 'POST', headers: { Authorization: `Bearer ${token}` },
      });
      if (!gen.ok) throw new Error('Generation failed');
      const res = await fetch(`/api/v1/reports/${sessionId}/download`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`Download failed: ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = `report_${sessionId.slice(0, 8)}.pdf`;
      a.click(); URL.revokeObjectURL(url);
    } catch (e) { alert('Download failed: ' + e.message); }
    finally { setDlLoad(false); }
  };

  // Loading / error states
  if (loading) return (
    <div style={{
      minHeight: '100vh', background: colors.gray50,
      display: 'flex', alignItems: 'center', justifyContent: 'center'
    }}>
      <div style={{
        width: 32, height: 32, border: `3px solid ${colors.gray200}`,
        borderTopColor: colors.accent, borderRadius: '50%',
        animation: 'spin 0.8s linear infinite'
      }} />
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );

  if (error) return (
    <div style={{
      minHeight: '100vh', background: colors.gray50,
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px'
    }}>
      <div style={{ ...S.sectionCard, maxWidth: '400px', textAlign: 'center', padding: '40px' }}>
        <div style={{ color: colors.dangerMid, fontSize: '13px', marginBottom: '16px' }}>{error}</div>
        <button style={{ ...btn.secondary }} onClick={() => navigate('/dashboard')}>
          Back to Dashboard
        </button>
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
      {/* Navbar */}
      <nav style={S.navbar}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            width: '28px', height: '28px', background: colors.brand,
            borderRadius: radius.md, display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L4 6v6c0 5.5 3.6 10.3 8 12 4.4-1.7 8-6.5 8-12V6L12 2z" fill="white" />
            </svg>
          </div>
          <span style={{ fontFamily: fonts.display, fontSize: '15px', color: colors.gray900, letterSpacing: '-0.02em' }}>
            Exam Report
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {isAdmin ? (
            <button style={{ ...btn.primary, fontSize: '12px', padding: '7px 14px' }}
              onClick={handleDownload} disabled={dlLoad}>
              {dlLoad ? 'Generating…' : 'Download PDF'}
            </button>
          ) : (
            <span style={{ fontSize: '11px', color: colors.gray400 }}>
              Download available to administrators only
            </span>
          )}
          <button style={{ ...btn.secondary, fontSize: '12px', padding: '7px 14px' }}
            onClick={() => navigate(isAdmin ? '/admin' : '/dashboard')}>
            Back
          </button>
        </div>
      </nav>

      <div style={S.body}>

        {/* Candidate + Exam */}
        <div style={{ ...S.sectionCard, ...S.metaGrid }}>
          <div>
            <div style={S.metaLabel}>Candidate</div>
            <div style={S.metaValue}>{data?.candidate?.name || '—'}</div>
            <div style={S.metaSub}>{data?.candidate?.email}</div>
          </div>
          <div>
            <div style={S.metaLabel}>Exam</div>
            <div style={S.metaValue}>{data?.exam?.title || '—'}</div>
            <div style={S.metaSub}>
              {data?.exam?.started_at
                ? new Date(data.exam.started_at * 1000).toLocaleString()
                : '—'}
            </div>
          </div>
        </div>

        {/* Metric cards */}
        <div style={S.statCards}>
          {[
            { l: 'Risk Score', v: score.toFixed(1), u: '/100', col: cfg.color },
            { l: 'Risk Level', v: cfg.label, u: '', col: cfg.color },
            { l: 'Cheat Probability', v: (prob * 100).toFixed(1), u: '%', col: prob > 0.75 ? colors.dangerMid : prob > 0.4 ? colors.warningMid : colors.successMid },
            { l: 'Total Violations', v: viols.length, u: '', col: colors.gray700 },
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
            <div style={S.sectionTitle}>Module Breakdown</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(100px,1fr))', gap: '8px' }}>
              {Object.entries(mstats).map(([mod, s]) => (
                <div key={mod} style={{
                  background: colors.gray50, border: `1px solid ${colors.gray200}`,
                  borderRadius: radius.md, padding: '10px', textAlign: 'center'
                }}>
                  <div style={{
                    fontFamily: fonts.mono, fontSize: '20px', fontWeight: 700,
                    color: colors.gray900
                  }}>{s.violation_count}</div>
                  <div style={{
                    fontSize: '10px', color: colors.gray500, textTransform: 'capitalize',
                    fontWeight: 600, marginTop: '3px'
                  }}>{mod}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Gaze heatmap */}
        {data?.gaze_summary && (
          <div style={S.sectionCard}>
            <div style={S.sectionTitle}>Gaze Analysis</div>
            <GazeHeatmap gazeData={data.gaze_summary} />
          </div>
        )}

        {/* Violation timeline */}
        <div style={S.sectionCard}>
          <div style={S.sectionTitle}>Violation Timeline ({viols.length})</div>
          {viols.length === 0 ? (
            <div style={{ color: colors.successMid, fontSize: '13px' }}>No violations recorded.</div>
          ) : (
            <div style={{ maxHeight: '380px', overflowY: 'auto' }}>
              <div style={{
                display: 'flex', gap: '8px', padding: '4px 10px 6px',
                fontSize: '10px', fontWeight: 700, color: colors.gray400,
                textTransform: 'uppercase', letterSpacing: '0.05em'
              }}>
                <span style={{ width: '72px' }}>Time</span>
                <span style={{ flex: 1 }}>Type</span>
                <span style={{ width: '72px' }}>Confidence</span>
                <span style={{ width: '44px' }}>Weight</span>
              </div>
              {viols.map((v, i) => {
                const ts = v.timestamp ? new Date(v.timestamp * 1000).toLocaleTimeString() : '—';
                const high = (v.weight || 0) >= 30;
                return (
                  <div key={i} style={S.violRow(high)}>
                    <span style={{ fontFamily: fonts.mono, fontSize: '10px', color: colors.gray400 }}>{ts}</span>
                    <span style={S.violType(high)}>{v.violation_type}</span>
                    <span style={{ fontFamily: fonts.mono, fontSize: '10px', color: colors.gray400 }}>
                      {((v.confidence || 0) * 100).toFixed(0)}%
                    </span>
                    <span style={S.weightBadge(high)}>w:{v.weight}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Integrity assessment */}
        {data?.integrity_assessment && (
          <IntegrityReport assessment={data.integrity_assessment} />
        )}

        {/* Disclaimer */}
        <p style={{
          color: colors.gray400, fontSize: '11px', textAlign: 'center',
          marginTop: '20px', lineHeight: 1.6
        }}>
          This report was generated by the AI Proctoring System. All detections should be reviewed
          by a human invigilator before any disciplinary action is taken.
        </p>
      </div>
    </div>
  );
}