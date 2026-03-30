// src/pages/AdminPage.js — COMPLETE with live monitoring dashboard
import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { examAPI, adminAPI } from '../services/api';
import { useAdminSocket } from '../hooks/useAdminSocket';

// ── Risk level config ─────────────────────────────────────────────
const LEVEL = {
  SAFE    : { color:'#10b981', bg:'#052e16', border:'#14532d', label:'Safe'     },
  WARNING : { color:'#f59e0b', bg:'#1c1003', border:'#78350f', label:'Warning'  },
  HIGH    : { color:'#ef4444', bg:'#1a0505', border:'#7f1d1d', label:'High Risk' },
  CRITICAL: { color:'#dc2626', bg:'#1a0505', border:'#991b1b', label:'Critical' },
};

// ── Score bar component ───────────────────────────────────────────
function ScoreBar({ value, max = 100 }) {
  const pct = Math.min(100, (value / max) * 100);
  const col = pct > 60 ? '#ef4444' : pct > 30 ? '#f59e0b' : '#10b981';
  return (
    <div style={{ height: 4, background: '#1e2d45', borderRadius: 2, overflow: 'hidden' }}>
      <div style={{
        height: '100%', width: `${pct}%`,
        background: col, borderRadius: 2,
        transition: 'width 0.8s ease',
      }}/>
    </div>
  );
}

// ── Session card ──────────────────────────────────────────────────
function SessionCard({ session, onTerminate, onSelect, selected }) {
  const lvl = LEVEL[session.risk_level] || LEVEL.SAFE;
  const isHigh = ['HIGH', 'CRITICAL'].includes(session.risk_level);

  return (
    <div onClick={() => onSelect(session)}
      style={{
        background: selected ? '#0d1a2e' : 'var(--card)',
        border: `1px solid ${selected ? 'var(--accent)' : isHigh ? lvl.border : 'var(--border)'}`,
        borderRadius: 12, padding: '16px',
        cursor: 'pointer',
        transition: 'all 0.2s',
        animation: isHigh ? 'pulse-border 2s infinite' : 'none',
      }}>

      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
        <div>
          <div style={{ fontFamily: 'Syne', fontWeight: 700, fontSize: 14, marginBottom: 2 }}>
            {session.user_name}
          </div>
          <div style={{ color: 'var(--muted)', fontSize: 11 }}>
            {session.exam_title}
          </div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4 }}>
          <div style={{
            padding: '3px 10px', borderRadius: 20, fontSize: 11,
            fontFamily: 'Syne', fontWeight: 700,
            background: lvl.bg, border: `1px solid ${lvl.border}`,
            color: lvl.color,
          }}>
            {lvl.label}
          </div>
          <div style={{ color: 'var(--muted)', fontSize: 10 }}>
            {session.duration_minutes}m elapsed
          </div>
        </div>
      </div>

      {/* Big score */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginBottom: 10 }}>
        <span style={{
          fontFamily: 'Syne', fontWeight: 800, fontSize: 32,
          color: lvl.color,
        }}>
          {session.risk_score.toFixed(1)}
        </span>
        <span style={{ color: 'var(--muted)', fontSize: 12 }}>/ 100</span>
        <span style={{ marginLeft: 'auto', color: 'var(--muted)', fontSize: 11 }}>
          P(cheat): {(session.cheat_probability * 100).toFixed(0)}%
        </span>
      </div>

      {/* Overall score bar */}
      <ScoreBar value={session.risk_score} />

      {/* Module mini-bars */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)',
        gap: 6, marginTop: 10, marginBottom: 12,
      }}>
        {[
          ['Face',    session.face_score],
          ['Pose',    session.pose_score],
          ['Object',  session.object_score],
          ['Audio',   session.audio_score],
          ['Browser', session.browser_score],
        ].map(([name, val]) => (
          <div key={name}>
            <div style={{ fontSize: 9, color: 'var(--muted)', marginBottom: 2, textAlign: 'center' }}>
              {name}
            </div>
            <ScoreBar value={val} max={80} />
            <div style={{ fontSize: 9, color: 'var(--muted)', textAlign: 'center', marginTop: 1 }}>
              {val.toFixed(0)}
            </div>
          </div>
        ))}
      </div>

      {/* Footer row */}
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
      }}>
        <div style={{ fontSize: 11, color: 'var(--muted)' }}>
          ⚠ {session.violation_count} violations
        </div>
        {isHigh && (
          <button
            onClick={(e) => { e.stopPropagation(); onTerminate(session); }}
            style={{
              background: '#450a0a', border: '1px solid #7f1d1d',
              color: '#f87171', borderRadius: 6, padding: '4px 12px',
              fontSize: 11, fontFamily: 'Syne', fontWeight: 700,
              cursor: 'pointer', transition: 'all 0.2s',
            }}
            onMouseOver={e => e.target.style.background = '#7f1d1d'}
            onMouseOut={e  => e.target.style.background = '#450a0a'}
          >
            Terminate
          </button>
        )}
      </div>
    </div>
  );
}

