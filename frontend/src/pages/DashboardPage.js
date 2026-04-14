// src/pages/DashboardPage.js — ProctorAI Premium

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { examAPI, authAPI } from '../services/api';
import { colors, fonts, radius, shadow } from '../styles/theme';
import { btn } from '../styles/styles';

const S = {
  page: { minHeight: '100vh', background: colors.gray50, fontFamily: fonts.ui },

  navbar: {
    background: colors.white, borderBottom: `1px solid ${colors.gray200}`,
    padding: '0 28px', height: '58px',
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    position: 'sticky', top: 0, zIndex: 50,
    boxShadow: '0 1px 0 #e2e6ef, 0 2px 8px rgba(10,22,40,0.04)',
  },
  navLeft: { display: 'flex', alignItems: 'center', gap: '12px' },
  navLogo: {
    width: '34px', height: '34px',
    background: 'linear-gradient(135deg, #0a1628 0%, #122040 100%)',
    borderRadius: radius.md,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    boxShadow: '0 2px 8px rgba(10,22,40,0.20)',
  },
  navBrand: { fontFamily: fonts.display, fontSize: '16px', fontWeight: 700, color: colors.gray900, letterSpacing: '-0.02em' },
  navTag: {
    fontSize: '9px', fontWeight: 700, color: colors.accent,
    background: colors.accentLight, border: `1px solid ${colors.accentBorder}`,
    borderRadius: '4px', padding: '1px 6px', letterSpacing: '0.05em', textTransform: 'uppercase',
  },

  body: { maxWidth: '900px', margin: '0 auto', padding: '36px 24px' },

  // Hero — smooth solid gradient, single soft glow, no grid
  hero: {
    background: 'linear-gradient(145deg, #0a1628 0%, #0f2244 55%, #162d58 100%)',
    borderRadius: radius.xl, padding: '28px 32px', marginBottom: '24px',
    position: 'relative', overflow: 'hidden', boxShadow: shadow.lg,
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  },
  heroGlow: {
    position: 'absolute', top: '-40px', right: '-40px', width: '220px', height: '220px',
    background: 'radial-gradient(circle, rgba(249,115,22,0.12) 0%, transparent 70%)',
    pointerEvents: 'none',
  },
  heroGreeting: {
    fontFamily: fonts.display, fontSize: '24px', fontWeight: 700,
    color: colors.white, letterSpacing: '-0.03em', marginBottom: '4px', position: 'relative',
  },
  heroAccent: {
    background: 'linear-gradient(135deg, #f97316 0%, #fb923c 100%)',
    WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
  },
  heroSub: { fontSize: '13px', color: 'rgba(255,255,255,0.5)', position: 'relative' },
  heroBadge: {
    background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.10)',
    borderRadius: radius.md, padding: '10px 16px', textAlign: 'right', position: 'relative',
  },
  heroBadgeVal: { fontFamily: fonts.mono, fontSize: '16px', fontWeight: 700, color: colors.white },
  heroBadgeLbl: { fontSize: '10px', color: 'rgba(255,255,255,0.38)', marginTop: '2px' },

  statRow: { display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '14px', marginBottom: '24px' },
  statCard: {
    background: colors.white, border: `1px solid ${colors.gray200}`,
    borderRadius: radius.lg, padding: '18px 20px',
    boxShadow: shadow.xs, position: 'relative', overflow: 'hidden',
  },
  statBar: (col) => ({ position: 'absolute', left: 0, top: 0, bottom: 0, width: '3px', background: col, borderRadius: '3px 0 0 3px' }),
  statInner: { paddingLeft: '10px' },
  statVal: { fontFamily: fonts.mono, fontSize: '26px', fontWeight: 700, color: colors.gray900, lineHeight: 1, marginBottom: '5px' },
  statLbl: { fontSize: '11px', fontWeight: 700, color: colors.gray400, textTransform: 'uppercase', letterSpacing: '0.06em' },

  enrollBanner: (ok) => ({
    background: ok ? colors.successLight : '#fff8f0',
    border: `1px solid ${ok ? colors.successBorder : colors.accentBorder}`,
    borderLeft: `3px solid ${ok ? colors.successMid : colors.accent}`,
    borderRadius: `0 ${radius.lg} ${radius.lg} 0`,
    padding: '14px 20px', display: 'flex', alignItems: 'center',
    justifyContent: 'space-between', marginBottom: '24px', gap: '16px',
  }),
  enrollDot: (ok) => ({
    width: '8px', height: '8px', borderRadius: '50%', flexShrink: 0,
    background: ok ? colors.successMid : colors.accent,
  }),
  enrollTitle: (ok) => ({ fontWeight: 700, fontSize: '13px', color: ok ? colors.success : colors.accent, marginBottom: '2px' }),
  enrollSub: { fontSize: '12px', color: colors.gray500 },

  sectionLabel: {
    fontSize: '11px', fontWeight: 700, color: colors.gray400,
    textTransform: 'uppercase', letterSpacing: '0.08em',
    display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px',
  },
  sectionRule: { flex: 1, height: '1px', background: colors.gray200 },
  sectionCount: {
    background: colors.accentLight, color: colors.accent,
    border: `1px solid ${colors.accentBorder}`,
    borderRadius: '99px', padding: '1px 8px', fontSize: '10px', fontWeight: 700,
  },

  examCard: {
    background: colors.white, border: `1px solid ${colors.gray200}`,
    borderRadius: radius.lg, padding: '16px 20px',
    display: 'flex', alignItems: 'center', gap: '16px',
    marginBottom: '10px', boxShadow: shadow.xs,
    transition: 'box-shadow 0.18s, transform 0.18s, border-color 0.18s',
  },
  examIndicator: (active) => ({
    width: '10px', height: '10px', borderRadius: '50%', flexShrink: 0,
    background: active ? colors.successMid : colors.gray300,
    boxShadow: active ? '0 0 0 3px rgba(16,185,129,0.18)' : 'none',
  }),
  examTitle: { fontWeight: 700, fontSize: '15px', color: colors.gray900, letterSpacing: '-0.02em', marginBottom: '4px' },
  examMeta: { display: 'flex', gap: '14px', fontSize: '12px', color: colors.gray500, alignItems: 'center' },
  examStatusPill: (active) => ({
    display: 'inline-flex', alignItems: 'center', gap: '4px',
    padding: '2px 8px', borderRadius: '99px', fontSize: '10px', fontWeight: 700,
    background: active ? colors.successLight : colors.gray100,
    color: active ? colors.successMid : colors.gray400,
    border: `1px solid ${active ? colors.successBorder : colors.gray200}`,
    textTransform: 'uppercase', letterSpacing: '0.04em',
  }),

  histCard: {
    background: colors.white, border: `1px solid ${colors.gray200}`,
    borderRadius: radius.lg, padding: '13px 20px',
    display: 'flex', alignItems: 'center', gap: '14px',
    marginBottom: '8px', opacity: 0.88, boxShadow: shadow.xs,
  },
  histIcon: (status) => ({
    width: '32px', height: '32px', borderRadius: '50%', flexShrink: 0,
    background: status === 'completed' ? colors.successLight : colors.gray100,
    border: `1.5px solid ${status === 'completed' ? colors.successBorder : colors.gray200}`,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: '13px', color: status === 'completed' ? colors.successMid : colors.gray400,
    fontWeight: 700,
  }),
  histTitle: { fontWeight: 600, fontSize: '14px', color: colors.gray700, marginBottom: '3px' },
  histMeta: { fontSize: '11px', color: colors.gray400 },

  emptyBox: {
    background: colors.white, border: `1px solid ${colors.gray200}`,
    borderRadius: radius.lg, padding: '48px', textAlign: 'center',
    color: colors.gray400, fontSize: '13px', boxShadow: shadow.xs,
  },
};

