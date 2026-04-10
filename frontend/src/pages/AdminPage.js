// src/pages/AdminPage.js — professional, style/logic separated
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { examAPI, adminAPI } from '../services/api';
import { useAdminSocket } from '../hooks/useAdminSocket';
import { colors, fonts, radius, shadow, statusConfig } from '../styles/theme';
import { nav, card, btn, text, badge, statusPill, table, modal } from '../styles/styles';

// ── All styles ────────────────────────────────────────────────────
const S = {
  summaryStrip: {
    background: colors.white,
    borderBottom: `1px solid ${colors.gray200}`,
    display: 'grid',
    gridTemplateColumns: 'repeat(5,1fr)',
    padding: '0 24px',
  },
  summaryCell: {
    padding: '12px 0',
    textAlign: 'center',
    borderRight: `1px solid ${colors.gray100}`,
  },
  summaryVal: (col) => ({
    fontFamily: fonts.mono,
    fontSize: '22px',
    fontWeight: 600,
    color: col,
    lineHeight: 1,
  }),
  summaryLbl: {
    fontSize: '10px',
    fontWeight: 700,
    color: colors.gray400,
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginTop: '3px',
    fontFamily: fonts.ui,
  },
  tabBar: {
    background: colors.white,
    borderBottom: `1px solid ${colors.gray200}`,
    display: 'flex',
    padding: '0 24px',
  },
  tabBtn: (active) => ({
    fontFamily: fonts.ui,
    fontWeight: active ? 600 : 400,
    fontSize: '13px',
    background: 'transparent',
    border: 'none',
    borderBottom: `2px solid ${active ? colors.accent : 'transparent'}`,
    color: active ? colors.accent : colors.gray500,
    padding: '12px 16px',
    cursor: 'pointer',
    transition: 'all 0.15s',
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  }),
  sessionCard: (selected, level) => {
    const cfg = statusConfig[level] || statusConfig.SAFE;
    return {
      background: selected ? colors.brandLight : colors.white,
      border: `1px solid ${selected ? colors.brandBorder : colors.gray200}`,
      borderRadius: radius.lg,
      padding: '16px',
      cursor: 'pointer',
      transition: 'all 0.15s',
      boxShadow: selected ? `0 0 0 2px ${colors.accent}20` : shadow.xs,
    };
  },
  scoreNum: (col) => ({
    fontFamily: fonts.mono,
    fontSize: '28px',
    fontWeight: 700,
    color: col,
    lineHeight: 1,
  }),
  moduleBar: { display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '5px' },
  modLabel: { fontSize: '11px', color: colors.gray500, width: '50px', fontFamily: fonts.ui },
  barTrack: { flex: 1, height: '3px', background: colors.gray200, borderRadius: '99px' },
  barFill: (pct, col) => ({
    height: '100%', width: `${Math.min(100, pct || 0)}%`,
    background: col,
    borderRadius: '99px',
    transition: 'width 0.6s ease',
  }),
  violRow: (high) => ({
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '6px 10px',
    borderRadius: radius.sm,
    marginBottom: '4px',
    background: high ? colors.dangerLight : colors.gray50,
    border: `1px solid ${high ? colors.dangerBorder : colors.gray200}`,
    fontSize: '11px',
  }),
  detailPanel: {
    width: '340px',
    background: colors.white,
    borderLeft: `1px solid ${colors.gray200}`,
    overflowY: 'auto',
    display: 'flex',
    flexDirection: 'column',
    gap: '0',
  },
  detailSection: {
    padding: '16px',
    borderBottom: `1px solid ${colors.gray200}`,
  },
};

// ── Score bar ─────────────────────────────────────────────────────
function ModuleBar({ label, value }) {
  const pct = Math.min(100, value || 0);
  const col = pct > 60 ? colors.dangerMid : pct > 30 ? colors.warningMid : colors.gray300;
  return (
    <div style={S.moduleBar}>
      <span style={S.modLabel}>{label}</span>
      <div style={S.barTrack}><div style={S.barFill(pct, col)} /></div>
      <span style={{ fontSize: '10px', color: colors.gray400, width: '24px', textAlign: 'right', fontFamily: fonts.mono }}>
        {pct.toFixed(0)}
      </span>
    </div>
  );
}

