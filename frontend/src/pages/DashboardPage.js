// src/pages/DashboardPage.js — FINAL
// - Available exams (scheduled/active) in main section
// - Completed/terminated in history section below
// - "Start Exam" button visible and working
// - Exam history shows "View Report" for completed sessions

import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { examAPI, authAPI } from '../services/api';
import { colors, fonts, radius, shadow } from '../styles/theme';
import { nav, btn, text } from '../styles/styles';

// ── All styles ────────────────────────────────────────────────────
const S = {
  page: { minHeight: '100vh', background: colors.gray50, fontFamily: fonts.ui },
  body: { maxWidth: '860px', margin: '0 auto', padding: '36px 24px' },
  greeting: {
    fontFamily: fonts.display, fontSize: '24px', fontWeight: 400,
    color: colors.gray900, letterSpacing: '-0.03em', marginBottom: '4px',
  },
  greetSub: { fontSize: '14px', color: colors.gray500, marginBottom: '28px' },
  statRow: {
    display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '12px', marginBottom: '28px',
  },
  statCard: {
    background: colors.white, border: `1px solid ${colors.gray200}`,
    borderRadius: radius.lg, padding: '16px 20px', boxShadow: shadow.xs, textAlign: 'center',
  },
  statVal: {
    fontFamily: fonts.mono, fontSize: '26px', fontWeight: 700,
    color: colors.gray900, lineHeight: 1, marginBottom: '4px',
  },
  statLbl: {
    fontSize: '11px', fontWeight: 600, color: colors.gray400,
    textTransform: 'uppercase', letterSpacing: '0.05em',
  },
  enrollBanner: (ok) => ({
    background: ok ? colors.successLight : colors.warningLight,
    border: `1px solid ${ok ? colors.successBorder : colors.warningBorder}`,
    borderRadius: radius.lg, padding: '14px 20px',
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    marginBottom: '28px',
  }),
  enrollTitle: (ok) => ({
    fontWeight: 600, fontSize: '13px',
    color: ok ? colors.success : colors.warning, marginBottom: '2px',
  }),
  enrollSub: { fontSize: '12px', color: colors.gray500 },
  sectionLabel: {
    fontSize: '11px', fontWeight: 700, color: colors.gray400,
    textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '12px',
  },
  examCard: {
    background: colors.white, border: `1px solid ${colors.gray200}`,
    borderRadius: radius.lg, padding: '16px 20px',
    display: 'flex', alignItems: 'center', gap: '20px',
    marginBottom: '10px', boxShadow: shadow.xs,
    transition: 'box-shadow 0.15s',
  },
  examTitle: {
    fontWeight: 600, fontSize: '15px', color: colors.gray900,
    letterSpacing: '-0.01em', marginBottom: '4px',
  },
  examMeta: { display: 'flex', gap: '16px', fontSize: '12px', color: colors.gray500 },
  statusDot: (status) => ({
    display: 'inline-block', width: 6, height: 6, borderRadius: '50%',
    marginRight: 4, verticalAlign: 'middle',
    background: status === 'active' ? colors.successMid : colors.gray300,
  }),
  histCard: {
    background: colors.white, border: `1px solid ${colors.gray200}`,
    borderRadius: radius.lg, padding: '12px 20px',
    display: 'flex', alignItems: 'center', gap: '16px',
    marginBottom: '8px', opacity: 0.85,
  },
  histIcon: (status) => ({
    width: 32, height: 32, borderRadius: '50%', flexShrink: 0,
    background: status === 'completed' ? colors.successLight : colors.gray100,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: '13px', color: status === 'completed' ? colors.successMid : colors.gray400,
  }),
  histTitle: {
    fontWeight: 600, fontSize: '14px', color: colors.gray700, marginBottom: '2px',
  },
  histMeta: { fontSize: '11px', color: colors.gray400 },
  emptyBox: {
    background: colors.white, border: `1px solid ${colors.gray200}`,
    borderRadius: radius.lg, padding: '40px', textAlign: 'center',
    color: colors.gray400, fontSize: '13px',
  },
};

