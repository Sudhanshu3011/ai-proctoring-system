// src/pages/AdminPage.js  — COMPLETE VERSION
// Includes: exam creation, list, and live session monitoring

import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { examAPI } from '../services/api';

const LEVEL_COLOR = {
  SAFE:'#10b981', WARNING:'#f59e0b', HIGH:'#ef4444', CRITICAL:'#dc2626'
};

export default function AdminPage() {
  const { user, logout } = useAuth();
  const navigate         = useNavigate();

  const [tab,     setTab]    = useState('exams');   // 'exams' | 'live'
  const [exams,   setExams]  = useState([]);
  const [form,    setForm]   = useState({ title:'', duration_minutes:60, description:'' });
  const [creating,setCreate] = useState(false);
  const [error,   setError]  = useState('');

  // Live sessions (polled from risk endpoint)
  const [sessions,    setSessions]   = useState([]);
  const pollRef = useRef(null);

  const load = () => examAPI.list().then(r => setExams(r.data)).catch(console.error);

  useEffect(() => { load(); }, []);

  // Poll live sessions every 3s when on live tab
  useEffect(() => {
    if (tab !== 'live') { clearInterval(pollRef.current); return; }
    const poll = async () => {
      // In a real app you'd have a /admin/live-sessions endpoint
      // For now we show exams with active status
      const res = await examAPI.list();
      setSessions(res.data.filter(e => e.status === 'active'));
    };
    poll();
    pollRef.current = setInterval(poll, 3000);
    return () => clearInterval(pollRef.current);
  }, [tab]);

  const handleCreate = async () => {
    setError('');
    try {
      await examAPI.create(form);
      setForm({ title:'', duration_minutes:60, description:'' });
      setCreate(false);
      load();
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to create exam');
    }
  };

  return (
    <div style={{ minHeight:'100vh', background:'var(--bg)' }}>

      {/* Navbar */}
      <nav style={{
        display:'flex', alignItems:'center', justifyContent:'space-between',
        padding:'14px 28px', borderBottom:'1px solid var(--border)',
        background:'var(--bg2)',
      }}>
        <div style={{ display:'flex', alignItems:'center', gap:'12px' }}>
          <span style={{ fontSize:'20px' }}>🔒</span>
          <span style={{ fontFamily:'Syne', fontWeight:700, fontSize:'16px' }}>ProctorAI</span>
          <span style={{
            background:'#1e3a5f', color:'var(--accent)',
            borderRadius:'4px', padding:'2px 8px', fontSize:'10px',
            fontFamily:'Syne', fontWeight:700, letterSpacing:'0.05em',
          }}>ADMIN</span>
        </div>
        <div style={{ display:'flex', gap:'10px', alignItems:'center' }}>
          <span style={{ color:'var(--muted)', fontSize:'12px' }}>{user?.email}</span>
          <button className="btn-ghost" onClick={logout}
            style={{ fontSize:'12px', padding:'6px 14px' }}>Logout</button>
        </div>
      </nav>

      <div style={{ maxWidth:'960px', margin:'0 auto', padding:'32px 24px' }}>

        {/* Title + tab switcher */}
        <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:'24px' }}>
          <div>
            <h1 style={{ fontSize:'26px', marginBottom:'4px' }}>Admin Dashboard</h1>
            <p style={{ color:'var(--muted)', fontSize:'12px' }}>Manage exams and monitor candidates</p>
          </div>
          <div style={{ display:'flex', gap:'8px' }}>
            {[['exams','📋 Exams'],['live','🔴 Live']].map(([t, label]) => (
              <button key={t} onClick={() => setTab(t)}
                style={{
                  background: tab === t ? 'var(--accent)' : 'var(--bg3)',
                  color: tab === t ? 'white' : 'var(--muted)',
                  border:`1px solid ${tab === t ? 'var(--accent)' : 'var(--border)'}`,
                  borderRadius:'8px', padding:'8px 16px', fontSize:'13px',
                  fontFamily:'Syne', fontWeight:600, cursor:'pointer',
                }}>
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* ── EXAMS TAB ── */}
        {tab === 'exams' && (
          <>
            <div style={{ display:'flex', justifyContent:'flex-end', marginBottom:'16px' }}>
              <button className="btn-primary" onClick={() => setCreate(true)}
                style={{ padding:'10px 20px' }}>
                + Create Exam
              </button>
            </div>

            {exams.length === 0 ? (
              <div className="card" style={{ textAlign:'center', padding:'48px', color:'var(--muted)' }}>
                <div style={{ fontSize:'32px', marginBottom:'12px' }}>📋</div>
                No exams created yet. Create your first exam.
              </div>
            ) : (
              <div style={{ display:'flex', flexDirection:'column', gap:'10px' }}>
                {exams.map(exam => (
                  <div key={exam.id} className="card" style={{
                    display:'flex', alignItems:'center', gap:'20px',
                  }}>
                    <div style={{ flex:1 }}>
                      <div style={{ fontFamily:'Syne', fontWeight:700, fontSize:'15px', marginBottom:'4px' }}>
                        {exam.title}
                      </div>
                      <div style={{ color:'var(--muted)', fontSize:'11px', display:'flex', gap:'16px' }}>
                        <span>⏱ {exam.duration_minutes} min</span>
                        <span style={{ opacity:0.5, fontFamily:'DM Mono', fontSize:'10px' }}>
                          {exam.id.slice(0,12)}...
                        </span>
                      </div>
                    </div>
                    <div style={{
                      padding:'4px 14px', borderRadius:'20px', fontSize:'11px',
                      fontFamily:'Syne', fontWeight:700, letterSpacing:'0.03em',
                      background: exam.status === 'active' ? '#052e16' : '#0c1117',
                      color: exam.status === 'active' ? 'var(--safe)' : 'var(--muted)',
                      border:`1px solid ${exam.status === 'active' ? '#14532d' : 'var(--border)'}`,
                    }}>
                      {exam.status}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        {/* ── LIVE TAB ── */}
        {tab === 'live' && (
          <div>
            <div style={{
              display:'flex', alignItems:'center', gap:'8px', marginBottom:'20px',
            }}>
              <div style={{ width:8, height:8, borderRadius:'50%', background:'var(--high)', animation:'pulse 2s infinite' }}/>
              <span style={{ color:'var(--muted)', fontSize:'12px' }}>
                Auto-refreshing every 3 seconds
              </span>
            </div>

            {sessions.length === 0 ? (
              <div className="card" style={{ textAlign:'center', padding:'48px', color:'var(--muted)' }}>
                <div style={{ fontSize:'32px', marginBottom:'12px' }}>🔴</div>
                No active exam sessions right now.
              </div>
            ) : (
              <div style={{ display:'flex', flexDirection:'column', gap:'10px' }}>
                {sessions.map(s => (
                  <div key={s.id} className="card">
                    <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
                      <div>
                        <div style={{ fontFamily:'Syne', fontWeight:700 }}>{s.title}</div>
                        <div style={{ color:'var(--muted)', fontSize:'11px', marginTop:'2px' }}>
                          Session active
                        </div>
                      </div>
                      <div style={{ display:'flex', gap:'8px' }}>
                        <div style={{
                          padding:'4px 12px', borderRadius:'20px',
                          background:'#052e16', border:'1px solid #14532d',
                          color:'var(--safe)', fontSize:'11px',
                          display:'flex', alignItems:'center', gap:'6px',
                        }}>
                          <span style={{ animation:'pulse 2s infinite' }}>●</span> Live
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Create exam modal */}
      {creating && (
        <div style={{
          position:'fixed', inset:0, background:'rgba(0,0,0,0.75)',
          display:'flex', alignItems:'center', justifyContent:'center', zIndex:100,
        }}
          onClick={e => { if (e.target === e.currentTarget) setCreate(false); }}
        >
          <div className="card animate-in" style={{ width:'100%', maxWidth:'440px' }}>
            <h2 style={{ fontSize:'18px', marginBottom:'4px' }}>Create New Exam</h2>
            <p style={{ color:'var(--muted)', fontSize:'12px', marginBottom:'20px' }}>
              Students will see this in their dashboard.
            </p>

            <div style={{ display:'flex', flexDirection:'column', gap:'14px' }}>
              <div>
                <label style={{ color:'var(--muted)', fontSize:'11px', display:'block', marginBottom:'4px' }}>
                  EXAM TITLE *
                </label>
                <input
                  placeholder="e.g. Python Programming Midterm"
                  value={form.title}
                  onChange={e => setForm(p => ({ ...p, title: e.target.value }))}
                  autoFocus
                />
              </div>

              <div>
                <label style={{ color:'var(--muted)', fontSize:'11px', display:'block', marginBottom:'4px' }}>
                  DURATION (minutes)
                </label>
                <input type="number" min={5} max={300}
                  value={form.duration_minutes}
                  onChange={e => setForm(p => ({
                    ...p, duration_minutes: parseInt(e.target.value) || 60
                  }))}
                />
              </div>

              <div>
                <label style={{ color:'var(--muted)', fontSize:'11px', display:'block', marginBottom:'4px' }}>
                  DESCRIPTION (optional)
                </label>
                <input
                  placeholder="Brief instructions or notes"
                  value={form.description}
                  onChange={e => setForm(p => ({ ...p, description: e.target.value }))}
                />
              </div>

              {error && (
                <div style={{
                  background:'#1f0a0a', border:'1px solid #7f1d1d',
                  borderRadius:'8px', padding:'10px', color:'#f87171', fontSize:'12px',
                }}>
                  {error}
                </div>
              )}

              <div style={{ display:'flex', gap:'10px', marginTop:'4px' }}>
                <button className="btn-ghost" style={{ flex:1 }}
                  onClick={() => { setCreate(false); setError(''); }}>
                  Cancel
                </button>
                <button className="btn-primary" style={{ flex:2, padding:'11px' }}
                  onClick={handleCreate}
                  disabled={!form.title.trim()}>
                  Create Exam →
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}