// ── Detail panel ──────────────────────────────────────────────────
function SessionDetail({ session, onClose, onTerminate }) {
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    if (!session) return;
    adminAPI.sessionDetail(session.session_id)
      .then(r => setDetail(r.data))
      .catch(console.error);
  }, [session?.session_id]);

  if (!session) return null;
  const lvl = LEVEL[session.risk_level] || LEVEL.SAFE;

  return (
    <div style={{
      background: 'var(--bg2)', borderLeft: '1px solid var(--border)',
      height: '100%', overflowY: 'auto', padding: 20,
      display: 'flex', flexDirection: 'column', gap: 16,
    }}>
      {/* Close */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ fontFamily: 'Syne', fontSize: 16 }}>Session Detail</h3>
        <button className="btn-ghost" style={{ padding: '4px 10px', fontSize: 11 }}
          onClick={onClose}>✕ Close</button>
      </div>

      {/* Identity */}
      <div className="card" style={{ padding: 14 }}>
        <div style={{ fontFamily: 'Syne', fontWeight: 700, fontSize: 15, marginBottom: 4 }}>
          {session.user_name}
        </div>
        <div style={{ color: 'var(--muted)', fontSize: 11, marginBottom: 2 }}>
          {session.user_email}
        </div>
        <div style={{ color: 'var(--muted)', fontSize: 11 }}>
          Exam: {session.exam_title}
        </div>
        <div style={{ color: 'var(--muted)', fontSize: 11 }}>
          Duration: {session.duration_minutes} minutes
        </div>
      </div>

      {/* Risk overview */}
      <div className="card" style={{ padding: 14 }}>
        <div style={{
          fontFamily: 'Syne', fontWeight: 800, fontSize: 40,
          color: lvl.color, lineHeight: 1, marginBottom: 4,
        }}>
          {session.risk_score.toFixed(1)}
          <span style={{ fontSize: 14, color: 'var(--muted)', fontWeight: 400 }}>/100</span>
        </div>
        <div style={{
          display: 'inline-block', padding: '3px 10px', borderRadius: 20,
          background: lvl.bg, border: `1px solid ${lvl.border}`,
          color: lvl.color, fontSize: 11, fontFamily: 'Syne', fontWeight: 700,
          marginBottom: 10,
        }}>
          {lvl.label}
        </div>
        <div style={{ color: 'var(--muted)', fontSize: 11 }}>
          Cheat probability: {(session.cheat_probability * 100).toFixed(1)}%
        </div>
      </div>

      {/* Module breakdown */}
      <div className="card" style={{ padding: 14 }}>
        <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 10 }}>
          MODULE SCORES
        </div>
        {[
          ['👤 Face',    session.face_score],
          ['👁 Pose',    session.pose_score],
          ['📱 Object',  session.object_score],
          ['🎙 Audio',   session.audio_score],
          ['🌐 Browser', session.browser_score],
        ].map(([name, val]) => (
          <div key={name} style={{
            display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8,
          }}>
            <span style={{ fontSize: 12, width: 76, color: 'var(--muted)' }}>{name}</span>
            <div style={{ flex: 1 }}>
              <ScoreBar value={val} max={80}/>
            </div>
            <span style={{ fontSize: 11, color: 'var(--muted)', width: 28, textAlign: 'right' }}>
              {val.toFixed(0)}
            </span>
          </div>
        ))}
      </div>

      {/* Recent violations */}
      <div className="card" style={{ padding: 14, flex: 1 }}>
        <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 10 }}>
          RECENT VIOLATIONS
        </div>
        {!detail?.recent_violations?.length ? (
          <div style={{ color: 'var(--safe)', fontSize: 12, textAlign: 'center', padding: 16 }}>
            ✓ No violations yet
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {detail.recent_violations.map((v, i) => (
              <div key={i} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '6px 10px', borderRadius: 6,
                background: v.weight >= 30 ? '#1a0505' : 'var(--bg3)',
                border: `1px solid ${v.weight >= 30 ? '#7f1d1d' : 'var(--border)'}`,
                fontSize: 11,
              }}>
                <span style={{
                  color: v.weight >= 30 ? '#f87171' : 'var(--text)',
                  fontFamily: 'Syne', fontWeight: 600,
                }}>
                  {v.type}
                </span>
                <span style={{
                  background: v.weight >= 30 ? '#450a0a' : '#0c1a2e',
                  color: v.weight >= 30 ? '#f87171' : 'var(--accent)',
                  padding: '2px 8px', borderRadius: 10, fontSize: 10, fontWeight: 700,
                }}>
                  w:{v.weight}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Terminate button */}
      <button className="btn-danger"
        style={{ width: '100%', padding: 12 }}
        onClick={() => onTerminate(session)}>
        ⚠ Terminate This Session
      </button>
    </div>
  );
}