function Navbar({ user, logout, navigate }) {
  return (
    <nav style={S.navbar}>
      <div style={S.navLeft}>
        <div style={S.navLogo}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
            <path d="M12 2L4 6v6c0 5.5 3.6 10.3 8 12 4.4-1.7 8-6.5 8-12V6L12 2z" fill="white" opacity=".95" />
          </svg>
        </div>
        <span style={S.navBrand}>ProctorAI</span>
        <span style={S.navTag}>Student</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span style={{ fontSize: '13px', color: colors.gray500, marginRight: '4px' }}>{user?.full_name}</span>
        <button style={btn.ghost} onClick={() => navigate('/enroll')}>Face Setup</button>
        <button style={btn.ghost} onClick={logout}>Sign Out</button>
      </div>
    </nav>
  );
}

export default function DashboardPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [allExams, setAllExams] = useState([]);
  const [enroll, setEnroll] = useState(null);
  const [loading, setLoad] = useState(true);
  const [starting, setStarting] = useState(null);

  useEffect(() => {
    Promise.all([examAPI.list(), authAPI.enrollStatus()])
      .then(([e, en]) => { setAllExams(e.data); setEnroll(en.data); })
      .catch(console.error)
      .finally(() => setLoad(false));
  }, []);

  const handleStart = async (examId) => {
    if (!enroll?.enrolled) { navigate('/enroll'); return; }
    setStarting(examId);
    try {
      const res = await examAPI.start(examId);
      navigate(`/room-scan/${examId}?session=${res.data.session_id}`);
    } catch (e) { alert(e.response?.data?.detail || 'Could not start exam.'); }
    finally { setStarting(null); }
  };

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
  const available = allExams.filter(e => ['scheduled', 'active'].includes(e.status));
  const history = allExams.filter(e => ['completed', 'terminated'].includes(e.status));

  return (
    <div style={S.page}>
      <Navbar user={user} logout={logout} navigate={navigate} />
      <div style={S.body}>

        {/* Hero */}
        <div style={S.hero}>
          <div style={S.heroGlow} />
          <div>
            <div style={S.heroGreeting}>
              {greeting}, <span style={S.heroAccent}>{user?.full_name?.split(' ')[0]}</span>
            </div>
            <div style={S.heroSub}>Here are your available exams and history.</div>
          </div>
          <div style={S.heroBadge}>
            <div style={S.heroBadgeVal}>{new Date().toLocaleDateString('en-IN', { day: 'numeric', month: 'short' })}</div>
            <div style={S.heroBadgeLbl}>{new Date().toLocaleDateString('en-IN', { weekday: 'long' })}</div>
          </div>
        </div>

        {/* Stats */}
        <div style={S.statRow}>
          {[
            { l: 'Available Exams', v: available.length, col: colors.blue },
            { l: 'Completed', v: history.length, col: colors.successMid },
            { l: 'Face Enrolled', v: enroll?.enrolled ? 'Yes' : 'No', col: enroll?.enrolled ? colors.successMid : colors.accent },
          ].map(({ l, v, col }) => (
            <div key={l} style={S.statCard} className="stat-card-shine">
              <div style={S.statBar(col)} />
              <div style={S.statInner}>
                <div style={S.statVal}>{v}</div>
                <div style={S.statLbl}>{l}</div>
              </div>
            </div>
          ))}
        </div>

        {/* Enrollment banner */}
        {enroll && (
          <div style={S.enrollBanner(enroll.enrolled)}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={S.enrollDot(enroll.enrolled)} />
              <div>
                <div style={S.enrollTitle(enroll.enrolled)}>
                  {enroll.enrolled ? 'Face enrollment complete' : 'Face enrollment required'}
                </div>
                <div style={S.enrollSub}>
                  {enroll.enrolled
                    ? 'Your face is registered. You may start any available exam.'
                    : 'Complete face enrollment before starting any exam.'}
                </div>
              </div>
            </div>
            {!enroll.enrolled && (
              <button className="btn-primary" onClick={() => navigate('/enroll')} style={{ flexShrink: 0 }}>
                Enroll Now
              </button>
            )}
          </div>
        )}

        {/* Available Exams */}
        <div style={S.sectionLabel}>
          Available Exams
          <div style={S.sectionRule} />
          <span style={S.sectionCount}>{available.length}</span>
        </div>

        {loading ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {[1, 2].map(i => <div key={i} style={{ ...S.examCard, height: '78px' }} className="skeleton" />)}
          </div>
        ) : available.length === 0 ? (
          <div style={S.emptyBox}>
            <div style={{ fontWeight: 600, marginBottom: '4px' }}>No exams available</div>
            <div style={{ fontSize: '12px' }}>Check back later or contact your administrator.</div>
          </div>
        ) : (
          available.map(exam => (
            <div key={exam.id} style={S.examCard} className="card-hover">
              <div style={S.examIndicator(exam.status === 'active')} />
              <div style={{ flex: 1 }}>
                <div style={S.examTitle}>{exam.title}</div>
                <div style={S.examMeta}>
                  <span>{exam.duration_minutes} min</span>
                  <span style={S.examStatusPill(exam.status === 'active')}>{exam.status}</span>
                </div>
              </div>
              <button className="btn-primary"
                style={{ opacity: starting === exam.id ? 0.6 : 1, cursor: starting === exam.id ? 'not-allowed' : 'pointer', minWidth: '108px' }}
                onClick={() => handleStart(exam.id)} disabled={starting === exam.id}>
                {starting === exam.id ? 'Starting…' : 'Start Exam'}
              </button>
            </div>
          ))
        )}

        {/* History */}
        {!loading && history.length > 0 && (
          <>
            <div style={{ ...S.sectionLabel, marginTop: '36px' }}>
              Exam History <div style={S.sectionRule} />
            </div>
            {history.map(exam => (
              <div key={exam.id} style={S.histCard}>
                <div style={S.histIcon(exam.status)}>{exam.status === 'completed' ? '✓' : '—'}</div>
                <div style={{ flex: 1 }}>
                  <div style={S.histTitle}>{exam.title}</div>
                  <div style={S.histMeta}>
                    {exam.duration_minutes} min
                    <span style={{ marginLeft: 8, textTransform: 'capitalize', color: exam.status === 'terminated' ? colors.dangerMid : colors.gray400 }}>
                      · {exam.status}
                    </span>
                  </div>
                </div>
                {exam.status === 'completed' && exam.last_session_id && (
                  <button style={{ ...btn.secondary, fontSize: '12px', padding: '6px 14px' }}
                    onClick={() => navigate(`/report?session=${exam.last_session_id}`)}>
                    View Report
                  </button>
                )}
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}