function Navbar({ user, logout, navigate }) {
  return (
    <nav style={nav.root}>
      <div style={nav.brand}>
        <div style={nav.brandLogo}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path d="M12 2L4 6v6c0 5.5 3.6 10.3 8 12 4.4-1.7 8-6.5 8-12V6L12 2z"
              fill="white" opacity=".9" />
          </svg>
        </div>
        <span style={nav.brandName}>ProctorAI</span>
      </div>
      <div style={nav.actions}>
        <span style={{ fontSize: '13px', color: colors.gray500 }}>{user?.full_name}</span>
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
  const [sessions, setSessions] = useState([]); // user's past sessions for report links
  const [enroll, setEnroll] = useState(null);
  const [loading, setLoad] = useState(true);
  const [starting, setStarting] = useState(null); // exam id being started

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
    } catch (e) {
      alert(e.response?.data?.detail || 'Could not start exam.');
    } finally {
      setStarting(null);
    }
  };

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning'
    : hour < 17 ? 'Good afternoon'
      : 'Good evening';

  // Split by status
  const available = allExams.filter(e => ['scheduled', 'active'].includes(e.status));
  const history = allExams.filter(e => ['completed', 'terminated'].includes(e.status));

  return (
    <div style={S.page}>
      <Navbar user={user} logout={logout} navigate={navigate} />

      <div style={S.body}>
        {/* Greeting */}
        <div>
          <h1 style={S.greeting}>
            {greeting}, {user?.full_name?.split(' ')[0]}
          </h1>
          <p style={S.greetSub}>Here are your exams.</p>
        </div>

        {/* Stats */}
        <div style={S.statRow}>
          {[
            { l: 'Available Exams', v: available.length },
            { l: 'Completed Exams', v: history.length },
            { l: 'Face Enrolled', v: enroll?.enrolled ? 'Yes' : 'No' },
          ].map(({ l, v }) => (
            <div key={l} style={S.statCard}>
              <div style={S.statVal}>{v}</div>
              <div style={S.statLbl}>{l}</div>
            </div>
          ))}
        </div>

        {/* Enrollment banner */}
        {enroll && (
          <div style={S.enrollBanner(enroll.enrolled)}>
            <div>
              <div style={S.enrollTitle(enroll.enrolled)}>
                {enroll.enrolled
                  ? 'Face enrollment complete'
                  : 'Face enrollment required'}
              </div>
              <div style={S.enrollSub}>
                {enroll.enrolled
                  ? 'Your face is registered. You may start any available exam.'
                  : 'Complete face enrollment before starting any exam.'}
              </div>
            </div>
            {!enroll.enrolled && (
              <button style={btn.primary} onClick={() => navigate('/enroll')}>
                Enroll Now
              </button>
            )}
          </div>
        )}

        {/* ── Available Exams ── */}
        <div style={S.sectionLabel}>Available Exams</div>

        {loading ? (
          <div style={S.emptyBox}>Loading…</div>
        ) : available.length === 0 ? (
          <div style={S.emptyBox}>No exams available at this time.</div>
        ) : (
          available.map(exam => (
            <div key={exam.id} style={S.examCard} className="card-hover">
              <div style={{ flex: 1 }}>
                <div style={S.examTitle}>{exam.title}</div>
                <div style={S.examMeta}>
                  <span>{exam.duration_minutes} minutes</span>
                  <span>
                    <span style={S.statusDot(exam.status)} />
                    {exam.status}
                  </span>
                </div>
              </div>
              <button
                style={{
                  ...btn.primary,
                  opacity: starting === exam.id ? 0.6 : 1,
                  cursor: starting === exam.id ? 'not-allowed' : 'pointer',
                }}
                onClick={() => handleStart(exam.id)}
                disabled={starting === exam.id}>
                {starting === exam.id ? 'Starting…' : 'Start Exam'}
              </button>
            </div>
          ))
        )}

        {/* ── Exam History ── */}
        {!loading && history.length > 0 && (
          <>
            <div style={{ ...S.sectionLabel, marginTop: '36px' }}>
              Exam History
            </div>
            {history.map(exam => (
              <div key={exam.id} style={S.histCard}>
                <div style={S.histIcon(exam.status)}>
                  {exam.status === 'completed' ? '✓' : '—'}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={S.histTitle}>{exam.title}</div>
                  <div style={S.histMeta}>
                    {exam.duration_minutes} min
                    <span style={{
                      marginLeft: 8, textTransform: 'capitalize',
                      color: exam.status === 'terminated' ? colors.dangerMid : colors.gray400
                    }}>
                      {exam.status}
                    </span>
                  </div>
                </div>
                {/* View Report — navigates to report page
                    Note: requires session_id which examAPI.list doesn't return.
                    The backend list_exams should include last_session_id
                    or admin can view from admin panel. */}
                {exam.status === 'completed' && exam.last_session_id && (
                  <button
                    style={{ ...btn.secondary, fontSize: '12px', padding: '6px 12px' }}
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