// ── Session card ──────────────────────────────────────────────────
function SessionCard({ session, selected, onSelect, onTerminate }) {
  const cfg = statusConfig[session.risk_level] || statusConfig.SAFE;
  return (
    <div style={S.sessionCard(selected, session.risk_level)}
      onClick={() => onSelect(session)}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
        <div>
          <div style={{ fontWeight: 600, fontSize: '14px', color: colors.gray900, marginBottom: '2px' }}>
            {session.user_name}
          </div>
          <div style={{ fontSize: '11px', color: colors.gray500 }}>{session.exam_title}</div>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px' }}>
          <span style={{ ...badge.base, background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}` }}>
            {cfg.label}
          </span>
          <span style={{ fontSize: '10px', color: colors.gray400, fontFamily: fonts.mono }}>
            {session.duration_minutes}m
          </span>
        </div>
      </div>

      <div style={{ marginBottom: '8px' }}>
        <span style={S.scoreNum(cfg.color)}>{session.risk_score.toFixed(1)}</span>
        <span style={{ fontSize: '12px', color: colors.gray400, fontFamily: fonts.mono }}>/100</span>
        <span style={{ fontSize: '12px', color: colors.gray500, marginLeft: '12px' }}>
          P: {(session.cheat_probability * 100).toFixed(0)}%
        </span>
      </div>

      {/* Score bar */}
      <div style={{ height: '3px', background: colors.gray200, borderRadius: '99px', marginBottom: '10px' }}>
        <div style={S.barFill(session.risk_score, cfg.color)} />
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontSize: '11px', color: colors.gray500 }}>
          {session.violation_count} violations
        </span>
        {['HIGH', 'CRITICAL'].includes(session.risk_level) && (
          <button className="btn-danger" style={{ ...btn.danger, fontSize: '11px', padding: '3px 10px' }}
            onClick={(e) => { e.stopPropagation(); onTerminate(session); }}>
            Terminate
          </button>
        )}
      </div>
    </div>
  );
}

// ── Detail panel ──────────────────────────────────────────────────
function DetailPanel({ session, detail, onClose, onTerminate }) {
  if (!session) return null;
  const cfg = statusConfig[session.risk_level] || statusConfig.SAFE;
  return (
    <div style={S.detailPanel}>
      {/* Header */}
      <div style={{ ...S.detailSection, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontWeight: 700, fontSize: '13px', color: colors.gray900 }}>Session Detail</span>
        <button style={{ ...btn.ghost, padding: '4px 8px', fontSize: '16px' }} onClick={onClose}>×</button>
      </div>
      {/* Identity */}
      <div style={S.detailSection}>
        <div style={{ fontWeight: 700, fontSize: '14px', color: colors.gray900 }}>{session.user_name}</div>
        <div style={{ fontSize: '11px', color: colors.gray500, marginTop: '2px' }}>{session.user_email}</div>
        <div style={{ fontSize: '11px', color: colors.gray500, marginTop: '6px' }}>{session.exam_title}</div>
      </div>
      {/* Score */}
      <div style={S.detailSection}>
        <div style={S.scoreNum(cfg.color)}>{session.risk_score.toFixed(1)}</div>
        <span style={{ ...badge.base, ...{ background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}`, marginTop: '8px', display: 'inline-flex' } }}>
          {cfg.label}
        </span>
      </div>
      {/* Modules */}
      <div style={S.detailSection}>
        <div style={text.sectionTitle}>Module Scores</div>
        {[['Face', session.face_score], ['Pose', session.pose_score], ['Objects', session.object_score], ['Audio', session.audio_score], ['Browser', session.browser_score]].map(([n, v]) => (
          <ModuleBar key={n} label={n} value={v} />
        ))}
      </div>
      {/* Violations */}
      <div style={{ ...S.detailSection, flex: 1 }}>
        <div style={text.sectionTitle}>Recent Violations</div>
        {!detail?.recent_violations?.length ? (
          <div style={{ fontSize: '12px', color: colors.successMid }}>None recorded</div>
        ) : detail.recent_violations.map((v, i) => (
          <div key={i} style={S.violRow(v.weight >= 30)}>
            <span style={{ fontWeight: 600, color: v.weight >= 30 ? colors.dangerMid : colors.gray700 }}>{v.type}</span>
            <span style={{ ...badge.base, background: v.weight >= 30 ? colors.dangerLight : colors.gray100, color: v.weight >= 30 ? colors.dangerMid : colors.gray600, border: 'none', fontSize: '10px' }}>
              w:{v.weight}
            </span>
          </div>
        ))}
      </div>
      {/* Actions */}
      <div style={{ padding: '14px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <button className="btn-danger" style={{ ...btn.danger, width: '100%', justifyContent: 'center' }}
          onClick={() => onTerminate(session)}>
          Terminate Session
        </button>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────
export default function AdminPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const [tab, setTab] = useState('live');
  const [exams, setExams] = useState([]);
  const [selected, setSelect] = useState(null);
  const [detail, setDetail] = useState(null);
  const [creating, setCreate] = useState(false);
  const [form, setForm] = useState({ title: '', duration_minutes: 60, description: '' });
  const [formErr, setFormErr] = useState('');
  const [termConf, setTerm] = useState(null);
  const [termAll, setTermAll] = useState(false);

  const { connected, sessions, summary, lastUpdate, terminateSession } = useAdminSocket();

  const loadExams = () => examAPI.list().then(r => setExams(r.data)).catch(console.error);
  useEffect(() => { loadExams(); }, []);

  useEffect(() => {
    if (!selected) return;
    adminAPI.sessionDetail(selected.session_id).then(r => setDetail(r.data)).catch(console.error);
  }, [selected?.session_id]);

  const handleTerminate = (s) => setTerm(s);
  const confirmTerminate = async () => {
    if (!termConf) return;
    terminateSession(termConf.session_id);
    await adminAPI.terminate(termConf.session_id).catch(console.error);
    setTerm(null);
    if (selected?.session_id === termConf.session_id) setSelect(null);
  };
  const handleTerminateAll = async () => {
    await adminAPI.terminateAll().catch(console.error);
    setTermAll(false);
  };
  const handleCreate = async () => {
    setFormErr('');
    try {
      await examAPI.create(form);
      setForm({ title: '', duration_minutes: 60, description: '' });
      setCreate(false);
      loadExams();
    } catch (e) { setFormErr(e.response?.data?.detail || 'Failed'); }
  };
  const handleStatusChange = (id, status) =>
    adminAPI.updateExamStatus(id, status).then(loadExams).catch(console.error);
  const handleDelete = async (id) => {
    if (!window.confirm('Delete this exam?')) return;
    await adminAPI.deleteExam(id).then(loadExams).catch(e => alert(e.response?.data?.detail || 'Delete failed'));
  };

  const sorted = [...sessions].sort((a, b) => b.risk_score - a.risk_score);
  const SUMMARY_COLS = [
    { l: 'Active', v: summary?.total_active || 0, col: colors.accent },
    { l: 'Safe', v: summary?.safe || 0, col: colors.successMid },
    { l: 'Warning', v: summary?.warning || 0, col: colors.warningMid },
    { l: 'High', v: summary?.high_risk || 0, col: colors.dangerMid },
    { l: 'Critical', v: summary?.critical || 0, col: colors.critical },
  ];

  return (
    <div style={{ minHeight: '100vh', background: colors.gray50, fontFamily: fonts.ui }}>
      {/* Navbar */}
      <nav style={nav.root}>
        <div style={nav.brand}>
          <div style={nav.brandLogo}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L4 6v6c0 5.5 3.6 10.3 8 12 4.4-1.7 8-6.5 8-12V6L12 2z" fill="white" opacity=".9" />
            </svg>
          </div>
          <span style={nav.brandName}>ProctorAI</span>
          <span style={{ ...badge.base, ...badge.admin }}>Admin</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={statusPill(connected)}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: connected ? colors.successMid : colors.dangerMid, display: 'inline-block', animation: connected ? 'none' : 'pulse 1.5s infinite' }} />
            {connected ? 'Live' : 'Offline'}
            {lastUpdate && <span style={{ color: colors.gray400, marginLeft: '4px', fontFamily: fonts.mono, fontSize: '10px' }}>{lastUpdate.toLocaleTimeString()}</span>}
          </div>
          <span style={{ fontSize: '13px', color: colors.gray500 }}>{user?.email}</span>
          <button className="btn-ghost" style={btn.ghost} onClick={logout}>Sign out</button>
        </div>
      </nav>

      {/* Summary strip */}
      <div style={S.summaryStrip}>
        {SUMMARY_COLS.map(({ l, v, col }) => (
          <div key={l} style={S.summaryCell}>
            <div style={S.summaryVal(col)}>{v}</div>
            <div style={S.summaryLbl}>{l}</div>
          </div>
        ))}
      </div>

      {/* Tab bar */}
      <div style={S.tabBar}>
        {[['live', 'Live Sessions'], ['exams', 'Exam Management']].map(([t, l]) => (
          <button key={t} style={S.tabBtn(tab === t)} onClick={() => setTab(t)}>
            {l}
            {t === 'live' && sessions.length > 0 && (
              <span style={{ background: colors.dangerMid, color: '#fff', borderRadius: '99px', padding: '1px 6px', fontSize: '10px', fontWeight: 700 }}>
                {sessions.length}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ display: 'flex', height: 'calc(100vh - 153px)', overflow: 'hidden' }}>

        {/* Live tab */}
        {tab === 'live' && (
          <>
            {/* Terminate all */}
            {sessions.length > 0 && (
              <div style={{ position: 'absolute', top: '8px', right: '16px', zIndex: 10 }}>
                <button className="btn-danger" style={{ ...btn.danger, fontSize: '12px' }}
                  onClick={() => setTermAll(true)}>
                  Terminate All ({sessions.length})
                </button>
              </div>
            )}

            <div style={{
              flex: 1, overflowY: 'auto', padding: '20px',
              display: 'grid',
              gridTemplateColumns: selected ? 'repeat(auto-fill,minmax(260px,1fr))' : 'repeat(auto-fill,minmax(300px,1fr))',
              gap: '12px', alignContent: 'start',
            }}>
              {sorted.length === 0 ? (
                <div style={{ gridColumn: '1/-1', ...card.base, textAlign: 'center', padding: '56px', color: colors.gray400 }}>
                  <div style={{ fontSize: '13px' }}>No active exam sessions.</div>
                </div>
              ) : sorted.map(s => (
                <SessionCard key={s.session_id} session={s}
                  selected={selected?.session_id === s.session_id}
                  onSelect={setSelect} onTerminate={handleTerminate} />
              ))}
            </div>

            {selected && (
              <DetailPanel session={selected} detail={detail}
                onClose={() => setSelect(null)} onTerminate={handleTerminate} />
            )}
          </>
        )}

        {/* Exams tab */}
        {tab === 'exams' && (
          <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '16px', alignItems: 'center' }}>
              <span style={text.sectionTitle}>All Exams</span>
              <button className="btn-primary" style={btn.primary} onClick={() => setCreate(true)}>
                + Create Exam
              </button>
            </div>
            {exams.length === 0 ? (
              <div style={{ ...card.base, textAlign: 'center', padding: '48px', color: colors.gray400 }}>No exams created yet.</div>
            ) : (
              <table style={table.root}>
                <thead>
                  <tr>
                    {['Title', 'Duration', 'Status', 'Actions'].map(h => (
                      <th key={h} style={table.th}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {exams.map(exam => (
                    <tr key={exam.id}>
                      <td style={table.td}>
                        <div style={{ fontWeight: 600, color: colors.gray900 }}>{exam.title}</div>
                        <div style={{ fontSize: '10px', color: colors.gray400, fontFamily: fonts.mono }}>{exam.id.slice(0, 12)}…</div>
                      </td>
                      <td style={{ ...table.td, fontFamily: fonts.mono }}>{exam.duration_minutes}m</td>
                      <td style={table.td}>
                        <select value={exam.status}
                          onChange={e => handleStatusChange(exam.id, e.target.value)}
                          style={{ fontFamily: fonts.ui, fontSize: '12px', padding: '4px 8px', border: `1px solid ${colors.gray200}`, borderRadius: radius.sm, background: colors.white, color: colors.gray700, cursor: 'pointer' }}>
                          {['scheduled', 'active', 'completed', 'terminated'].map(s => (
                            <option key={s} value={s}>{s}</option>
                          ))}
                        </select>
                      </td>
                      <td style={table.td}>
                        <button className="btn-danger" style={{ ...btn.danger, fontSize: '11px', padding: '4px 10px' }}
                          onClick={() => handleDelete(exam.id)}>
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      {/* Create modal */}
      {creating && (
        <div style={modal.overlay} onClick={e => e.target === e.currentTarget && setCreate(false)}>
          <div style={modal.panel} className="animate-fade-up">
            <h3 style={{ ...text.cardTitle, marginBottom: '4px' }}>Create New Exam</h3>
            <p style={{ ...text.body, marginBottom: '20px' }}>Students will see this in their dashboard.</p>
            {[['Title', 'title', 'text', 'e.g. Python Midterm'], ['Duration (minutes)', 'duration_minutes', 'number', '60'], ['Description', 'description', 'text', 'Optional']].map(([l, k, t, ph]) => (
              <div key={k} style={{ marginBottom: '14px' }}>
                <label style={text.sectionTitle}>{l}</label>
                <div style={{ height: '4px' }} />
                <input type={t} placeholder={ph} value={form[k]}
                  onChange={e => setForm(p => ({ ...p, [k]: t === 'number' ? parseInt(e.target.value) || 60 : e.target.value }))}
                  style={{ fontFamily: fonts.ui, fontSize: '14px', background: colors.white, border: `1px solid ${colors.gray300}`, borderRadius: radius.md, color: colors.gray900, padding: '9px 12px', width: '100%', outline: 'none' }} />
              </div>
            ))}
            {formErr && <div style={{ background: colors.dangerLight, border: `1px solid ${colors.dangerBorder}`, borderRadius: radius.md, padding: '10px 14px', color: colors.dangerMid, fontSize: '13px', marginBottom: '14px' }}>{formErr}</div>}
            <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
              <button className="btn-secondary" style={{ ...btn.secondary, flex: 1 }} onClick={() => { setCreate(false); setFormErr(''); }}>Cancel</button>
              <button className="btn-primary" style={{ ...btn.primary, flex: 2 }} onClick={handleCreate} disabled={!form.title.trim()}>Create Exam</button>
            </div>
          </div>
        </div>
      )}

      {/* Terminate confirm */}
      {termConf && (
        <div style={modal.overlay}>
          <div style={modal.panel} className="animate-fade-up">
            <h3 style={{ ...text.cardTitle, color: colors.dangerMid, marginBottom: '8px' }}>Terminate Session?</h3>
            <p style={{ ...text.body, marginBottom: '6px' }}>
              <strong style={{ color: colors.gray900 }}>{termConf.user_name}</strong> — {termConf.exam_title}
            </p>
            <p style={{ ...text.caption, marginBottom: '24px' }}>
              Score: {termConf.risk_score.toFixed(1)} · {termConf.violation_count} violations. This cannot be undone.
            </p>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button className="btn-secondary" style={{ ...btn.secondary, flex: 1 }} onClick={() => setTerm(null)}>Cancel</button>
              <button className="btn-danger" style={{ ...btn.danger, flex: 2, justifyContent: 'center' }} onClick={confirmTerminate}>Terminate</button>
            </div>
          </div>
        </div>
      )}

      {/* Terminate all confirm */}
      {termAll && (
        <div style={modal.overlay}>
          <div style={modal.panel} className="animate-fade-up">
            <h3 style={{ ...text.cardTitle, color: colors.dangerMid, marginBottom: '8px' }}>Terminate All Sessions?</h3>
            <p style={{ ...text.body, marginBottom: '6px' }}>
              This will immediately end <strong style={{ color: colors.gray900 }}>{sessions.length}</strong> active session(s).
            </p>
            <p style={{ ...text.caption, marginBottom: '24px' }}>All candidates will be notified. This cannot be undone.</p>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button className="btn-secondary" style={{ ...btn.secondary, flex: 1 }} onClick={() => setTermAll(false)}>Cancel</button>
              <button className="btn-danger" style={{ ...btn.danger, flex: 2, justifyContent: 'center' }} onClick={handleTerminateAll}>
                Terminate All {sessions.length} Sessions
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}