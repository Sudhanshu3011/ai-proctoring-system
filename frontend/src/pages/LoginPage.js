// src/pages/LoginPage.js — ProctorAI Premium

import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { authAPI } from '../services/api';
import { colors, fonts, radius } from '../styles/theme';
import { btn, form } from '../styles/styles';

const S = {
  page: { minHeight: '100vh', display: 'flex', fontFamily: fonts.ui, background: colors.gray50 },

  left: {
    width: '46%',
    background: 'linear-gradient(160deg, #0a1628 0%, #0f2040 45%, #162d58 100%)',
    display: 'flex', flexDirection: 'column', justifyContent: 'space-between',
    padding: '44px 52px', position: 'relative', overflow: 'hidden',
  },
  leftGlow: {
    position: 'absolute', inset: 0, pointerEvents: 'none',
    background: 'radial-gradient(ellipse at 15% 85%, rgba(249,115,22,0.14) 0%, transparent 60%)',
  },

  logo: { display: 'flex', alignItems: 'center', gap: '12px', position: 'relative' },
  logoIcon: {
    width: '40px', height: '40px',
    background: 'linear-gradient(135deg, #f97316 0%, #ea6a08 100%)',
    borderRadius: '10px',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    boxShadow: '0 4px 16px rgba(249,115,22,0.35)',
  },
  logoName: { fontFamily: fonts.display, fontSize: '22px', fontWeight: 700, color: colors.white, letterSpacing: '-0.02em' },
  logoBadge: {
    fontSize: '9px', fontWeight: 700, letterSpacing: '0.06em', color: 'rgba(255,255,255,0.45)',
    border: '1px solid rgba(255,255,255,0.15)', borderRadius: '4px', padding: '2px 6px',
    textTransform: 'uppercase', marginLeft: '4px',
  },

  h1: {
    fontFamily: fonts.display, fontSize: '40px', fontWeight: 700,
    lineHeight: 1.05, letterSpacing: '-0.04em', color: colors.white, marginBottom: '18px',
  },
  h1Accent: {
    background: 'linear-gradient(135deg, #f97316 0%, #fb923c 100%)',
    WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text',
  },
  sub: { fontSize: '14px', color: 'rgba(255,255,255,0.52)', lineHeight: 1.75, maxWidth: '300px' },

  featureItem: { display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' },
  featureDot: { width: '4px', height: '4px', borderRadius: '50%', background: 'rgba(249,115,22,0.7)', flexShrink: 0 },
  featureText: { fontSize: '13px', color: 'rgba(255,255,255,0.62)' },

  statRow: {
    display: 'flex', gap: '28px',
    borderTop: '1px solid rgba(255,255,255,0.08)',
    paddingTop: '24px', marginTop: '4px',
  },
  statVal: { fontFamily: fonts.display, fontSize: '22px', fontWeight: 700, color: colors.white, letterSpacing: '-0.03em' },
  statLbl: { fontSize: '11px', color: 'rgba(255,255,255,0.38)', marginTop: '2px', fontWeight: 500 },

  right: { flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '40px 48px', background: colors.gray50 },
  panel: { width: '100%', maxWidth: '380px' },
  panelTitle: { fontFamily: fonts.display, fontSize: '26px', fontWeight: 700, color: colors.gray900, letterSpacing: '-0.03em', marginBottom: '6px' },
  panelSub: { fontSize: '14px', color: colors.gray500, marginBottom: '32px' },

  tabs: {
    display: 'grid', gridTemplateColumns: '1fr 1fr',
    background: colors.gray100, borderRadius: radius.md,
    padding: '3px', marginBottom: '28px', gap: '3px',
  },
  tab: (active) => ({
    fontFamily: fonts.ui, fontWeight: active ? 700 : 500,
    fontSize: '13px', border: 'none', borderRadius: '8px', padding: '9px', cursor: 'pointer',
    background: active ? 'linear-gradient(135deg, #f97316 0%, #ea6a08 100%)' : 'transparent',
    color: active ? colors.white : colors.gray500,
    boxShadow: active ? '0 2px 8px rgba(249,115,22,0.28)' : 'none',
    transition: 'all 0.18s ease',
  }),

  footer: { marginTop: '28px', fontSize: '11px', color: colors.gray400, textAlign: 'center', lineHeight: 1.6 },
  footerDot: { display: 'inline-block', width: '3px', height: '3px', borderRadius: '50%', background: colors.gray300, margin: '0 8px', verticalAlign: 'middle' },
};

const FEATURES = [
  'AI face recognition and liveness detection',
  'Real-time behaviour anomaly scoring',
  'Multi-signal audio and gaze monitoring',
  'Automated integrity reports',
];

const STATS = [
  { val: '99.2%', lbl: 'Detection accuracy' },
  { val: '<80ms', lbl: 'Analysis latency' },
  { val: '18+', lbl: 'Violation signals' },
];

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
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
    } catch (e) { setError(e.response?.data?.detail || 'Invalid email or password.'); }
    finally { setLoad(false); }
  };

  const handleRegister = async () => {
    setError(''); setLoad(true);
    try { await authAPI.register(form_); setTab('login'); setError(''); }
    catch (e) {
      const errs = e.response?.data?.errors;
      setError(errs ? errs.map((x) => x.message).join(', ') : e.response?.data?.detail || 'Registration failed.');
    } finally { setLoad(false); }
  };

  const handleKey = (e) => { if (e.key === 'Enter' && tab === 'login') handleLogin(); };

  return (
    <div style={S.page}>
      <div style={S.left}>
        <div style={S.leftGlow} />
        <div style={S.logo}>
          <div style={S.logoIcon}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L4 6v6c0 5.5 3.6 10.3 8 12 4.4-1.7 8-6.5 8-12V6L12 2z" fill="white" opacity=".95" />
            </svg>
          </div>
          <div>
            <span style={S.logoName}>ProctorAI</span>
            <span style={S.logoBadge}>v2.0</span>
          </div>
        </div>

        <div>
          <h1 style={S.h1}>
            Intelligent<br />
            <span style={S.h1Accent}>Exam Integrity</span><br />
            Platform
          </h1>
          <p style={S.sub}>
            AI-powered proctoring that protects academic integrity
            without disrupting the student experience.
          </p>
        </div>

        <div>
          {FEATURES.map((f) => (
            <div key={f} style={S.featureItem}>
              <div style={S.featureDot} />
              <span style={S.featureText}>{f}</span>
            </div>
          ))}
          <div style={S.statRow}>
            {STATS.map((s) => (
              <div key={s.val}>
                <div style={S.statVal}>{s.val}</div>
                <div style={S.statLbl}>{s.lbl}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={S.right}>
        <div style={S.panel} className="animate-fade-up">
          <h2 style={S.panelTitle}>{tab === 'login' ? 'Welcome back' : 'Create account'}</h2>
          <p style={S.panelSub}>{tab === 'login' ? 'Sign in to access your exams and reports.' : 'Register to get started with ProctorAI.'}</p>

          <div style={S.tabs}>
            {['login', 'register'].map((t) => (
              <button key={t} style={S.tab(tab === t)} onClick={() => { setTab(t); setError(''); }}>
                {t === 'login' ? 'Sign In' : 'Register'}
              </button>
            ))}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {tab === 'register' && (
              <div>
                <label style={form.label}>Full Name</label>
                <div style={{ height: '6px' }} />
                <input style={form.input} placeholder="Your full name" value={form_.full_name} onChange={set('full_name')} />
              </div>
            )}
            <div>
              <label style={form.label}>Email Address</label>
              <div style={{ height: '6px' }} />
              <input style={form.input} type="email" placeholder="you@university.edu" value={form_.email} onChange={set('email')} onKeyDown={handleKey} />
            </div>
            <div>
              <label style={form.label}>Password</label>
              <div style={{ height: '6px' }} />
              <input style={form.input} type="password" placeholder="••••••••" value={form_.password} onChange={set('password')} onKeyDown={handleKey} />
            </div>
            {tab === 'register' && (
              <div>
                <label style={form.label}>Role</label>
                <div style={{ height: '6px' }} />
                <select style={form.select} value={form_.role} onChange={set('role')}>
                  <option value="student">Student</option>
                  <option value="admin">Administrator</option>
                </select>
              </div>
            )}
            {error && (
              <div style={form.error}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0, marginTop: '1px' }}>
                  <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
                  <line x1="12" y1="8" x2="12" y2="12" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                  <circle cx="12" cy="16" r="1" fill="currentColor" />
                </svg>
                {error}
              </div>
            )}
            <button className="btn-primary" style={{ width: '100%', padding: '12px', marginTop: '4px' }}
              onClick={tab === 'login' ? handleLogin : handleRegister} disabled={loading}>
              {loading ? 'Please wait…' : tab === 'login' ? 'Sign In' : 'Create Account'}
            </button>
          </div>

          <div style={S.footer}>
            <span>Secure</span><span style={S.footerDot} /><span>AI-Monitored</span><span style={S.footerDot} /><span>Confidential</span>
          </div>
        </div>
      </div>
    </div>
  );
}