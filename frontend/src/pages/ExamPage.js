// src/pages/ExamPage.js — FINAL
// Includes: P1 face verify modal, P3 fullscreen enforcement

import React, { useRef, useEffect, useState, useCallback } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { examAPI } from '../services/api';
import { useProctorSocket } from '../hooks/useProctorSocket';
import RiskMeter from '../components/RiskMeter';
import ViolationAlert from '../components/ViolationAlert';
import FaceVerifyModal from '../components/FaceVerifyModal';

const FRAME_INTERVAL_MS = 1500;

export default function ExamPage() {
  const { id }          = useParams();
  const [searchParams]  = useSearchParams();
  const sessionId       = searchParams.get('session');
  const navigate        = useNavigate();

  const videoRef  = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const timerRef  = useRef(null);

  const [exam,         setExam]        = useState(null);
  const [timeLeft,     setTimeLeft]    = useState(null);
  const [submitting,   setSubmitting]  = useState(false);
  // P1: face verification state
  const [verifyDone,   setVerifyDone]  = useState(false);
  const [verifyFailed, setVerifyFail]  = useState(false);
  // P3: fullscreen state
  const [isFullscreen, setFullscreen]  = useState(false);
  const [fsWarning,    setFsWarning]   = useState(false);

  const { connected, riskData, alerts, terminated, sendFrame, sendBrowserEvent } =
    useProctorSocket(sessionId);

  // Load exam info
  useEffect(() => {
    examAPI.get(id).then(r => {
      setExam(r.data);
      setTimeLeft(r.data.duration_minutes * 60);
    });
  }, [id]);

  // P3: Request fullscreen as soon as verify passes
  useEffect(() => {
    if (!verifyDone) return;
    enterFullscreen();
  }, [verifyDone]);

  // P3: Fullscreen change listener — detect if student exits
  useEffect(() => {
    const onFsChange = () => {
      const inFs = !!document.fullscreenElement;
      setFullscreen(inFs);
      if (!inFs && verifyDone) {
        sendBrowserEvent('FULLSCREEN_EXIT');
        setFsWarning(true);
        setTimeout(() => setFsWarning(false), 4000);
      }
    };
    document.addEventListener('fullscreenchange', onFsChange);
    return () => document.removeEventListener('fullscreenchange', onFsChange);
  }, [verifyDone, sendBrowserEvent]);

  // Countdown timer
  useEffect(() => {
    if (timeLeft === null || !verifyDone) return;
    if (timeLeft <= 0) { handleSubmit(); return; }
    const t = setTimeout(() => setTimeLeft(t => t - 1), 1000);
    return () => clearTimeout(t);
  }, [timeLeft, verifyDone]);

  // Start webcam (only after verification passes)
  useEffect(() => {
    if (!verifyDone) return;
    startCamera();
    return () => { stopCamera(); clearInterval(timerRef.current); };
  }, [verifyDone]);

  // Start frame sending once connected
  useEffect(() => {
    if (!connected || !verifyDone) return;
    timerRef.current = setInterval(captureAndSendFrame, FRAME_INTERVAL_MS);
    return () => clearInterval(timerRef.current);
  }, [connected, verifyDone]);

  // Browser event listeners
  useEffect(() => {
    if (!verifyDone) return;
    const onVis   = () => { if (document.hidden) sendBrowserEvent('TAB_SWITCH'); };
    const onBlur  = () => sendBrowserEvent('WINDOW_BLUR');
    const onCopy  = () => sendBrowserEvent('COPY_PASTE');
    const onPaste = () => sendBrowserEvent('COPY_PASTE');

    document.addEventListener('visibilitychange', onVis);
    window.addEventListener('blur', onBlur);
    document.addEventListener('copy',  onCopy);
    document.addEventListener('paste', onPaste);

    return () => {
      document.removeEventListener('visibilitychange', onVis);
      window.removeEventListener('blur', onBlur);
      document.removeEventListener('copy',  onCopy);
      document.removeEventListener('paste', onPaste);
    };
  }, [verifyDone, sendBrowserEvent]);

  // Auto-terminate
  useEffect(() => {
    if (terminated) {
      stopCamera();
      alert('Your exam has been terminated due to suspicious activity.');
      navigate('/dashboard');
    }
  }, [terminated, navigate]);

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 320, height: 240, facingMode: 'user' },
      });
      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
    } catch (e) { console.error('Camera failed:', e); }
  };

  const stopCamera = () => streamRef.current?.getTracks().forEach(t => t.stop());

  const captureAndSendFrame = useCallback(() => {
    const canvas = canvasRef.current;
    const video  = videoRef.current;
    if (!canvas || !video || video.readyState < 2) return;
    canvas.width  = 320;
    canvas.height = 240;
    canvas.getContext('2d').drawImage(video, 0, 0, 320, 240);
    const b64 = canvas.toDataURL('image/jpeg', 0.7).split(',')[1];
    sendFrame(b64);
  }, [sendFrame]);

  const enterFullscreen = () => {
    document.documentElement.requestFullscreen?.()
      .then(() => setFullscreen(true))
      .catch(() => {});
  };

  const handleSubmit = async () => {
    if (submitting) return;
    if (!window.confirm('Submit exam? This cannot be undone.')) return;
    setSubmitting(true);
    clearInterval(timerRef.current);
    stopCamera();
    // Exit fullscreen
    if (document.fullscreenElement) document.exitFullscreen?.();
    try {
      await examAPI.submit(id);
      navigate(`/report?session=${sessionId}`);
    } catch (e) {
      alert(e.response?.data?.detail || 'Submission failed');
      setSubmitting(false);
    }
  };

  const fmtTime = (s) => {
    const m = Math.floor(s / 60);
    return `${String(m).padStart(2,'0')}:${String(s % 60).padStart(2,'0')}`;
  };

  const riskLevel = riskData?.risk_level || 'SAFE';
  const riskScore = riskData?.current_score || 0;

  const levelColors = {
    SAFE: 'var(--safe)', WARNING: 'var(--warn)',
    HIGH: 'var(--high)', CRITICAL: 'var(--critical)',
  };

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg)', display: 'flex', flexDirection: 'column' }}>

      {/* P1: Face verify modal — blocks everything until verified */}
      {!verifyDone && !verifyFailed && sessionId && (
        <FaceVerifyModal
          sessionId={sessionId}
          onVerified={() => setVerifyDone(true)}
          onFailed={() => {
            setVerifyFail(true);
            navigate('/dashboard');
          }}
        />
      )}

      {/* P3: Fullscreen exit warning banner */}
      {fsWarning && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
          background: '#1a0505', border: '1px solid #7f1d1d',
          padding: '10px 20px', textAlign: 'center',
          color: '#f87171', fontSize: '13px', fontFamily: 'Syne',
          animation: 'slideIn 0.2s ease',
        }}>
          ⚠ Fullscreen exited — this has been logged as a violation.
          <button style={{
            marginLeft: 16, background: 'var(--high)', color: 'white',
            border: 'none', borderRadius: 6, padding: '4px 12px',
            fontSize: 12, cursor: 'pointer',
          }} onClick={enterFullscreen}>
            Return to Fullscreen
          </button>
        </div>
      )}

      {/* Top bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 24px', background: 'var(--bg2)',
        borderBottom: '1px solid var(--border)',
        position: 'sticky', top: 0, zIndex: 50,
        opacity: verifyDone ? 1 : 0.3, pointerEvents: verifyDone ? 'auto' : 'none',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span style={{ fontFamily: 'Syne', fontWeight: 700 }}>
            {exam?.title || 'Loading...'}
          </span>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            background: connected ? '#052e16' : '#1c0a03',
            border: `1px solid ${connected ? '#14532d' : '#78350f'}`,
            borderRadius: '20px', padding: '3px 10px', fontSize: '11px',
            color: connected ? 'var(--safe)' : 'var(--warn)',
          }}>
            <span style={{ animation: 'pulse 2s infinite' }}>●</span>
            {connected ? 'Monitoring Active' : 'Connecting...'}
          </div>
          {/* P3: Fullscreen indicator */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            background: isFullscreen ? '#052e16' : '#1c1003',
            border: `1px solid ${isFullscreen ? '#14532d' : '#78350f'}`,
            borderRadius: '20px', padding: '3px 10px', fontSize: '11px',
            color: isFullscreen ? 'var(--safe)' : 'var(--warn)',
          }}>
            {isFullscreen ? '⛶ Fullscreen' : '⚠ Not fullscreen'}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
          <div style={{
            fontFamily: 'DM Mono', fontSize: '20px', fontWeight: 500,
            color: timeLeft < 300 ? 'var(--high)' : 'var(--text)',
          }}>
            {timeLeft !== null ? fmtTime(timeLeft) : '--:--'}
          </div>
          <div style={{
            background: 'var(--bg3)', borderRadius: '8px',
            padding: '6px 12px', fontSize: '12px',
            border: `1px solid ${levelColors[riskLevel]}`,
            color: levelColors[riskLevel],
            fontFamily: 'Syne', fontWeight: 700,
          }}>
            {riskLevel} · {riskScore.toFixed(1)}
          </div>
          <button className="btn-primary"
            style={{ padding: '8px 18px', fontSize: '13px' }}
            onClick={handleSubmit} disabled={submitting || !verifyDone}>
            {submitting ? 'Submitting...' : 'Submit Exam'}
          </button>
        </div>
      </div>

      {/* Main layout */}
      <div style={{
        flex: 1, display: 'grid', gridTemplateColumns: '1fr 280px',
        height: 'calc(100vh - 57px)',
        opacity: verifyDone ? 1 : 0.2, pointerEvents: verifyDone ? 'auto' : 'none',
      }}>
        {/* Exam content */}
        <div style={{ padding: '32px', overflowY: 'auto', borderRight: '1px solid var(--border)' }}>
          <div className="card" style={{ maxWidth: '700px' }}>
            <h2 style={{ fontSize: '18px', marginBottom: '16px' }}>{exam?.title}</h2>
            <div style={{
              background: 'var(--bg)', borderRadius: '8px', padding: '20px',
              color: 'var(--muted)', fontSize: '13px', lineHeight: 2,
              border: '1px solid var(--border)',
            }}>
              <p>Your exam content will be displayed here.</p>
              <p style={{ marginTop: '12px' }}>
                Proctoring is active. Keep focus on this window.
                Do not look away, switch tabs, or exit fullscreen.
              </p>
            </div>
          </div>
        </div>

        {/* Right sidebar */}
        <div style={{ display: 'flex', flexDirection: 'column', background: 'var(--bg2)' }}>
          {/* Webcam */}
          <div style={{ position: 'relative', background: '#000' }}>
            <video ref={videoRef} autoPlay playsInline muted
              style={{
                width: '100%', aspectRatio: '4/3',
                objectFit: 'cover', transform: 'scaleX(-1)', display: 'block',
              }}
            />
            <canvas ref={canvasRef} style={{ display: 'none' }} />
            <div style={{
              position: 'absolute', bottom: 8, left: 8,
              background: 'rgba(0,0,0,0.7)', borderRadius: '20px',
              padding: '3px 10px', fontSize: '10px', color: 'var(--safe)',
            }}>
              ● Camera Active
            </div>
          </div>

          {/* Risk meter */}
          <div style={{ padding: '16px', borderBottom: '1px solid var(--border)' }}>
            <div style={{ fontSize: '11px', color: 'var(--muted)', marginBottom: '8px' }}>
              RISK SCORE
            </div>
            <RiskMeter score={riskScore} level={riskLevel} />
          </div>

          {/* Module scores */}
          {riskData && (
            <div style={{ padding: '16px', borderBottom: '1px solid var(--border)' }}>
              <div style={{ fontSize: '11px', color: 'var(--muted)', marginBottom: '10px' }}>
                MODULE SCORES
              </div>
              {[
                ['Face',    riskData.face_score],
                ['Pose',    riskData.pose_score],
                ['Objects', riskData.object_score],
                ['Audio',   riskData.audio_score],
                ['Browser', riskData.browser_score],
              ].map(([name, val]) => (
                <div key={name} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                  <span style={{ fontSize: '11px', color: 'var(--muted)', width: 50 }}>{name}</span>
                  <div style={{ flex: 1, height: 4, background: 'var(--border)', borderRadius: '2px' }}>
                    <div style={{
                      height: '100%', borderRadius: '2px',
                      width: `${Math.min(100, val || 0)}%`,
                      background: (val || 0) > 60 ? 'var(--high)' :
                                  (val || 0) > 30 ? 'var(--warn)' : 'var(--safe)',
                      transition: 'width 0.5s',
                    }} />
                  </div>
                  <span style={{ fontSize: '10px', color: 'var(--muted)', width: 28, textAlign: 'right' }}>
                    {(val || 0).toFixed(0)}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Alert feed */}
          <div style={{ flex: 1, padding: '16px', overflowY: 'auto' }}>
            <div style={{ fontSize: '11px', color: 'var(--muted)', marginBottom: '10px' }}>ALERTS</div>
            {alerts.length === 0 ? (
              <div style={{ color: 'var(--muted)', fontSize: '11px' }}>No alerts yet.</div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {[...alerts].reverse().map(a => <ViolationAlert key={a.id} alert={a} />)}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}