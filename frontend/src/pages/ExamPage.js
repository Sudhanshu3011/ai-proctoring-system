// src/pages/ExamPage.js — style/logic separated, professional theme
import React, { useRef, useEffect, useState, useCallback } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { examAPI } from '../services/api';
import { useProctorSocket } from '../hooks/useProctorSocket';
import RiskMeter from '../components/RiskMeter';
import FaceVerifyModal from '../components/FaceVerifyModal';
import ViolationSidebar from '../components/ViolationSidebar';
import { colors, fonts, radius, shadow, statusConfig } from '../styles/theme';
import { btn, modal, text, statusPill } from '../styles/styles';

// ── Constants ─────────────────────────────────────────────────────
const FRAME_INTERVAL_MS = 1500;
const TAB_SWITCH_LIMIT = 2;
const TAB_GRACE_MS = 3000;

// ── Styles (all presentation, zero logic) ────────────────────────
const S = {
  page: {
    minHeight: '100vh', background: colors.gray50,
    display: 'flex', flexDirection: 'column',
    fontFamily: fonts.ui, color: colors.gray900,
  },
  navbar: {
    background: colors.white, borderBottom: `1px solid ${colors.gray200}`,
    padding: '0 20px', height: '54px',
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    position: 'sticky', top: 0, zIndex: 50, boxShadow: shadow.xs,
    gap: '16px',
  },
  examTitle: {
    fontFamily: fonts.display, fontSize: '16px', fontWeight: 400,
    color: colors.gray900, letterSpacing: '-0.02em',
    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
    maxWidth: '280px',
  },
  timer: (urgent) => ({
    fontFamily: fonts.mono, fontSize: '20px', fontWeight: 600,
    color: urgent ? colors.dangerMid : colors.gray900,
    background: urgent ? colors.dangerLight : colors.gray100,
    border: `1px solid ${urgent ? colors.dangerBorder : colors.gray200}`,
    borderRadius: radius.md, padding: '4px 14px', letterSpacing: '0.04em',
  }),
  riskBadge: (level) => {
    const c = statusConfig[level] || statusConfig.SAFE;
    return {
      background: c.bg, border: `1px solid ${c.border}`,
      borderRadius: radius.md, padding: '4px 12px',
      fontSize: '12px', fontWeight: 700, color: c.color,
      fontFamily: fonts.ui, letterSpacing: '-0.01em',
    };
  },
  submitBtn: {
    ...btn.primary, padding: '8px 18px', fontSize: '13px',
  },
  body: {
    flex: 1, display: 'grid', gridTemplateColumns: '1fr 272px',
    overflow: 'hidden', height: 'calc(100vh - 54px)',
  },
  examArea: {
    padding: '32px', overflowY: 'auto', background: colors.white,
    borderRight: `1px solid ${colors.gray200}`,
  },
  sidebar: {
    display: 'flex', flexDirection: 'column',
    background: colors.white, overflow: 'hidden',
  },
  webcamWrap: {
    position: 'relative', background: '#000', flexShrink: 0,
  },
  webcamPill: {
    position: 'absolute', bottom: 6, left: 8,
    background: 'rgba(0,0,0,0.55)', borderRadius: '99px',
    padding: '2px 8px', fontSize: '10px', color: '#6ee7b7',
    fontFamily: fonts.mono,
  },
  sideSection: (noBorder) => ({
    padding: '12px 14px',
    borderBottom: noBorder ? 'none' : `1px solid ${colors.gray200}`,
    flexShrink: 0,
  }),
  sectionLabel: {
    fontSize: '10px', fontWeight: 700, color: colors.gray400,
    textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '8px',
    fontFamily: fonts.ui,
  },
  modRow: {
    display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '5px',
  },
  modLabel: {
    fontSize: '11px', color: colors.gray500, width: '48px', fontFamily: fonts.ui,
  },
  modTrack: {
    flex: 1, height: '3px', background: colors.gray200, borderRadius: '99px',
  },
  modFill: (v) => ({
    height: '100%', borderRadius: '99px',
    width: `${Math.min(100, v || 0)}%`,
    background: (v || 0) > 60 ? colors.dangerMid : (v || 0) > 30 ? colors.warningMid : colors.gray300,
    transition: 'width 0.6s ease',
  }),
  modVal: {
    fontSize: '10px', color: colors.gray400, width: '22px',
    textAlign: 'right', fontFamily: fonts.mono,
  },
  violSection: {
    flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column',
  },
  violHeader: {
    padding: '10px 14px 6px',
    borderBottom: `1px solid ${colors.gray200}`, flexShrink: 0,
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  },
  violCount: (n) => ({
    background: n > 0 ? colors.dangerLight : colors.gray100,
    color: n > 0 ? colors.dangerMid : colors.gray400,
    borderRadius: '99px', padding: '1px 7px',
    fontSize: '10px', fontWeight: 700, fontFamily: fonts.mono,
  }),
  violScroll: {
    flex: 1, overflowY: 'auto', padding: '8px 14px',
  },
  fsWarning: {
    position: 'fixed', top: 0, left: 0, right: 0, zIndex: 200,
    background: colors.dangerMid, padding: '10px 20px',
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  },
  tabWarning: {
    position: 'fixed', bottom: 16, left: '50%', transform: 'translateX(-50%)',
    background: colors.white, border: `1px solid ${colors.dangerBorder}`,
    borderLeft: `3px solid ${colors.dangerMid}`, borderRadius: radius.md,
    padding: '8px 18px', zIndex: 100, boxShadow: shadow.md,
    fontSize: '12px', color: colors.dangerMid, fontWeight: 600,
    whiteSpace: 'nowrap',
  },
  // Modals
  termOverlay: {
    ...modal.overlay, zIndex: 999, background: 'rgba(0,0,0,0.75)',
  },
  termPanel: {
    background: colors.white, borderRadius: radius.xl,
    padding: '40px', maxWidth: '460px', width: '100%',
    textAlign: 'center', boxShadow: shadow.xl,
  },
  termIcon: {
    width: '60px', height: '60px', borderRadius: '50%',
    background: colors.dangerLight, border: `2px solid ${colors.dangerBorder}`,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    margin: '0 auto 18px', fontSize: '24px',
  },
  submitOverlay: { ...modal.overlay, zIndex: 200 },
  submitPanel: {
    background: colors.white, borderRadius: radius.xl,
    padding: '32px', maxWidth: '400px', width: '100%',
    boxShadow: shadow.xl, textAlign: 'center',
  },
  envOverlay: { ...modal.overlay, zIndex: 300 },
  envPanel: {
    background: colors.white, borderRadius: radius.xl,
    padding: '36px', maxWidth: '420px', width: '100%',
    boxShadow: shadow.xl,
  },
  envRow: {
    display: 'flex', alignItems: 'center', gap: '12px',
    padding: '10px 0', borderBottom: `1px solid ${colors.gray100}`,
  },
  envDot: (val) => ({
    width: '24px', height: '24px', borderRadius: '50%', flexShrink: 0,
    background: val === true ? colors.successLight : val === false ? colors.dangerLight : colors.gray100,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: '12px',
  }),
  envStatus: (val) => ({
    fontSize: '12px', fontWeight: 600,
    color: val === true ? colors.successMid : val === false ? colors.dangerMid : colors.gray400,
  }),
};

