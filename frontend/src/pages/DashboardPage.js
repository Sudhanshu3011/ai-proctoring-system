// src/pages/DashboardPage.js
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { examAPI, authAPI } from '../services/api';
import { colors, fonts, radius, shadow } from '../styles/theme';
import { nav, card, btn, text, badge, statusPill, layout } from '../styles/styles';

// ── Styles ────────────────────────────────────────────────────────
const S = {
  enrollBanner: (enrolled) => ({
    background: enrolled ? colors.successLight : colors.warningLight,
    border: `1px solid ${enrolled ? colors.successBorder : colors.warningBorder}`,
    borderRadius: radius.lg,
    padding: '14px 20px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: '20px',
  }),
  enrollText: (enrolled) => ({
    fontFamily: fonts.ui,
    fontSize: '13px',
    fontWeight: 600,
    color: enrolled ? colors.success : colors.warning,
    marginBottom: '2px',
  }),
  enrollSub: {
    fontSize: '12px',
    color: colors.gray500,
  },
  examRow: {
    ...card.base,
    display: 'flex',
    alignItems: 'center',
    gap: '20px',
    marginBottom: '10px',
    transition: 'box-shadow 0.2s',
  },
  examMeta: {
    display: 'flex', gap: '16px',
    fontSize: '12px', color: colors.gray500,
    marginTop: '4px',
  },
  statCard: {
    ...card.compact,
    textAlign: 'center',
  },
  statValue: {
    fontFamily: fonts.mono,
    fontSize: '28px',
    fontWeight: 600,
    color: colors.gray900,
    lineHeight: 1,
  },
  statLabel: {
    fontSize: '11px',
    color: colors.gray400,
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginTop: '4px',
  },
};

// ── Navbar (shared) ───────────────────────────────────────────────
function Navbar({ user, logout, navigate }) {
  return (
    <nav style={nav.root}>
      <div style={nav.brand}>
        <div style={nav.brandLogo}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path d="M12 2L4 6v6c0 5.5 3.6 10.3 8 12 4.4-1.7 8-6.5 8-12V6L12 2z" fill="white" opacity=".9" />
          </svg>
        </div>
        <span style={nav.brandName}>ProctorAI</span>
      </div>
      <div style={nav.actions}>
        <span style={{ fontSize: '13px', color: colors.gray500 }}>{user?.full_name}</span>
        <button className="btn-ghost" style={btn.ghost}
          onClick={() => navigate('/enroll')}>
          Face Setup
        </button>
        <button className="btn-ghost" style={btn.ghost} onClick={logout}>
          Sign Out
        </button>
      </div>
    </nav>
  );
}

// ── Component ─────────────────────────────────────────────────────
export default function DashboardPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [exams, setExams] = useState([]);
  const [enroll, setEnroll] = useState(null);
  const [loading, setLoad] = useState(true);

  useEffect(() => {
    Promise.all([examAPI.list(), authAPI.enrollStatus()])
      .then(([e, en]) => { setExams(e.data); setEnroll(en.data); })
      .catch(console.error)
      .finally(() => setLoad(false));
  }, []);

  const handleStart = async (examId) => {
    if (!enroll?.enrolled) { navigate('/enroll'); return; }
    try {
      const res = await examAPI.start(examId);
      navigate(`/room-scan/${examId}?session=${res.data.session_id}`);
    } catch (e) {
      alert(e.response?.data?.detail || 'Could not start exam.');
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: colors.gray50, fontFamily: fonts.ui }}>
      <Navbar user={user} logout={logout} navigate={navigate} />

      <div style={layout.container}>
        {/* Header */}
        <div style={{ marginBottom: '28px' }}>
          <h1 style={text.pageTitle}>
            Good {new Date().getHours() < 12 ? 'morning' : 'afternoon'}, {user?.full_name?.split(' ')[0]}
          </h1>
          <p style={text.body}>Here are your available exams.</p>
        </div>

        {/* Stats row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '12px', marginBottom: '28px' }}>
          {[
            { label: 'Available Exams', value: exams.length },
            { label: 'Face Enrolled', value: enroll?.enrolled ? 'Yes' : 'No' },
            { label: 'Account Status', value: 'Active' },
          ].map(({ label, value }) => (
            <div key={label} style={S.statCard}>
              <div style={S.statValue}>{value}</div>
              <div style={S.statLabel}>{label}</div>
            </div>
          ))}
        </div>

        {/* Enrollment banner */}
        {enroll && (
          <div style={S.enrollBanner(enroll.enrolled)}>
            <div>
              <div style={S.enrollText(enroll.enrolled)}>
                {enroll.enrolled ? 'Face enrollment complete' : 'Face enrollment required'}
              </div>
              <div style={S.enrollSub}>
                {enroll.enrolled
                  ? 'Your face is registered. You may start any exam below.'
                  : 'Complete face enrollment before starting any exam.'}
              </div>
            </div>
            {!enroll.enrolled && (
              <button className="btn-primary" style={btn.primary}
                onClick={() => navigate('/enroll')}>
                Enroll Now
              </button>
            )}
          </div>
        )}

        {/* Exam list */}
        <div style={{ marginBottom: '8px' }}>
          <div style={text.sectionTitle}>Available Exams</div>
        </div>

        {loading ? (
          <div style={{ ...card.base, textAlign: 'center', padding: '40px', color: colors.gray400 }}>
            Loading…
          </div>
        ) : exams.length === 0 ? (
          <div style={{ ...card.base, textAlign: 'center', padding: '48px' }}>
            <div style={{ fontSize: '32px', marginBottom: '12px', opacity: 0.3 }}>&#9633;</div>
            <div style={{ ...text.body, color: colors.gray400 }}>No exams available at this time.</div>
          </div>
        ) : (
          exams.map((exam) => (
            <div key={exam.id} style={S.examRow} className="card-hover">
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: '15px', color: colors.gray900, letterSpacing: '-0.01em', marginBottom: '4px' }}>
                  {exam.title}
                </div>
                <div style={S.examMeta}>
                  <span>{exam.duration_minutes} minutes</span>
                  <span style={{ color: exam.status === 'active' ? colors.successMid : colors.gray400 }}>
                    {exam.status}
                  </span>
                </div>
              </div>
              <button className="btn-primary" style={btn.primary}
                onClick={() => handleStart(exam.id)}>
                Start Exam
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}