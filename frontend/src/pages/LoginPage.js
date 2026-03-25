// src/pages/LoginPage.js
import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { authAPI } from '../services/api';

export default function LoginPage() {
  const { login }    = useAuth();
  const navigate     = useNavigate();
  const [tab,  setTab]    = useState('login');    // 'login' | 'register'
  const [form, setForm]   = useState({ email:'', password:'', full_name:'', role:'student' });
  const [error,setError]  = useState('');
  const [loading,setLoad] = useState(false);

  const set = k => e => setForm(p => ({ ...p, [k]: e.target.value }));

  const handleLogin = async () => {
    setError(''); setLoad(true);
    try {
      const data = await login(form.email, form.password);
      navigate(data.role === 'admin' ? '/admin' : '/dashboard');
    } catch (e) {
      setError(e.response?.data?.detail || 'Login failed');
    } finally { setLoad(false); }
  };

  const handleRegister = async () => {
    setError(''); setLoad(true);
    try {
      await authAPI.register(form);
      setTab('login');
      setError('');
      setForm(p => ({ ...p, full_name: '' }));
    } catch (e) {
      setError(e.response?.data?.detail || 'Registration failed');
    } finally { setLoad(false); }
  };

  return (
    <div style={{
      minHeight:'100vh', display:'flex', alignItems:'center',
      justifyContent:'center', padding:'20px',
      background:'radial-gradient(ellipse at 20% 50%, #0a1628 0%, #080c14 60%)',
    }}>
      {/* Decorative grid lines */}
      <div style={{
        position:'fixed', inset:0, pointerEvents:'none',
        backgroundImage:'linear-gradient(var(--border) 1px, transparent 1px), linear-gradient(90deg, var(--border) 1px, transparent 1px)',
        backgroundSize:'60px 60px', opacity:0.15,
      }}/>

      <div style={{ width:'100%', maxWidth:'420px', position:'relative' }}>
        {/* Logo */}
        <div style={{ textAlign:'center', marginBottom:'32px' }}>
          <div style={{
            width:52, height:52, borderRadius:'14px',
            background:'linear-gradient(135deg, #1d4ed8, #0ea5e9)',
            display:'flex', alignItems:'center', justifyContent:'center',
            margin:'0 auto 16px', fontSize:'24px',
          }}>🔒</div>
          <h1 style={{ fontSize:'24px', fontFamily:'Syne', color:'var(--text)' }}>
            ProctorAI
          </h1>
          <p style={{ color:'var(--muted)', fontSize:'12px', marginTop:'4px' }}>
            Intelligent Exam Monitoring System
          </p>
        </div>

        <div className="card animate-in">
          {/* Tabs */}
          <div style={{
            display:'grid', gridTemplateColumns:'1fr 1fr',
            gap:'4px', background:'var(--bg)', borderRadius:'8px',
            padding:'4px', marginBottom:'24px',
          }}>
            {['login','register'].map(t => (
              <button key={t} onClick={() => { setTab(t); setError(''); }}
                style={{
                  background: tab === t ? 'var(--bg3)' : 'transparent',
                  color: tab === t ? 'var(--text)' : 'var(--muted)',
                  border:'none', borderRadius:'6px', padding:'8px',
                  fontSize:'13px', fontFamily:'Syne', fontWeight:600,
                  transition:'all 0.2s',
                }}>
                {t === 'login' ? 'Sign In' : 'Register'}
              </button>
            ))}
          </div>

          {/* Form fields */}
          <div style={{ display:'flex', flexDirection:'column', gap:'12px' }}>
            {tab === 'register' && (
              <div>
                <label style={{ color:'var(--muted)', fontSize:'11px', marginBottom:'4px', display:'block' }}>
                  FULL NAME
                </label>
                <input
                  placeholder="Your full name"
                  value={form.full_name}
                  onChange={set('full_name')}
                />
              </div>
            )}

            <div>
              <label style={{ color:'var(--muted)', fontSize:'11px', marginBottom:'4px', display:'block' }}>
                EMAIL
              </label>
              <input
                type="email"
                placeholder="you@example.com"
                value={form.email}
                onChange={set('email')}
                onKeyDown={e => e.key === 'Enter' && tab === 'login' && handleLogin()}
              />
            </div>

            <div>
              <label style={{ color:'var(--muted)', fontSize:'11px', marginBottom:'4px', display:'block' }}>
                PASSWORD
              </label>
              <input
                type="password"
                placeholder="••••••••"
                value={form.password}
                onChange={set('password')}
                onKeyDown={e => e.key === 'Enter' && tab === 'login' && handleLogin()}
              />
            </div>

            {tab === 'register' && (
              <div>
                <label style={{ color:'var(--muted)', fontSize:'11px', marginBottom:'4px', display:'block' }}>
                  ROLE
                </label>
                <select value={form.role} onChange={set('role')}>
                  <option value="student">Student</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
            )}

            {error && (
              <div style={{
                background:'#1f0a0a', border:'1px solid #7f1d1d',
                borderRadius:'8px', padding:'10px 14px',
                color:'#f87171', fontSize:'12px',
              }}>
                {error}
              </div>
            )}

            <button
              className="btn-primary"
              style={{ marginTop:'8px', padding:'12px', fontSize:'14px' }}
              onClick={tab === 'login' ? handleLogin : handleRegister}
              disabled={loading}
            >
              {loading ? 'Please wait...' : tab === 'login' ? 'Sign In →' : 'Create Account →'}
            </button>
          </div>
        </div>

        <p style={{ textAlign:'center', color:'var(--muted)', fontSize:'11px', marginTop:'20px' }}>
          AI-powered exam integrity monitoring
        </p>
      </div>
    </div>
  );
}