// ── Sub-components ────────────────────────────────────────────────
function TerminationModal({ reason, onAck }) {
  return (
    <div style={S.termOverlay}>
      <div style={S.termPanel} className="animate-fade-up">
        <div style={S.termIcon}>&#9888;</div>
        <h2 style={{
          fontFamily: fonts.display, fontSize: '20px', fontWeight: 400,
          color: colors.gray900, marginBottom: '10px', letterSpacing: '-0.02em'
        }}>
          Exam Session Terminated
        </h2>
        <p style={{ color: colors.gray600, fontSize: '13px', lineHeight: 1.7, marginBottom: '8px' }}>
          {reason || 'Your exam session has been terminated.'}
        </p>
        <p style={{ color: colors.gray400, fontSize: '12px', marginBottom: '28px' }}>
          Your responses up to this point have been saved. Contact your invigilator if you believe this is an error.
        </p>
        <button style={{ ...btn.danger, padding: '10px 28px', justifyContent: 'center' }}
          onClick={onAck}>
          Acknowledge &amp; Exit
        </button>
      </div>
    </div>
  );
}

function SubmitModal({ onConfirm, onCancel }) {
  return (
    <div style={S.submitOverlay}>
      <div style={S.submitPanel} className="animate-fade-up">
        <h3 style={{
          fontFamily: fonts.display, fontSize: '18px', fontWeight: 400,
          color: colors.gray900, marginBottom: '8px', letterSpacing: '-0.02em'
        }}>
          Submit Exam?
        </h3>
        <p style={{ color: colors.gray500, fontSize: '13px', marginBottom: '24px', lineHeight: 1.6 }}>
          Once submitted, you cannot return. Ensure you have answered all questions.
        </p>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button style={{ ...btn.secondary, flex: 1 }} onClick={onCancel}>Continue Exam</button>
          <button style={{ ...btn.primary, flex: 1 }} onClick={onConfirm}>Submit Now</button>
        </div>
      </div>
    </div>
  );
}

