// src/components/FaceVerifyModal.js
// Called right before exam starts — verifies live face matches enrolled face

import React, { useRef, useState, useEffect, useCallback } from 'react';
import { authAPI } from '../services/api';

export default function FaceVerifyModal({ sessionId, onVerified, onFailed }) {
  const videoRef  = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);

  const [status,   setStatus]  = useState('waiting');  // waiting|capturing|verifying|done|failed
  const [message,  setMessage] = useState('Look at the camera and blink once');
  const [score,    setScore]   = useState(null);
  const [attempts, setAttempts]= useState(0);

  useEffect(() => {
    startCamera();
    return () => stopCamera();
  }, []);

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: 'user' },
      });
      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
      setStatus('capturing');
    } catch {
      setStatus('failed');
      setMessage('Camera access denied. Cannot verify identity.');
    }
  };

  const stopCamera = () =>
    streamRef.current?.getTracks().forEach(t => t.stop());

  const captureAndVerify = useCallback(async () => {
    const canvas = canvasRef.current;
    const video  = videoRef.current;
    if (!canvas || !video) return;

    setStatus('verifying');
    setMessage('Verifying identity...');

    // Capture frame
    canvas.width  = video.videoWidth  || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    const b64 = canvas.toDataURL('image/jpeg', 0.92).split(',')[1];

    try {
      const res = await authAPI.verifyFace({
        session_id:       sessionId,
        face_image_base64: b64,      // backend extracts embedding and compares
      });

      const data = res.data;
      setScore(data.similarity_score);

      if (data.verified) {
        setStatus('done');
        setMessage('Identity verified! Starting exam...');
        stopCamera();
        setTimeout(() => onVerified(), 1200);
      } else {
        setAttempts(a => a + 1);
        if (attempts >= 2) {
          setStatus('failed');
          setMessage(`Verification failed (score: ${(data.similarity_score * 100).toFixed(0)}%). Contact your invigilator.`);
          stopCamera();
          setTimeout(() => onFailed(), 3000);
        } else {
          setStatus('capturing');
          setMessage(`Face not matched (${(data.similarity_score * 100).toFixed(0)}% similarity). Try again — ensure good lighting.`);
        }
      }
    } catch (e) {
      setAttempts(a => a + 1);
      setStatus('capturing');
      setMessage(e.response?.data?.detail || 'Verification error. Try again.');
    }
  }, [sessionId, attempts, onVerified, onFailed]);

  const statusConfig = {
    waiting:    { color: 'var(--muted)',   icon: '👤' },
    capturing:  { color: 'var(--accent)',  icon: '📷' },
    verifying:  { color: 'var(--warn)',    icon: '🔍' },
    done:       { color: 'var(--safe)',    icon: '✓'  },
    failed:     { color: 'var(--high)',    icon: '✗'  },
  };
  const cfg = statusConfig[status] || statusConfig.waiting;

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 200,
      background: 'rgba(8,12,20,0.92)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '24px',
    }}>
      <div className="card animate-in" style={{ width: '100%', maxWidth: '460px' }}>

        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '20px' }}>
          <div style={{ fontSize: '28px', marginBottom: '8px' }}>{cfg.icon}</div>
          <h2 style={{ fontSize: '18px', marginBottom: '4px' }}>Identity Verification</h2>
          <p style={{ color: 'var(--muted)', fontSize: '12px' }}>
            Step 1 of 1 — required before exam begins
          </p>
        </div>

        {/* Camera view */}
        <div style={{
          position: 'relative', borderRadius: '10px', overflow: 'hidden',
          background: '#000', aspectRatio: '4/3', marginBottom: '16px',
        }}>
          <video ref={videoRef} autoPlay playsInline muted
            style={{
              width: '100%', height: '100%', objectFit: 'cover',
              transform: 'scaleX(-1)', display: 'block',
            }}
          />
          {/* Animated border when verifying */}
          <div style={{
            position: 'absolute', inset: 0,
            border: `3px solid ${cfg.color}`,
            borderRadius: '10px', pointerEvents: 'none',
            opacity: status === 'verifying' ? 1 : 0,
            animation: status === 'verifying' ? 'pulse 1s infinite' : 'none',
            transition: 'opacity 0.3s',
          }} />
          {/* Face guide */}
          {(status === 'capturing' || status === 'waiting') && (
            <div style={{
              position: 'absolute', inset: 0, pointerEvents: 'none',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <div style={{
                width: 160, height: 200,
                border: `2px dashed ${cfg.color}`,
                borderRadius: '50%',
                boxShadow: '0 0 0 9999px rgba(0,0,0,0.2)',
              }} />
            </div>
          )}
          {/* Loading spinner */}
          {status === 'verifying' && (
            <div style={{
              position: 'absolute', inset: 0, background: 'rgba(8,12,20,0.7)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexDirection: 'column', gap: 10,
            }}>
              <div style={{
                width: 40, height: 40, border: '3px solid var(--border)',
                borderTopColor: 'var(--accent)', borderRadius: '50%',
                animation: 'spin 0.8s linear infinite',
              }} />
              <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
            </div>
          )}
          {/* Done overlay */}
          {status === 'done' && (
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
            padding: '4px 12px', fontSize: '10px', color: cfg.color,
          }}>
            {status === 'verifying' ? '● Verifying...' :
             status === 'done'      ? '✓ Verified'     :
             status === 'failed'    ? '✗ Failed'       :
             '● Camera active'}
          </div>
        </div>

        {/* Similarity score bar */}
        {score !== null && (
          <div style={{ marginBottom: '12px' }}>
            <div style={{
              display: 'flex', justifyContent: 'space-between',
              fontSize: '11px', color: 'var(--muted)', marginBottom: '4px',
            }}>
              <span>Similarity score</span>
              <span style={{ color: score >= 0.75 ? 'var(--safe)' : 'var(--high)', fontWeight: 700 }}>
                {(score * 100).toFixed(1)}%
              </span>
            </div>
            <div style={{ height: 6, background: 'var(--border)', borderRadius: 3 }}>
              <div style={{
                height: '100%', borderRadius: 3,
                width: `${score * 100}%`,
                background: score >= 0.75 ? 'var(--safe)' : score >= 0.5 ? 'var(--warn)' : 'var(--high)',
                transition: 'width 0.5s',
              }} />
            </div>
            <div style={{ fontSize: '10px', color: 'var(--muted)', marginTop: 3 }}>
              Required: 75% minimum
            </div>
          </div>
        )}

        {/* Message */}
        <div style={{
          background: status === 'done' ? '#052e16' : status === 'failed' ? '#1a0505' : 'var(--bg3)',
          border: `1px solid ${status === 'done' ? '#14532d' : status === 'failed' ? '#7f1d1d' : 'var(--border)'}`,
          borderRadius: '8px', padding: '10px 14px',
          color: cfg.color, fontSize: '12px', marginBottom: '16px',
          textAlign: 'center',
        }}>
          {message}
          {attempts > 0 && status !== 'failed' && (
            <div style={{ color: 'var(--muted)', fontSize: '11px', marginTop: '4px' }}>
              Attempt {attempts + 1} of 3
            </div>
          )}
        </div>

        {/* Verify button */}
        {(status === 'capturing') && (
          <button className="btn-primary"
            style={{ width: '100%', padding: '12px', fontSize: '14px' }}
            onClick={captureAndVerify}>
            Verify My Identity →
          </button>
        )}

        {status === 'failed' && (
          <div style={{ textAlign: 'center', color: 'var(--muted)', fontSize: '12px' }}>
            Redirecting... Contact your invigilator if this is an error.
          </div>
        )}
      </div>

      <canvas ref={canvasRef} style={{ display: 'none' }} />
    </div>
  );
}