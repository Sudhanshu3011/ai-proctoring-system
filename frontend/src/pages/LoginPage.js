// src/pages/LoginPage.js
// Logic: auth state, form submission
// Styles: imported from styles.js / theme.js

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { authAPI } from '../services/api';
import { colors, fonts, shadow, radius } from '../styles/theme';
import { btn, form, text, card } from '../styles/styles';

// ── Styles (all presentation, no logic) ──────────────────────────
const S = {
  page: {
    minHeight: '100vh',
    background: colors.gray50,
    display: 'flex',
    fontFamily: fonts.ui,
  },
  left: {
    width: '42%',
    background: colors.brand,
    padding: '48px',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
    position: 'relative',
    overflow: 'hidden',
  },
  leftPattern: {
    position: 'absolute', inset: 0, pointerEvents: 'none',
    backgroundImage: 'radial-gradient(circle at 20% 80%, rgba(255,255,255,0.06) 0%, transparent 50%), radial-gradient(circle at 80% 20%, rgba(255,255,255,0.04) 0%, transparent 50%)',
  },
  leftLogo: {
    display: 'flex', alignItems: 'center', gap: '12px', position: 'relative',
  },
  leftLogoIcon: {
    width: '40px', height: '40px', background: 'rgba(255,255,255,0.15)',
    borderRadius: radius.md, display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  leftLogoText: {
    fontFamily: fonts.display, fontSize: '22px', color: colors.white,
    fontWeight: 400, letterSpacing: '-0.02em',
  },
  leftHeadline: {
    position: 'relative',
  },
  leftH1: {
    fontFamily: fonts.display, fontSize: '38px', color: colors.white,
    fontWeight: 400, lineHeight: 1.1, letterSpacing: '-0.03em', marginBottom: '16px',
  },
  leftSub: {
    fontSize: '14px', color: 'rgba(255,255,255,0.65)', lineHeight: 1.7,
    maxWidth: '320px',
  },
  leftFeature: {
    display: 'flex', alignItems: 'center', gap: '10px',
    marginBottom: '10px',
  },
  leftFeatureDot: {
    width: '6px', height: '6px', borderRadius: '50%',
    background: 'rgba(255,255,255,0.5)', flexShrink: 0,
  },
  leftFeatureText: {
    fontSize: '13px', color: 'rgba(255,255,255,0.7)',
  },
  right: {
    flex: 1, display: 'flex', alignItems: 'center',
    justifyContent: 'center', padding: '48px',
  },
  panel: {
    width: '100%', maxWidth: '380px',
  },
  panelHead: {
    marginBottom: '28px',
  },
  panelTitle: {
    fontFamily: fonts.display, fontSize: '24px', color: colors.gray900,
    fontWeight: 400, letterSpacing: '-0.03em', marginBottom: '6px',
  },
  panelSub: {
    fontSize: '14px', color: colors.gray500,
  },
  tabs: {
    display: 'grid', gridTemplateColumns: '1fr 1fr',
    background: colors.gray100, borderRadius: radius.md,
    padding: '3px', marginBottom: '24px', gap: '3px',
  },
  tab: (active) => ({
    fontFamily: fonts.ui, fontWeight: active ? 600 : 400,
    fontSize: '13px', border: 'none', borderRadius: '6px',
    padding: '8px', cursor: 'pointer',
    background: active ? colors.white : 'transparent',
    color: active ? colors.gray900 : colors.gray500,
    boxShadow: active ? shadow.xs : 'none',
    transition: 'all 0.15s',
  }),
  divider: {
    height: '1px', background: colors.gray200, margin: '20px 0',
  },
  footer: {
    marginTop: '24px', fontSize: '12px', color: colors.gray400,
    textAlign: 'center', lineHeight: 1.5,
  },
};

const FEATURES = [
  'AI-powered face recognition and liveness detection',
  'Real-time behaviour anomaly scoring',
  'Multi-signal audio and gaze monitoring',
  'Automated integrity reports',
];

// ── Component (all logic, no inline style literals) ───────────────
export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();

  // Logic state
  const [tab, setTab] = useState('login');
  const [form_, setForm] = useState({ email: '', password: '', full_name: '', role: 'student' });
  const [error, setError] = useState('');
  const [loading, setLoad] = useState(false);

  const set = (k) => (e) => setForm((p) => ({ ...p, [k]: e.target.value }));

  const handleLogin = async () => {
    setError(''); setLoad(true);
    try {
      const data = await login(form_.email, form_.password);
      navigate(data.role === 'admin' ? '/admin' : '/dashboard');
    } catch (e) {
      setError(e.response?.data?.detail || 'Invalid email or password.');
    } finally { setLoad(false); }
  };

  const handleRegister = async () => {
    setError(''); setLoad(true);
    try {
      await authAPI.register(form_);
      setTab('login');
      setError('');
    } catch (e) {
      const errs = e.response?.data?.errors;
      setError(errs ? errs.map((x) => x.message).join(', ') : e.response?.data?.detail || 'Registration failed.');
    } finally { setLoad(false); }
  };

  const handleKey = (e) => {
    if (e.key === 'Enter' && tab === 'login') handleLogin();
  };

  return (
    <div style={S.page}>
      {/* Left panel — brand */}
      <div style={S.left}>
        <div style={S.leftPattern} />
        <div style={S.leftLogo}>
          <div style={S.leftLogoIcon}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L4 6v6c0 5.5 3.6 10.3 8 12 4.4-1.7 8-6.5 8-12V6L12 2z" fill="white" opacity=".9" />
            </svg>
          </div>
          <span style={S.leftLogoText}>ProctorAI</span>
        </div>

        <div style={S.leftHeadline}>
          <h1 style={S.leftH1}>Intelligent<br />Exam<br />Integrity</h1>
          <p style={S.leftSub}>
            AI-powered proctoring that protects academic integrity without disrupting the student experience.
          </p>
        </div>

        <div>
          {FEATURES.map((f) => (
            <div key={f} style={S.leftFeature}>
              <div style={S.leftFeatureDot} />
              <span style={S.leftFeatureText}>{f}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Right panel — form */}
      <div style={S.right}>
        <div style={S.panel} className="animate-fade-up">
          <div style={S.panelHead}>
            <h2 style={S.panelTitle}>
              {tab === 'login' ? 'Welcome back' : 'Create account'}
            </h2>
            <p style={S.panelSub}>
              {tab === 'login' ? 'Sign in to access your exams.' : 'Register to get started.'}
            </p>
          </div>

          {/* Tabs */}
          <div style={S.tabs}>
            {['login', 'register'].map((t) => (
              <button key={t} style={S.tab(tab === t)}
                onClick={() => { setTab(t); setError(''); }}>
                {t === 'login' ? 'Sign In' : 'Register'}
              </button>
            ))}
          </div>

          {/* Fields */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {tab === 'register' && (
              <div>
                <label style={form.label}>Full Name</label>
                <div style={{ height: '4px' }} />
                <input style={form.input} placeholder="Your full name"
                  value={form_.full_name} onChange={set('full_name')} />
              </div>
            )}

            <div>
              <label style={form.label}>Email Address</label>
              <div style={{ height: '4px' }} />
              <input style={form.input} type="email" placeholder="you@university.edu"
                value={form_.email} onChange={set('email')} onKeyDown={handleKey} />
            </div>

            <div>
              <label style={form.label}>Password</label>
              <div style={{ height: '4px' }} />
              <input style={form.input} type="password" placeholder="••••••••"
                value={form_.password} onChange={set('password')} onKeyDown={handleKey} />
            </div>

            {tab === 'register' && (
              <div>
                <label style={form.label}>Role</label>
                <div style={{ height: '4px' }} />
                <select style={form.select} value={form_.role} onChange={set('role')}>
                  <option value="student">Student</option>
                  <option value="admin">Administrator</option>
                </select>
              </div>
            )}

            {error && <div style={form.error}>{error}</div>}

            <button
              className="btn-primary"
              style={{ ...btn.primary, width: '100%', padding: '11px', marginTop: '4px' }}
              onClick={tab === 'login' ? handleLogin : handleRegister}
              disabled={loading}>
              {loading ? 'Please wait…' : tab === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </div>

          <div style={S.footer}>
            Secure · AI-Monitored · Confidential
          </div>
        </div>
      </div>
    </div>
  );
}