function EnvCheckModal({ onReady }) {
  const [checks, setChecks] = useState({ camera: null, audio: null, fullscreen: null });
  const [loading, setLoad] = useState(false);

  const run = async () => {
    setLoad(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      stream.getTracks().forEach(t => t.stop());
      setChecks(p => ({ ...p, camera: true, audio: true }));
    } catch { setChecks(p => ({ ...p, camera: false, audio: false })); }
    setChecks(p => ({ ...p, fullscreen: !!document.documentElement.requestFullscreen }));
    setLoad(false);
  };

  useEffect(() => { run(); }, []);

  const allOk = Object.values(checks).every(v => v === true);
  const rows = [
    { key: 'camera', label: 'Camera accessible' },
    { key: 'audio', label: 'Microphone accessible' },
    { key: 'fullscreen', label: 'Fullscreen supported' },
  ];

  return (
    <div style={S.envOverlay}>
      <div style={S.envPanel} className="animate-fade-up">
        <h2 style={{
          fontFamily: fonts.display, fontSize: '20px', fontWeight: 400,
          color: colors.gray900, marginBottom: '4px', letterSpacing: '-0.02em'
        }}>
          Environment Check
        </h2>
        <p style={{ color: colors.gray500, fontSize: '13px', marginBottom: '20px' }}>
          Verifying your system before the exam begins.
        </p>
        {rows.map(({ key, label }) => {
          const v = checks[key];
          return (
            <div key={key} style={S.envRow}>
              <div style={S.envDot(v)}>
                {v === null ? '·' : v ? '✓' : '✗'}
              </div>
              <div style={{ flex: 1, fontSize: '13px', color: colors.gray700 }}>{label}</div>
              <div style={S.envStatus(v)}>
                {v === null ? 'Checking…' : v ? 'OK' : 'Failed'}
              </div>
            </div>
          );
        })}
        {Object.values(checks).some(v => v === false) && (
          <div style={{
            background: colors.dangerLight, border: `1px solid ${colors.dangerBorder}`,
            borderRadius: radius.md, padding: '10px 14px', fontSize: '12px',
            color: colors.dangerMid, marginTop: '14px'
          }}>
            Some checks failed. Grant camera and microphone permissions and retry.
          </div>
        )}
        <div style={{ display: 'flex', gap: '8px', marginTop: '20px' }}>
          {Object.values(checks).some(v => v === false) && (
            <button style={{ ...btn.secondary, flex: 1 }} onClick={run} disabled={loading}>
              Retry
            </button>
          )}
          <button style={{
            ...btn.primary, flex: 2, opacity: allOk ? 1 : 0.45,
            cursor: allOk ? 'pointer' : 'not-allowed'
          }}
            onClick={onReady} disabled={!allOk}>
            {allOk ? 'Proceed to Exam' : 'Waiting…'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────
export default function ExamPage() {
  const { id } = useParams();
  const [sp] = useSearchParams();
  const sessionId = sp.get('session');
  const navigate = useNavigate();

  // Refs
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const timerRef = useRef(null);
  const tabCountRef = useRef(0);
  const cooldownRef = useRef({});

  // Logic state
  const [exam, setExam] = useState(null);
  const [timeLeft, setTimeLeft] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [envDone, setEnvDone] = useState(false);
  const [verifyDone, setVerifyDone] = useState(false);
  const [termModal, setTermModal] = useState(null);
  const [showSubmit, setShowSubmit] = useState(false);
  const [isFullscreen, setFullscreen] = useState(false);
  const [fsWarning, setFsWarning] = useState(false);
  const [audioActive, setAudio] = useState(true);
  const [tabCount, setTabCount] = useState(0);
  const [wsMessages, setWsMessages] = useState([]);
  const [localViols, setLocalViols] = useState([]);

  const { connected, riskData, wsMessages: sockMessages, terminated,
    sendFrame, sendBrowserEvent } = useProctorSocket(sessionId);

  // Merge socket + local violations for sidebar
  useEffect(() => {
    if (sockMessages?.length) setWsMessages(sockMessages);
  }, [sockMessages]);

  // Load exam
  useEffect(() => {
    examAPI.get(id).then(r => {
      setExam(r.data);
      setTimeLeft(r.data.duration_minutes * 60);
    });
  }, [id]);

  // Admin-terminated via WS
  useEffect(() => {
    if (!terminated) return;
    stopCamera(); clearInterval(timerRef.current);
    if (document.fullscreenElement) document.exitFullscreen?.();
    setTermModal('Your exam has been terminated by the administrator.');
  }, [terminated]);

  // Prevent exit without submitting
  useEffect(() => {
    if (!verifyDone) return;
    const onBefore = (e) => { e.preventDefault(); e.returnValue = ''; return ''; };
    const onPop = (e) => {
      e.preventDefault();
      window.history.pushState(null, '', window.location.href);
      setShowSubmit(true);
    };
    window.addEventListener('beforeunload', onBefore);
    window.history.pushState(null, '', window.location.href);
    window.addEventListener('popstate', onPop);
    return () => {
      window.removeEventListener('beforeunload', onBefore);
      window.removeEventListener('popstate', onPop);
    };
  }, [verifyDone]);

  // Countdown
  useEffect(() => {
    if (!verifyDone || timeLeft === null) return;
    if (timeLeft <= 0) { doSubmit(); return; }
    const t = setTimeout(() => setTimeLeft(p => p - 1), 1000);
    return () => clearTimeout(t);
  }, [timeLeft, verifyDone]);

  // Fullscreen
  useEffect(() => {
    if (verifyDone) enterFullscreen();
  }, [verifyDone]);

  useEffect(() => {
    const onChange = () => {
      const inFs = !!document.fullscreenElement;
      setFullscreen(inFs);
      if (!inFs && verifyDone && !termModal) {
        sendBrowserEvent('FULLSCREEN_EXIT');
        setFsWarning(true);
        pushLocalViol('FULLSCREEN_EXIT', 'WARNING',
          'Fullscreen exited — this has been logged.', 'Return to fullscreen immediately.');
        setTimeout(() => setFsWarning(false), 6000);
      }
    };
    document.addEventListener('fullscreenchange', onChange);
    return () => document.removeEventListener('fullscreenchange', onChange);
  }, [verifyDone, termModal]);

  // Tab switching
  useEffect(() => {
    if (!verifyDone) return;
    let blurTimer = null;
    const onVis = () => {
      if (!document.hidden) return;
      blurTimer = setTimeout(() => {
        tabCountRef.current += 1;
        const n = tabCountRef.current;
        setTabCount(n);
        sendBrowserEvent('TAB_SWITCH');
        pushLocalViol('TAB_SWITCH',
          n >= TAB_SWITCH_LIMIT - 1 ? 'HIGH' : 'WARNING',
          `Tab switch detected (${n} of ${TAB_SWITCH_LIMIT - 1} allowed).`,
          n >= TAB_SWITCH_LIMIT - 1 ? 'Next switch will terminate the exam.' : 'Return immediately.');
        if (n >= TAB_SWITCH_LIMIT) {
          setTermModal(`Exam terminated: tab switched ${n} time(s). Limit is ${TAB_SWITCH_LIMIT - 1}.`);
          doSubmit();
        }
      }, TAB_GRACE_MS);
    };
    const onBack = () => { if (!document.hidden && blurTimer) { clearTimeout(blurTimer); blurTimer = null; } };
    document.addEventListener('visibilitychange', onVis);
    document.addEventListener('visibilitychange', onBack);
    return () => {
      document.removeEventListener('visibilitychange', onVis);
      document.removeEventListener('visibilitychange', onBack);
      if (blurTimer) clearTimeout(blurTimer);
    };
  }, [verifyDone]);

  // Copy-paste
  useEffect(() => {
    if (!verifyDone) return;
    const handler = () => {
      sendBrowserEvent('COPY_PASTE');
      pushLocalViol('COPY_PASTE', 'WARNING', 'Copy/paste detected.', 'This is not permitted during the exam.');
    };
    document.addEventListener('copy', handler);
    document.addEventListener('paste', handler);
    return () => { document.removeEventListener('copy', handler); document.removeEventListener('paste', handler); };
  }, [verifyDone]);

  // Audio check
  useEffect(() => {
    if (!verifyDone) return;
    const t = setInterval(async () => {
      const devs = await navigator.mediaDevices.enumerateDevices().catch(() => []);
      setAudio(devs.some(d => d.kind === 'audioinput'));
    }, 10000);
    return () => clearInterval(t);
  }, [verifyDone]);

  // Camera + frame sending
  useEffect(() => {
    if (!verifyDone) return;
    startCamera();
    return () => { stopCamera(); clearInterval(timerRef.current); };
  }, [verifyDone]);

  useEffect(() => {
    if (!connected || !verifyDone) return;
    timerRef.current = setInterval(captureFrame, FRAME_INTERVAL_MS);
    return () => clearInterval(timerRef.current);
  }, [connected, verifyDone]);

  // Helpers
  const startCamera = async () => {
    try {
      const s = await navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240, facingMode: 'user' } });
      streamRef.current = s;
      if (videoRef.current) videoRef.current.srcObject = s;
    } catch (e) { console.error('Camera:', e); }
  };
  const stopCamera = () => { streamRef.current?.getTracks().forEach(t => t.stop()); };
  const enterFullscreen = () => { document.documentElement.requestFullscreen?.().then(() => setFullscreen(true)).catch(() => { }); };

  const pushLocalViol = useCallback((vtype, severity, message, action) => {
    const now = Date.now();
    const last = cooldownRef.current[vtype] || 0;
    if (now - last < 8000) return;
    cooldownRef.current[vtype] = now;
    setLocalViols(prev => [...prev.slice(-9), { type: 'VIOLATION_DETAIL', vtype, severity, message, action, confidence: 1.0 }]);
  }, []);

  const captureFrame = useCallback(() => {
    const c = canvasRef.current, v = videoRef.current;
    if (!c || !v || v.readyState < 2) return;
    c.width = 320; c.height = 240;
    c.getContext('2d').drawImage(v, 0, 0, 320, 240);
    sendFrame(c.toDataURL('image/jpeg', 0.7).split(',')[1]);
  }, [sendFrame]);

  const doSubmit = async () => {
    if (submitting) return;
    setSubmitting(true);
    clearInterval(timerRef.current);
    stopCamera();
    if (document.fullscreenElement) document.exitFullscreen?.();
    try {
      await examAPI.submit(id);
      navigate(`/report?session=${sessionId}`);
    } catch { navigate('/dashboard'); }
  };

  const fmtTime = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

  const level = riskData?.risk_level || 'SAFE';
  const score = riskData?.current_score || 0;
  const cfg = statusConfig[level] || statusConfig.SAFE;
  const urgent = timeLeft !== null && timeLeft < 300;
  const allViols = [...wsMessages, ...localViols];

  return (
    <div style={S.page}>
      <style>{`@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.35}}`}</style>

      {/* Modals */}
      {termModal && <TerminationModal reason={termModal} onAck={() => navigate('/dashboard')} />}
      {!envDone && <EnvCheckModal onReady={() => setEnvDone(true)} />}
      {envDone && !verifyDone && sessionId && (
        <FaceVerifyModal sessionId={sessionId} onVerified={() => setVerifyDone(true)} onFailed={() => navigate('/dashboard')} />
      )}
      {showSubmit && <SubmitModal onConfirm={() => { setShowSubmit(false); doSubmit(); }} onCancel={() => setShowSubmit(false)} />}

      {/* Fullscreen warning */}
      {fsWarning && (
        <div style={S.fsWarning}>
          <span style={{ color: '#fff', fontSize: '13px', fontWeight: 600 }}>
            Fullscreen exited — violation logged.
          </span>
          <button onClick={enterFullscreen} style={{
            background: '#fff', color: colors.dangerMid,
            border: 'none', borderRadius: radius.md, padding: '4px 14px',
            fontSize: '12px', fontWeight: 700, cursor: 'pointer'
          }}>
            Return to Fullscreen
          </button>
        </div>
      )}

      {/* Tab warning */}
      {tabCount > 0 && (
        <div style={S.tabWarning}>
          Tab switch warning: {tabCount} / {TAB_SWITCH_LIMIT - 1} allowed.
          {TAB_SWITCH_LIMIT - tabCount <= 1 && '  Next switch terminates the exam.'}
        </div>
      )}

      {/* Navbar */}
      <nav style={{ ...S.navbar, opacity: verifyDone ? 1 : 0.4 }}>
        <div style={{ overflow: 'hidden', flex: 1 }}>
          <div style={S.examTitle}>{exam?.title || 'Loading…'}</div>
          <div style={{ fontSize: '11px', color: colors.gray400, fontFamily: fonts.mono }}>
            {exam?.duration_minutes}m exam
          </div>
        </div>

        {/* Monitoring status pills */}
        <div style={{ display: 'flex', gap: '6px' }}>
          {[
            { label: 'Proctoring', ok: connected },
            { label: 'Audio', ok: audioActive },
            { label: 'Fullscreen', ok: isFullscreen },
          ].map(({ label, ok }) => (
            <div key={label} style={statusPill(ok)}>
              <span style={{
                width: 5, height: 5, borderRadius: '50%',
                background: ok ? colors.successMid : colors.dangerMid,
                display: 'inline-block',
                animation: ok ? 'none' : 'pulse 1.5s infinite',
              }} />
              {label}
            </div>
          ))}
        </div>

        {/* Timer + risk + submit */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
          <span style={S.timer(urgent)}>{timeLeft !== null ? fmtTime(timeLeft) : '--:--'}</span>
          <span style={S.riskBadge(level)}>
            {cfg.label} · {score.toFixed(1)}
            {riskData?.cheat_probability ? ` · P:${(riskData.cheat_probability * 100).toFixed(0)}%` : ''}
          </span>
          <button style={S.submitBtn}
            onClick={() => setShowSubmit(true)}
            disabled={submitting || !verifyDone}>
            {submitting ? 'Submitting…' : 'Submit Exam'}
          </button>
        </div>
      </nav>

      {/* Main grid */}
      <div style={{ ...S.body, opacity: verifyDone ? 1 : 0.15, pointerEvents: verifyDone ? 'auto' : 'none' }}>

        {/* Exam content */}
        <div style={S.examArea}>
          <div style={{ maxWidth: '680px' }}>
            <h2 style={{
              fontFamily: fonts.display, fontSize: '20px', fontWeight: 400,
              color: colors.gray900, letterSpacing: '-0.02em', marginBottom: '16px'
            }}>
              {exam?.title}
            </h2>
            <div style={{
              background: colors.gray50, border: `1px solid ${colors.gray200}`,
              borderRadius: radius.lg, padding: '20px', color: colors.gray600,
              fontSize: '13px', lineHeight: 2
            }}>
              <p>Your exam questions appear here.</p>
              <p style={{ marginTop: '12px', color: colors.gray400, fontSize: '12px' }}>
                Proctoring is active. Do not switch tabs, look away, or exit fullscreen.
              </p>
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div style={S.sidebar}>
          {/* Webcam */}
          <div style={S.webcamWrap}>
            <video ref={videoRef} autoPlay playsInline muted style={{
              width: '100%', aspectRatio: '4/3', objectFit: 'cover',
              transform: 'scaleX(-1)', display: 'block',
            }} />
            <canvas ref={canvasRef} style={{ display: 'none' }} />
            <div style={S.webcamPill}>● live</div>
          </div>

          {/* Risk meter */}
          <div style={S.sideSection()}>
            <div style={S.sectionLabel}>Risk Score</div>
            <RiskMeter score={score} level={level} />
            {(riskData?.cheat_probability || 0) > 0 && (
              <div style={{ marginTop: '8px' }}>
                <div style={{
                  display: 'flex', justifyContent: 'space-between',
                  fontSize: '10px', color: colors.gray400, marginBottom: '3px'
                }}>
                  <span>Cheat probability</span>
                  <span style={{ fontWeight: 700, color: cfg.color, fontFamily: fonts.mono }}>
                    {(riskData.cheat_probability * 100).toFixed(1)}%
                  </span>
                </div>
                <div style={{ height: '3px', background: colors.gray200, borderRadius: '99px' }}>
                  <div style={{
                    height: '100%', borderRadius: '99px',
                    width: `${riskData.cheat_probability * 100}%`,
                    background: cfg.color, transition: 'width 0.5s'
                  }} />
                </div>
              </div>
            )}
          </div>

          {/* Module scores */}
          {riskData && (
            <div style={S.sideSection()}>
              <div style={S.sectionLabel}>Modules</div>
              {[['Face', riskData.face_score], ['Pose', riskData.pose_score],
              ['Objects', riskData.object_score], ['Audio', riskData.audio_score],
              ['Browser', riskData.browser_score]].map(([n, v]) => (
                <div key={n} style={S.modRow}>
                  <span style={S.modLabel}>{n}</span>
                  <div style={S.modTrack}><div style={S.modFill(v)} /></div>
                  <span style={S.modVal}>{(v || 0).toFixed(0)}</span>
                </div>
              ))}
            </div>
          )}

          {/* Violations */}
          <div style={S.violSection}>
            <div style={S.violHeader}>
              <span style={S.sectionLabel}>Violations</span>
              <span style={S.violCount(allViols.length)}>{allViols.length}</span>
            </div>
            <div style={S.violScroll}>
              <ViolationSidebar messages={allViols} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}