// ── Main AdminPage ────────────────────────────────────────────────
export default function AdminPage() {
  const { user, logout } = useAuth();
  const navigate         = useNavigate();

  const [tab,     setTab]     = useState('live');   // 'live' | 'exams'
  const [exams,   setExams]   = useState([]);
  const [selected,setSelected]= useState(null);
  const [creating,setCreate]  = useState(false);
  const [form,    setForm]    = useState({ title:'', duration_minutes:60, description:'' });
  const [error,   setError]   = useState('');
  const [confirmTerminate, setConfirmTerminate] = useState(null);

  const { connected, sessions, summary, lastUpdate, terminateSession } = useAdminSocket();

  useEffect(() => {
    examAPI.list().then(r => setExams(r.data)).catch(console.error);
  }, []);

  const handleTerminate = (session) => setConfirmTerminate(session);

  const confirmAndTerminate = async () => {
    if (!confirmTerminate) return;
    try {
      terminateSession(confirmTerminate.session_id);   // via WS
      await adminAPI.terminate(confirmTerminate.session_id); // via REST backup
    } catch (e) {
      console.error('Terminate failed:', e);
    }
    setConfirmTerminate(null);
    if (selected?.session_id === confirmTerminate.session_id) setSelected(null);
  };

  const handleCreateExam = async () => {
    setError('');
    try {
      await examAPI.create(form);
      setForm({ title:'', duration_minutes:60, description:'' });
      setCreate(false);
      const res = await examAPI.list();
      setExams(res.data);
    } catch (e) {
      setError(e.response?.data?.detail || 'Failed to create exam');
    }
  };

  // Sort sessions by risk score descending
  const sortedSessions = [...sessions].sort((a, b) => b.risk_score - a.risk_score);

  return (
    <div style={{ minHeight:'100vh', background:'var(--bg)', display:'flex', flexDirection:'column' }}>
      <style>{`
        @keyframes pulse-border {
          0%,100%{box-shadow:0 0 0 0 rgba(239,68,68,0)}
          50%{box-shadow:0 0 0 4px rgba(239,68,68,0.2)}
        }
      `}</style>

      {/* Navbar */}
      <nav style={{
        display:'flex', alignItems:'center', justifyContent:'space-between',
        padding:'14px 24px', borderBottom:'1px solid var(--border)',
        background:'var(--bg2)', position:'sticky', top:0, zIndex:50,
      }}>
        <div style={{ display:'flex', alignItems:'center', gap:12 }}>
          <span style={{ fontSize:18 }}>🔒</span>
          <span style={{ fontFamily:'Syne', fontWeight:700, fontSize:16 }}>ProctorAI</span>
          <span style={{
            background:'#1e3a5f', color:'var(--accent)', borderRadius:4,
            padding:'2px 8px', fontSize:10, fontFamily:'Syne', fontWeight:700,
          }}>ADMIN</span>
        </div>

        {/* WS status */}
        <div style={{ display:'flex', alignItems:'center', gap:6,
          background: connected ? '#052e16' : '#1c0a03',
          border:`1px solid ${connected ? '#14532d' : '#78350f'}`,
          borderRadius:20, padding:'3px 12px', fontSize:11,
          color: connected ? 'var(--safe)' : 'var(--warn)',
        }}>
          <span style={{ animation:'pulse 2s infinite' }}>●</span>
          {connected ? 'Live monitoring' : 'Reconnecting...'}
          {lastUpdate && <span style={{ color:'var(--muted)', marginLeft:4 }}>
            {lastUpdate.toLocaleTimeString()}
          </span>}
        </div>

        <div style={{ display:'flex', gap:10, alignItems:'center' }}>
          <span style={{ color:'var(--muted)', fontSize:12 }}>{user?.email}</span>
          <button className="btn-ghost" onClick={logout}
            style={{ fontSize:12, padding:'6px 14px' }}>Logout</button>
        </div>
      </nav>

      {/* Summary strip */}
      {summary && (
        <div style={{
          display:'grid', gridTemplateColumns:'repeat(5,1fr)',
          background:'var(--bg2)', borderBottom:'1px solid var(--border)',
          padding:'10px 24px', gap:12,
        }}>
          {[
            { label:'Active',   val:summary.total_active, color:'var(--accent)' },
            { label:'Safe',     val:summary.safe,         color:'var(--safe)'   },
            { label:'Warning',  val:summary.warning,      color:'var(--warn)'   },
            { label:'High',     val:summary.high_risk,    color:'var(--high)'   },
            { label:'Critical', val:summary.critical,     color:'var(--critical)'},
          ].map(({ label, val, color }) => (
            <div key={label} style={{ textAlign:'center' }}>
              <div style={{ fontFamily:'Syne', fontWeight:800, fontSize:22, color }}>
                {val}
              </div>
              <div style={{ color:'var(--muted)', fontSize:10 }}>{label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div style={{
        display:'flex', gap:4, padding:'12px 24px 0',
        borderBottom:'1px solid var(--border)', background:'var(--bg2)',
      }}>
        {[['live','🔴 Live Sessions'],['exams','📋 Exams']].map(([t, label]) => (
          <button key={t} onClick={() => setTab(t)}
            style={{
              background:'transparent', border:'none',
              borderBottom: tab === t ? '2px solid var(--accent)' : '2px solid transparent',
              color: tab === t ? 'var(--text)' : 'var(--muted)',
              padding:'8px 16px', fontSize:13, fontFamily:'Syne', fontWeight:600,
              cursor:'pointer', borderRadius:0, transition:'all 0.2s',
            }}>
            {label}
            {t === 'live' && sessions.length > 0 && (
              <span style={{
                marginLeft:6, background:'var(--accent)', color:'white',
                borderRadius:'50%', width:18, height:18, fontSize:10,
                display:'inline-flex', alignItems:'center', justifyContent:'center',
              }}>
                {sessions.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex:1, display:'flex', overflow:'hidden' }}>

        {/* ── LIVE TAB ── */}
        {tab === 'live' && (
          <div style={{ flex:1, display:'flex', overflow:'hidden' }}>
            {/* Session grid */}
            <div style={{
              flex:1, overflowY:'auto', padding:20,
              display:'grid',
              gridTemplateColumns: selected
                ? 'repeat(auto-fill,minmax(280px,1fr))'
                : 'repeat(auto-fill,minmax(320px,1fr))',
              gap:16, alignContent:'start',
            }}>
              {sortedSessions.length === 0 ? (
                <div style={{
                  gridColumn:'1/-1', textAlign:'center',
                  padding:60, color:'var(--muted)',
                }}>
                  <div style={{ fontSize:40, marginBottom:12 }}>📋</div>
                  <div style={{ fontFamily:'Syne', fontSize:16 }}>
                    No active exam sessions
                  </div>
                  <div style={{ fontSize:12, marginTop:6 }}>
                    Sessions will appear here when students start exams
                  </div>
                </div>
              ) : sortedSessions.map(s => (
                <SessionCard
                  key={s.session_id}
                  session={s}
                  selected={selected?.session_id === s.session_id}
                  onTerminate={handleTerminate}
                  onSelect={setSelected}
                />
              ))}
            </div>

            {/* Detail panel */}
            {selected && (
              <div style={{ width:360, flexShrink:0, borderLeft:'1px solid var(--border)', overflow:'hidden' }}>
                <SessionDetail
                  session={selected}
                  onClose={() => setSelected(null)}
                  onTerminate={handleTerminate}
                />
              </div>
            )}
          </div>
        )}

        {/* ── EXAMS TAB ── */}
        {tab === 'exams' && (
          <div style={{ flex:1, overflowY:'auto', padding:24 }}>
            <div style={{ display:'flex', justifyContent:'flex-end', marginBottom:16 }}>
              <button className="btn-primary" onClick={() => setCreate(true)}
                style={{ padding:'10px 20px' }}>
                + Create Exam
              </button>
            </div>
            {exams.length === 0 ? (
              <div className="card" style={{ textAlign:'center', padding:48, color:'var(--muted)' }}>
                <div style={{ fontSize:32, marginBottom:12 }}>📋</div>
                No exams yet.
              </div>
            ) : (
              <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
                {exams.map(exam => (
                  <div key={exam.id} className="card" style={{
                    display:'flex', alignItems:'center', gap:20,
                  }}>
                    <div style={{ flex:1 }}>
                      <div style={{ fontFamily:'Syne', fontWeight:700, fontSize:15, marginBottom:4 }}>
                        {exam.title}
                      </div>
                      <div style={{ color:'var(--muted)', fontSize:11, display:'flex', gap:16 }}>
                        <span>⏱ {exam.duration_minutes} min</span>
                        <span style={{ fontFamily:'DM Mono', fontSize:10, opacity:0.5 }}>
                          {exam.id.slice(0,12)}...
                        </span>
                      </div>
                    </div>
                    <div style={{
                      padding:'4px 14px', borderRadius:20, fontSize:11,
                      fontFamily:'Syne', fontWeight:700,
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
          </div>
        )}
      </div>

      {/* Create exam modal */}
      {creating && (
        <div style={{
          position:'fixed', inset:0, background:'rgba(0,0,0,0.75)',
          display:'flex', alignItems:'center', justifyContent:'center', zIndex:100,
        }} onClick={e => { if (e.target === e.currentTarget) setCreate(false); }}>
          <div className="card animate-in" style={{ width:'100%', maxWidth:440 }}>
            <h2 style={{ fontSize:18, marginBottom:20 }}>Create New Exam</h2>
            <div style={{ display:'flex', flexDirection:'column', gap:14 }}>
              <div>
                <label style={{ color:'var(--muted)', fontSize:11, display:'block', marginBottom:4 }}>
                  EXAM TITLE *
                </label>
                <input placeholder="e.g. Python Programming Midterm"
                  value={form.title}
                  onChange={e => setForm(p => ({ ...p, title: e.target.value }))} autoFocus/>
              </div>
              <div>
                <label style={{ color:'var(--muted)', fontSize:11, display:'block', marginBottom:4 }}>
                  DURATION (minutes)
                </label>
                <input type="number" min={5} max={300}
                  value={form.duration_minutes}
                  onChange={e => setForm(p => ({ ...p, duration_minutes: parseInt(e.target.value)||60 }))}/>
              </div>
              <div>
                <label style={{ color:'var(--muted)', fontSize:11, display:'block', marginBottom:4 }}>
                  DESCRIPTION (optional)
                </label>
                <input placeholder="Brief instructions"
                  value={form.description}
                  onChange={e => setForm(p => ({ ...p, description: e.target.value }))}/>
              </div>
              {error && (
                <div style={{ background:'#1f0a0a', border:'1px solid #7f1d1d', borderRadius:8, padding:10, color:'#f87171', fontSize:12 }}>
                  {error}
                </div>
              )}
              <div style={{ display:'flex', gap:10, marginTop:4 }}>
                <button className="btn-ghost" style={{ flex:1 }}
                  onClick={() => { setCreate(false); setError(''); }}>
                  Cancel
                </button>
                <button className="btn-primary" style={{ flex:2, padding:11 }}
                  onClick={handleCreateExam} disabled={!form.title.trim()}>
                  Create Exam →
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Terminate confirm modal */}
      {confirmTerminate && (
        <div style={{
          position:'fixed', inset:0, background:'rgba(0,0,0,0.8)',
          display:'flex', alignItems:'center', justifyContent:'center', zIndex:200,
        }}>
          <div className="card animate-in" style={{
            width:'100%', maxWidth:400, border:'1px solid #7f1d1d',
          }}>
            <div style={{ fontSize:32, marginBottom:12, textAlign:'center' }}>⚠</div>
            <h2 style={{ fontSize:18, textAlign:'center', marginBottom:8, color:'var(--high)' }}>
              Terminate Exam Session?
            </h2>
            <p style={{ color:'var(--muted)', fontSize:13, textAlign:'center', marginBottom:8 }}>
              <strong style={{ color:'var(--text)' }}>{confirmTerminate.user_name}</strong>
              <br/>
              {confirmTerminate.exam_title}
            </p>
            <p style={{ color:'var(--muted)', fontSize:12, textAlign:'center', marginBottom:24, lineHeight:1.6 }}>
              Current risk score: <strong style={{ color:LEVEL[confirmTerminate.risk_level]?.color }}>
                {confirmTerminate.risk_score.toFixed(1)}
              </strong>
              <br/>This action cannot be undone.
            </p>
            <div style={{ display:'flex', gap:10 }}>
              <button className="btn-ghost" style={{ flex:1 }}
                onClick={() => setConfirmTerminate(null)}>
                Cancel
              </button>
              <button className="btn-danger" style={{ flex:2, padding:12 }}
                onClick={confirmAndTerminate}>
                Yes, Terminate Session
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}