// src/pages/ExamPage.js
import React, { useRef, useEffect, useState, useCallback } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { examAPI, monitorAPI } from '../services/api';
import { useProctorSocket } from '../hooks/useProctorSocket';
import RiskMeter from '../components/RiskMeter';
import ViolationAlert from '../components/ViolationAlert';

const FRAME_INTERVAL_MS = 1500;  // send frame every 1.5 seconds

export default function ExamPage() {
  const { id }              = useParams();
  const [searchParams]      = useSearchParams();
  const sessionId           = searchParams.get('session');
  const navigate            = useNavigate();

  const videoRef  = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const timerRef  = useRef(null);

  const [exam,        setExam]       = useState(null);
  const [timeLeft,    setTimeLeft]   = useState(null);
  const [submitting,  setSubmitting] = useState(false);
  const [fullscreen,  setFullscreen] = useState(false);

  const {
    connected, riskData, alerts, terminated,
    sendFrame, sendBrowserEvent,
  } = useProctorSocket(sessionId);

  // ── Load exam info ─────────────────────────────────────────────
  useEffect(() => {
    examAPI.get(id).then(r => {
      setExam(r.data);
      setTimeLeft(r.data.duration_minutes * 60);
    });
  }, [id]);

  // ── Countdown timer ────────────────────────────────────────────
  useEffect(() => {
    if (timeLeft === null) return;
    if (timeLeft <= 0) { handleSubmit(); return; }
    const t = setTimeout(() => setTimeLeft(t => t - 1), 1000);
    return () => clearTimeout(t);
  }, [timeLeft]);

  // ── Start webcam ───────────────────────────────────────────────
  useEffect(() => {
    startCamera();
    return () => {
      stopCamera();
      clearInterval(timerRef.current);
    };
  }, []);

  // ── Start frame sending loop once camera is ready ──────────────
  useEffect(() => {
    if (!connected) return;
    timerRef.current = setInterval(captureAndSendFrame, FRAME_INTERVAL_MS);
    return () => clearInterval(timerRef.current);
  }, [connected]);

  // ── Browser event listeners ────────────────────────────────────
  useEffect(() => {
    const onVisibility = () => {
      if (document.hidden) sendBrowserEvent('TAB_SWITCH');
    };
    const onBlur = () => sendBrowserEvent('WINDOW_BLUR');
    const onFullscreenChange = () => {
      if (!document.fullscreenElement) sendBrowserEvent('FULLSCREEN_EXIT');
    };
    const onCopy  = () => sendBrowserEvent('COPY_PASTE');
    const onPaste = () => sendBrowserEvent('COPY_PASTE');

    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener('blur', onBlur);
    document.addEventListener('fullscreenchange', onFullscreenChange);
    document.addEventListener('copy',  onCopy);
    document.addEventListener('paste', onPaste);

    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('blur', onBlur);
      document.removeEventListener('fullscreenchange', onFullscreenChange);
      document.removeEventListener('copy',  onCopy);
      document.removeEventListener('paste', onPaste);
    };
  }, [sendBrowserEvent]);

  // ── Auto-terminate when backend says so ───────────────────────
  useEffect(() => {
    if (terminated) {
      alert('Your exam has been terminated due to suspicious activity.');
      navigate('/dashboard');
    }
  }, [terminated, navigate]);

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width:320, height:240, facingMode:'user' }
      });
      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
    } catch (e) {
      console.error('Camera failed:', e);
    }
  };

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach(t => t.stop());
  };

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

  const handleSubmit = async () => {
    if (submitting) return;
    if (!window.confirm('Submit exam? This cannot be undone.')) return;
    setSubmitting(true);
    clearInterval(timerRef.current);
    stopCamera();
    try {
      await examAPI.submit(id);
      navigate('/dashboard');
    } catch (e) {
      alert(e.response?.data?.detail || 'Submission failed');
      setSubmitting(false);
    }
  };

  const enterFullscreen = () => {
    document.documentElement.requestFullscreen?.();
    setFullscreen(true);
  };

  const fmtTime = (s) => {
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
  };

  const riskLevel = riskData?.risk_level || 'SAFE';
  const riskScore = riskData?.current_score || 0;

  const levelColors = {
    SAFE:'var(--safe)', WARNING:'var(--warn)',
    HIGH:'var(--high)', CRITICAL:'var(--critical)',
  };

  return (
    <div style={{
      minHeight:'100vh', background:'var(--bg)',
      display:'flex', flexDirection:'column',
    }}>
      {/* Top bar */}
      <div style={{
        display:'flex', alignItems:'center', justifyContent:'space-between',
        padding:'12px 24px', background:'var(--bg2)',
        borderBottom:'1px solid var(--border)', position:'sticky', top:0, zIndex:50,
      }}>
        <div style={{ display:'flex', alignItems:'center', gap:'16px' }}>
          <span style={{ fontFamily:'Syne', fontWeight:700 }}>
            {exam?.title || 'Loading...'}
          </span>
          <div style={{
            display:'flex', alignItems:'center', gap:'6px',
            background: connected ? '#052e16' : '#1c0a03',
            border:`1px solid ${connected ? '#14532d' : '#78350f'}`,
            borderRadius:'20px', padding:'3px 10px', fontSize:'11px',
            color: connected ? 'var(--safe)' : 'var(--warn)',
          }}>
            <span style={{ animation:'pulse 2s infinite' }}>●</span>
            {connected ? 'Monitoring Active' : 'Connecting...'}
          </div>
        </div>

        <div style={{ display:'flex', alignItems:'center', gap:'20px' }}>
          {/* Timer */}
          <div style={{
            fontFamily:'DM Mono', fontSize:'20px', fontWeight:500,
            color: timeLeft < 300 ? 'var(--high)' : 'var(--text)',
          }}>
            {timeLeft !== null ? fmtTime(timeLeft) : '--:--'}
          </div>

          {/* Risk badge */}
          <div style={{
            background:'var(--bg3)', borderRadius:'8px',
            padding:'6px 12px', fontSize:'12px',
            border:`1px solid ${levelColors[riskLevel]}`,
            color: levelColors[riskLevel],
            fontFamily:'Syne', fontWeight:700,
          }}>
            {riskLevel} · {riskScore.toFixed(1)}
          </div>

          <button className="btn-primary"
            style={{ padding:'8px 18px', fontSize:'13px' }}
            onClick={handleSubmit} disabled={submitting}>
            {submitting ? 'Submitting...' : 'Submit Exam'}
          </button>
        </div>
      </div>

      {/* Main layout */}
      <div style={{
        flex:1, display:'grid',
        gridTemplateColumns:'1fr 280px',
        gap:'0', height:'calc(100vh - 57px)',
      }}>
        {/* Exam content area */}
        <div style={{
          padding:'32px', overflowY:'auto',
          borderRight:'1px solid var(--border)',
        }}>
          <div className="card" style={{ maxWidth:'700px' }}>
            <h2 style={{ fontSize:'18px', marginBottom:'16px' }}>
              {exam?.title}
            </h2>
            <div style={{
              background:'var(--bg)', borderRadius:'8px', padding:'20px',
              color:'var(--muted)', fontSize:'13px', lineHeight:2,
              border:'1px solid var(--border)',
            }}>
              <p>Your exam content will be displayed here.</p>
              <p style={{ marginTop:'12px' }}>
                The proctoring system is actively monitoring your session.
                Maintain focus on this window and avoid looking away from the screen.
              </p>
            </div>
          </div>

          {/* Fullscreen hint */}
          {!fullscreen && (
            <div style={{
              marginTop:'16px', background:'#0c1a2e',
              border:'1px solid #1e3a5f', borderRadius:'8px',
              padding:'12px 16px', fontSize:'12px', color:'var(--muted)',
              display:'flex', alignItems:'center', justifyContent:'space-between',
            }}>
              <span>For best experience, use fullscreen mode.</span>
              <button className="btn-ghost" style={{ fontSize:'11px', padding:'4px 12px' }}
                onClick={enterFullscreen}>
                Enter Fullscreen
              </button>
            </div>
          )}
        </div>

        {/* Right sidebar — webcam + risk */}
        <div style={{
          display:'flex', flexDirection:'column', gap:'0',
          background:'var(--bg2)',
        }}>
          {/* Webcam preview */}
          <div style={{ position:'relative', background:'#000' }}>
            <video ref={videoRef} autoPlay playsInline muted
              style={{
                width:'100%', aspectRatio:'4/3',
                objectFit:'cover', transform:'scaleX(-1)',
                display:'block',
              }}
            />
            <canvas ref={canvasRef} style={{ display:'none' }}/>
            <div style={{
              position:'absolute', bottom:8, left:8,
              background:'rgba(0,0,0,0.7)', borderRadius:'20px',
              padding:'3px 10px', fontSize:'10px', color:'var(--safe)',
            }}>
              ● Camera Active
            </div>
          </div>

          {/* Risk meter */}
          <div style={{ padding:'16px', borderBottom:'1px solid var(--border)' }}>
            <div style={{ fontSize:'11px', color:'var(--muted)', marginBottom:'8px' }}>
              RISK SCORE
            </div>
            <RiskMeter score={riskScore} level={riskLevel} />
          </div>

          {/* Module breakdown */}
          {riskData && (
            <div style={{ padding:'16px', borderBottom:'1px solid var(--border)' }}>
              <div style={{ fontSize:'11px', color:'var(--muted)', marginBottom:'10px' }}>
                MODULE SCORES
              </div>
              {[
                ['Face',    riskData.face_score],
                ['Pose',    riskData.pose_score],
                ['Objects', riskData.object_score],
                ['Audio',   riskData.audio_score],
                ['Browser', riskData.browser_score],
              ].map(([name, val]) => (
                <div key={name} style={{
                  display:'flex', alignItems:'center', gap:'8px',
                  marginBottom:'6px',
                }}>
                  <span style={{ fontSize:'11px', color:'var(--muted)', width:50 }}>{name}</span>
                  <div style={{
                    flex:1, height:4, background:'var(--border)', borderRadius:'2px',
                  }}>
                    <div style={{
                      height:'100%', borderRadius:'2px',
                      width:`${Math.min(100, (val||0))}%`,
                      background: (val||0) > 60 ? 'var(--high)' :
                                  (val||0) > 30 ? 'var(--warn)' : 'var(--safe)',
                      transition:'width 0.5s',
                    }}/>
                  </div>
                  <span style={{ fontSize:'10px', color:'var(--muted)', width:28, textAlign:'right' }}>
                    {(val||0).toFixed(0)}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Alert feed */}
          <div style={{ flex:1, padding:'16px', overflowY:'auto' }}>
            <div style={{ fontSize:'11px', color:'var(--muted)', marginBottom:'10px' }}>
              ALERTS
            </div>
            {alerts.length === 0 ? (
              <div style={{ color:'var(--muted)', fontSize:'11px' }}>
                No alerts yet.
              </div>
            ) : (
              <div style={{ display:'flex', flexDirection:'column', gap:'6px' }}>
                {alerts.map(a => (
                  <ViolationAlert key={a.id} alert={a} />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}