// src/components/FaceVerifyModal.js — MULTI-FRAME LIVENESS VERSION
// Captures 3 seconds of frames, shows liveness guidance, sends sequence to backend

import React, { useRef, useState, useEffect, useCallback } from 'react';
import { authAPI } from '../services/api';

const CAPTURE_FPS       = 8;
const CAPTURE_SECONDS   = 3;
const TOTAL_FRAMES      = CAPTURE_FPS * CAPTURE_SECONDS;
const FRAME_INTERVAL_MS = 1000 / CAPTURE_FPS;

export default function FaceVerifyModal({ sessionId, onVerified, onFailed }) {
  const videoRef  = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const captureRef= useRef(null);

  const [phase,    setPhase]   = useState('ready');  // ready|countdown|capturing|verifying|done|failed
  const [progress, setProgress]= useState(0);
  const [countdown,setCount]   = useState(null);
  const [attempts, setAttempts]= useState(0);
  const [message,  setMessage] = useState('Click Verify to begin liveness check');
  const [score,    setScore]   = useState(null);
  const [liveSigs, setLiveSigs]= useState(null);

  useEffect(() => {
    startCamera();
    return () => { stopEverything(); };
  }, []);

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user', frameRate: CAPTURE_FPS },
      });
      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
    } catch {
      setPhase('failed');
      setMessage('Camera access denied. Cannot verify identity.');
    }
  };

  const stopEverything = () => {
    if (captureRef.current) clearInterval(captureRef.current);
    streamRef.current?.getTracks().forEach(t => t.stop());
  };

  const startVerify = () => {
    let c = 3;
    setCount(c);
    setPhase('countdown');
    const timer = setInterval(() => {
      c--;
      if (c <= 0) { clearInterval(timer); setCount(null); beginCapture(); }
      else setCount(c);
    }, 1000);
  };

  const beginCapture = useCallback(() => {
    const collected = [];
    let frameCount  = 0;
    setPhase('capturing');
    setProgress(0);

    captureRef.current = setInterval(() => {
      const canvas = canvasRef.current;
      const video  = videoRef.current;
      if (!canvas || !video || video.readyState < 2) return;

      canvas.width  = 320;
      canvas.height = 240;
      const ctx = canvas.getContext('2d');
      ctx.translate(canvas.width, 0);
      ctx.scale(-1, 1);
      ctx.drawImage(video, 0, 0, 320, 240);
      ctx.setTransform(1, 0, 0, 1, 0, 0);

      const b64 = canvas.toDataURL('image/jpeg', 0.8).split(',')[1];
      collected.push(b64);
      frameCount++;
      setProgress(Math.min(100, (frameCount / TOTAL_FRAMES) * 100));

      if (frameCount >= TOTAL_FRAMES) {
        clearInterval(captureRef.current);
        submitVerification(collected);
      }
    }, FRAME_INTERVAL_MS);
  }, [sessionId, attempts]);

  const submitVerification = async (frameList) => {
    setPhase('verifying');
    setMessage('Analysing liveness and verifying identity...');

    try {
      const res  = await authAPI.verifyFace({
        session_id:     sessionId,
        frame_sequence: frameList,
        fps:            CAPTURE_FPS,
      });
      const data = res.data;
      setScore(data.similarity_score);
      setLiveSigs(data.liveness_signals);

      if (data.verified) {
        setPhase('done');
        setMessage('Identity verified with liveness check.');
        stopEverything();
        setTimeout(() => onVerified(), 1200);
      } else {
        const nextAttempt = attempts + 1;
        setAttempts(nextAttempt);
        if (nextAttempt >= 3) {
          setPhase('failed');
          setMessage(`Verification failed after 3 attempts. ${data.message}`);
          stopEverything();
          setTimeout(() => onFailed(), 3000);
        } else {
          setPhase('ready');
          setMessage(`Attempt ${nextAttempt + 1}/3: ${data.message}`);
        }
      }
    } catch (e) {
      const nextAttempt = attempts + 1;
      setAttempts(nextAttempt);
      setPhase('ready');
      setMessage(e.response?.data?.detail || 'Verification error. Try again.');
    }
  };

  const phaseColors = {
    ready:      'var(--accent)',
    countdown:  'var(--accent)',
    capturing:  '#ef4444',
    verifying:  'var(--warn)',
    done:       'var(--safe)',
    failed:     'var(--high)',
  };
  const col = phaseColors[phase] || 'var(--muted)';

  // Capture instructions
  const captureInstructions = [
    { pct: 0,  text: 'Look at camera',         icon: '👁' },
    { pct: 33, text: 'Blink naturally',          icon: '😑' },
    { pct: 66, text: 'Slight head movement',     icon: '↔'  },
  ];
  const currentInstruction = captureInstructions.reduce(
    (acc, ins) => progress >= ins.pct ? ins : acc
  );

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 200,
      background: 'rgba(8,12,20,0.92)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px',
    }}>
      <div className="card animate-in" style={{ width: '100%', maxWidth: '460px' }}>

        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '16px' }}>
          <h2 style={{ fontSize: '18px', marginBottom: '4px' }}>Identity Verification</h2>
          <p style={{ color: 'var(--muted)', fontSize: '11px' }}>
            Multi-frame liveness check — 3 seconds required
          </p>
        </div>

        {/* Camera view */}
        <div style={{
          position: 'relative', borderRadius: '10px', overflow: 'hidden',
          background: '#000', aspectRatio: '4/3', marginBottom: '14px',
        }}>
          <video ref={videoRef} autoPlay playsInline muted
            style={{ width: '100%', height: '100%', objectFit: 'cover',
              transform: 'scaleX(-1)', display: 'block' }}
          />

          {/* Face guide oval */}
          {(phase === 'ready' || phase === 'countdown') && (
            <div style={{
              position: 'absolute', inset: 0, pointerEvents: 'none',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <div style={{
                width: 160, height: 200,
                border: `2px dashed ${col}`, borderRadius: '50%',
                boxShadow: '0 0 0 9999px rgba(0,0,0,0.2)',
              }} />
            </div>
          )}

          {/* Countdown */}
          {phase === 'countdown' && countdown !== null && (
            <div style={{
              position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.55)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <div style={{
                fontSize: '80px', fontFamily: 'Syne', fontWeight: 800,
                color: 'white', animation: 'pulse 1s infinite',
              }}>
                {countdown}
              </div>
            </div>
          )}

          {/* Recording indicator */}
          {phase === 'capturing' && (
            <>
              <div style={{
                position: 'absolute', top: 10, left: 10,
                background: 'rgba(220,38,38,0.85)', borderRadius: '20px',
                padding: '3px 10px', fontSize: '10px', color: 'white',
                display: 'flex', alignItems: 'center', gap: '5px',
              }}>
                <span style={{ animation: 'pulse 1s infinite' }}>●</span> Recording
              </div>
              {/* Instruction overlay */}
              <div style={{
                position: 'absolute', bottom: 10, left: 0, right: 0,
                display: 'flex', justifyContent: 'center',
              }}>
                <div style={{
                  background: 'rgba(0,0,0,0.75)', borderRadius: '20px',
                  padding: '6px 16px', fontSize: '12px', fontFamily: 'Syne',
                  color: 'white', display: 'flex', alignItems: 'center', gap: '6px',
                }}>
                  <span style={{ fontSize: '16px' }}>{currentInstruction.icon}</span>
                  {currentInstruction.text}
                </div>
              </div>
            </>
          )}

          {/* Verifying spinner */}
          {phase === 'verifying' && (
            <div style={{
              position: 'absolute', inset: 0, background: 'rgba(8,12,20,0.8)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 10,
            }}>
              <div style={{
                width: 40, height: 40, border: '3px solid var(--border)',
                borderTopColor: 'var(--accent)', borderRadius: '50%',
                animation: 'spin 0.8s linear infinite',
              }} />
              <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
              <div style={{ color: 'white', fontSize: '12px', fontFamily: 'Syne' }}>
                Analysing {TOTAL_FRAMES} frames...
              </div>
            </div>
          )}

          {/* Done tick */}
          {phase === 'done' && (
            <div style={{
              position: 'absolute', inset: 0, background: 'rgba(5,46,22,0.7)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <div style={{ fontSize: '60px' }}>✓</div>
            </div>
          )}

          {/* Status chip */}
          <div style={{
            position: 'absolute', bottom: 10, left: 10,
            background: 'rgba(0,0,0,0.75)', borderRadius: '20px',
            padding: '3px 10px', fontSize: '10px', color: col,
            display: phase === 'capturing' ? 'none' : 'block',
          }}>
            {phase === 'ready'     ? '● Camera active'     : ''}
            {phase === 'done'      ? '✓ Verified'          : ''}
            {phase === 'failed'    ? '✗ Failed'            : ''}
            {phase === 'verifying' ? '● Processing'        : ''}
          </div>
        </div>

        {/* Progress bar (only during capture) */}
        {phase === 'capturing' && (
          <div style={{ marginBottom: '10px' }}>
            <div style={{ height: 6, background: 'var(--border)', borderRadius: 3 }}>
              <div style={{
                height: '100%', borderRadius: 3,
                width: `${progress}%`, background: '#ef4444',
                transition: 'width 0.15s',
              }} />
            </div>
            <div style={{ fontSize: '10px', color: 'var(--muted)', textAlign: 'right', marginTop: 3 }}>
              {Math.round(progress)}% captured
            </div>
          </div>
        )}

        {/* Liveness signals */}
        {liveSigs !== null && (
          <div style={{ marginBottom: '10px' }}>
            <div style={{ fontSize: '11px', color: 'var(--muted)', marginBottom: '4px' }}>
              Liveness signals: {liveSigs}/3
            </div>
            <div style={{ display: 'flex', gap: '6px' }}>
              {['Blink', 'Movement', 'Variation'].map((label, i) => (
                <div key={label} style={{
                  flex: 1, textAlign: 'center', padding: '4px 6px',
                  borderRadius: 6, fontSize: '10px',
                  background: i < liveSigs ? '#052e16' : 'var(--bg3)',
                  border: `1px solid ${i < liveSigs ? '#14532d' : 'var(--border)'}`,
                  color: i < liveSigs ? 'var(--safe)' : 'var(--muted)',
                }}>
                  {i < liveSigs ? '✓' : '✗'} {label}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Similarity bar */}
        {score !== null && phase !== 'ready' && (
          <div style={{ marginBottom: '12px' }}>
            <div style={{
              display: 'flex', justifyContent: 'space-between',
              fontSize: '11px', color: 'var(--muted)', marginBottom: '4px',
            }}>
              <span>Identity similarity</span>
              <span style={{ color: score >= 0.75 ? 'var(--safe)' : 'var(--high)', fontWeight: 700 }}>
                {(score * 100).toFixed(1)}%
              </span>
            </div>
            <div style={{ height: 5, background: 'var(--border)', borderRadius: 3 }}>
              <div style={{
                height: '100%', borderRadius: 3, width: `${score * 100}%`,
                background: score >= 0.75 ? 'var(--safe)' : score >= 0.5 ? 'var(--warn)' : 'var(--high)',
                transition: 'width 0.5s',
              }} />
            </div>
          </div>
        )}

        {/* Message */}
        <div style={{
          background: phase === 'done' ? '#052e16' : phase === 'failed' ? '#1a0505' : 'var(--bg3)',
          border: `1px solid ${phase === 'done' ? '#14532d' : phase === 'failed' ? '#7f1d1d' : 'var(--border)'}`,
          borderRadius: '8px', padding: '10px 14px',
          color: col, fontSize: '12px', marginBottom: '14px', textAlign: 'center',
        }}>
          {message}
          {attempts > 0 && phase === 'ready' && (
            <div style={{ color: 'var(--muted)', fontSize: '10px', marginTop: '3px' }}>
              Attempt {attempts + 1} of 3
            </div>
          )}
        </div>

        {/* Action button */}
        {phase === 'ready' && (
          <button className="btn-primary"
            style={{ width: '100%', padding: '12px', fontSize: '14px' }}
            onClick={startVerify}>
            ▶ Start Liveness Verification ({CAPTURE_SECONDS}s)
          </button>
        )}

        {phase === 'failed' && (
          <div style={{ textAlign: 'center', color: 'var(--muted)', fontSize: '12px' }}>
            Redirecting to dashboard...
          </div>
        )}
      </div>

      <canvas ref={canvasRef} style={{ display: 'none' }} />
    </div>
  );
}