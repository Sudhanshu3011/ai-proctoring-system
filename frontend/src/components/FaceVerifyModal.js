// src/components/FaceVerifyModal.js — light theme
import React, { useRef, useState, useEffect, useCallback } from 'react';
import { authAPI } from '../services/api';

const CAPTURE_FPS = 8, CAPTURE_SECONDS = 3;
const TOTAL_FRAMES = CAPTURE_FPS * CAPTURE_SECONDS;
const FRAME_INTERVAL_MS = 1000 / CAPTURE_FPS;

export default function FaceVerifyModal({ sessionId, onVerified, onFailed }) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const capRef = useRef(null);

  const [phase, setPhase] = useState('ready');
  const [progress, setProgress] = useState(0);
  const [countdown, setCount] = useState(null);
  const [attempts, setAttempts] = useState(0);
  const [message, setMessage] = useState('Click the button below to begin identity verification.');
  const [score, setScore] = useState(null);
  const [liveSigs, setLiveSigs] = useState(null);

  useEffect(() => { startCamera(); return stopAll; }, []);

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' }, audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
    } catch {
      setPhase('failed'); setMessage('Camera access denied.');
    }
  };

  const stopAll = () => {
    if (capRef.current) clearInterval(capRef.current);
    streamRef.current?.getTracks().forEach(t => t.stop());
  };

  const startVerify = () => {
    let c = 3; setCount(c); setPhase('countdown');
    const t = setInterval(() => {
      c--;
      if (c <= 0) { clearInterval(t); setCount(null); beginCapture(); }
      else setCount(c);
    }, 1000);
  };

  const beginCapture = useCallback(() => {
    const collected = []; let n = 0;
    setPhase('capturing'); setProgress(0);
    capRef.current = setInterval(() => {
      const v = videoRef.current, c = canvasRef.current;
      if (!v || !c || v.readyState < 2) return;
      c.width = 320; c.height = 240;
      const ctx = c.getContext('2d');
      ctx.save(); ctx.translate(320, 0); ctx.scale(-1, 1);
      ctx.drawImage(v, 0, 0, 320, 240); ctx.restore();
      const b64 = c.toDataURL('image/jpeg', 0.8).split(',')[1];
      if (b64?.length > 100) { collected.push(b64); n++; }
      setProgress(Math.min(100, (n / TOTAL_FRAMES) * 100));
      if (n >= TOTAL_FRAMES) { clearInterval(capRef.current); submitVerify(collected); }
    }, FRAME_INTERVAL_MS);
  }, [sessionId, attempts]);

  const submitVerify = async (frameList) => {
    setPhase('verifying'); setMessage('Verifying identity and liveness...');
    try {
      const res = await authAPI.verifyFace({ session_id: sessionId, frame_sequence: frameList, fps: CAPTURE_FPS });
      const data = res.data;
      setScore(data.similarity_score); setLiveSigs(data.liveness_signals);
      if (data.verified) {
        setPhase('done'); setMessage('Identity verified. Starting exam.');
        stopAll(); setTimeout(onVerified, 1200);
      } else {
        const next = attempts + 1; setAttempts(next);
        if (next >= 3) { setPhase('failed'); setMessage(`Verification failed after 3 attempts. ${data.message}`); stopAll(); setTimeout(onFailed, 3000); }
        else { setPhase('ready'); setMessage(`Attempt ${next + 1}/3: ${data.message}`); }
      }
    } catch (e) {
      const next = attempts + 1; setAttempts(next);
      setPhase('ready'); setMessage(e.response?.data?.detail || 'Error. Try again.');
    }
  };

  const phaseCol = { ready: 'var(--accent)', countdown: 'var(--accent)', capturing: 'var(--high)', verifying: 'var(--warn)', done: 'var(--safe)', failed: 'var(--high)' };
  const col = phaseCol[phase];

  const instrMap = [
    { pct: 0, text: 'Look directly at the camera' },
    { pct: 33, text: 'Blink once naturally' },
    { pct: 66, text: 'Move your head slightly' },
  ];
  const instr = instrMap.reduce((a, ins) => progress >= ins.pct ? ins : a);

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 300,
      background: 'rgba(15,23,42,0.6)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px',
    }}>
      <div className="card animate-in" style={{ width: '100%', maxWidth: '420px', boxShadow: 'var(--shadow-lg)' }}>
        <div style={{ textAlign: 'center', marginBottom: '16px' }}>
          <h2 style={{ fontSize: '16px', fontWeight: 700, marginBottom: '3px' }}>Identity Verification</h2>
          <p style={{ color: 'var(--muted)', fontSize: '11px' }}>
            Multi-frame liveness check required before exam starts
          </p>
        </div>

        {/* Camera */}
        <div style={{ position: 'relative', borderRadius: '8px', overflow: 'hidden', background: '#000', aspectRatio: '4/3', marginBottom: '14px' }}>
          <video ref={videoRef} autoPlay playsInline muted
            style={{ width: '100%', height: '100%', objectFit: 'cover', transform: 'scaleX(-1)', display: 'block' }} />
          {(phase === 'ready' || phase === 'countdown') && (
            <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div style={{ width: 150, height: 190, border: `2px dashed ${col}`, borderRadius: '50%', boxShadow: '0 0 0 9999px rgba(0,0,0,0.2)' }} />
            </div>
          )}
          {phase === 'countdown' && countdown !== null && (
            <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.55)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <span style={{ fontSize: '72px', fontWeight: 800, color: '#fff' }}>{countdown}</span>
            </div>
          )}
          {phase === 'capturing' && (
            <>
              <div style={{ position: 'absolute', top: 8, left: 8, background: 'rgba(220,38,38,0.85)', borderRadius: '20px', padding: '3px 10px', fontSize: '10px', color: '#fff', display: 'flex', alignItems: 'center', gap: '5px' }}>
                <span style={{ animation: 'pulse 1s infinite' }}>●</span> Recording
              </div>
              <div style={{ position: 'absolute', bottom: 8, left: 0, right: 0, display: 'flex', justifyContent: 'center' }}>
                <div style={{ background: 'rgba(0,0,0,0.7)', borderRadius: '20px', padding: '6px 16px', fontSize: '11px', color: '#fff' }}>
                  {instr.text}
                </div>
              </div>
            </>
          )}
          {phase === 'verifying' && (
            <div style={{ position: 'absolute', inset: 0, background: 'rgba(15,23,42,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 10 }}>
              <div style={{ width: 36, height: 36, border: '3px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
              <div style={{ color: '#fff', fontSize: '12px' }}>Analysing {TOTAL_FRAMES} frames...</div>
            </div>
          )}
          {phase === 'done' && (
            <div style={{ position: 'absolute', inset: 0, background: 'rgba(5,150,105,0.4)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <div style={{ fontSize: '48px', color: '#fff', fontWeight: 700 }}>✓</div>
            </div>
          )}
          <div style={{ position: 'absolute', bottom: 8, right: 8, background: 'rgba(0,0,0,0.55)', borderRadius: '20px', padding: '2px 8px', fontSize: '10px', color: col, display: ['capturing', 'verifying'].includes(phase) ? 'none' : 'block' }}>
            {phase === 'ready' ? 'Camera active' : phase === 'done' ? 'Verified' : phase === 'failed' ? 'Failed' : ''}
          </div>
        </div>

        {/* Progress */}
        {phase === 'capturing' && (
          <div style={{ marginBottom: '10px' }}>
            <div style={{ height: 4, background: 'var(--bg3)', borderRadius: 2 }}>
              <div style={{ height: '100%', width: `${progress}%`, background: 'var(--high)', borderRadius: 2, transition: 'width 0.15s' }} />
            </div>
          </div>
        )}

        {/* Liveness signals */}
        {liveSigs !== null && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 6, marginBottom: '10px' }}>
            {['Blink', 'Movement', 'Variation'].map((l, i) => (
              <div key={l} style={{
                textAlign: 'center', padding: '5px 6px', borderRadius: 6, fontSize: '10px', fontWeight: 600,
                background: i < liveSigs ? 'var(--safe-lt)' : 'var(--bg3)',
                border: `1px solid ${i < liveSigs ? 'var(--safe-bd)' : 'var(--border)'}`,
                color: i < liveSigs ? 'var(--safe)' : 'var(--muted)',
              }}>
                {i < liveSigs ? '✓' : '–'} {l}
              </div>
            ))}
          </div>
        )}

        {/* Similarity */}
        {score !== null && (
          <div style={{ marginBottom: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--muted)', marginBottom: '4px' }}>
              <span>Identity match</span>
              <span style={{ fontWeight: 700, color: score >= 0.75 ? 'var(--safe)' : 'var(--high)' }}>
                {(score * 100).toFixed(1)}%
              </span>
            </div>
            <div style={{ height: 4, background: 'var(--bg3)', borderRadius: 2 }}>
              <div style={{ height: '100%', width: `${score * 100}%`, borderRadius: 2, background: score >= 0.75 ? 'var(--safe)' : score >= 0.5 ? 'var(--warn)' : 'var(--high)', transition: 'width 0.5s' }} />
            </div>
          </div>
        )}

        {/* Message */}
        <div style={{
          background: phase === 'done' ? 'var(--safe-lt)' : phase === 'failed' ? 'var(--high-lt)' : 'var(--bg3)',
          border: `1px solid ${phase === 'done' ? 'var(--safe-bd)' : phase === 'failed' ? 'var(--high-bd)' : 'var(--border)'}`,
          borderRadius: '8px', padding: '10px 14px',
          color: phase === 'done' ? 'var(--safe)' : phase === 'failed' ? 'var(--high)' : 'var(--text2)',
          fontSize: '12px', marginBottom: '14px', lineHeight: 1.5,
        }}>
          {message}
          {attempts > 0 && phase === 'ready' && (
            <div style={{ color: 'var(--muted)', fontSize: '10px', marginTop: '3px' }}>
              Attempt {attempts + 1} of 3
            </div>
          )}
        </div>

        {phase === 'ready' && (
          <button className="btn-primary" style={{ width: '100%', padding: '11px', justifyContent: 'center' }}
            onClick={startVerify}>
            Begin Verification ({CAPTURE_SECONDS}s)
          </button>
        )}
        {phase === 'failed' && (
          <div style={{ textAlign: 'center', color: 'var(--muted)', fontSize: '12px' }}>
            Returning to dashboard...
          </div>
        )}
      </div>
      <canvas ref={canvasRef} style={{ display: 'none' }} />
    </div>
  );
}