// src/pages/EnrollPage.js  — FIXED VERSION
// Sends photo to backend, server extracts real FaceNet embedding

import React, { useRef, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI } from '../services/api';

const STEPS = ['Position', 'Capture', 'Confirm', 'Done'];

export default function EnrollPage() {
  const navigate   = useNavigate();
  const videoRef   = useRef(null);
  const canvasRef  = useRef(null);
  const streamRef  = useRef(null);

  const [step,      setStep]     = useState(0);
  const [captured,  setCaptured] = useState(null);   // base64 JPEG
  const [loading,   setLoading]  = useState(false);
  const [error,     setError]    = useState('');
  const [countdown, setCount]    = useState(null);
  const [tips,      setTips]     = useState([]);

  useEffect(() => { startCamera(); return () => stopCamera(); }, []);

  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width:640, height:480, facingMode:'user' }
      });
      streamRef.current = stream;
      if (videoRef.current) videoRef.current.srcObject = stream;
    } catch {
      setError('Cannot access camera. Allow camera permissions and reload.');
    }
  };

  const stopCamera = () => streamRef.current?.getTracks().forEach(t => t.stop());

  const captureWithCountdown = () => {
    let c = 3;
    setCount(c);
    const t = setInterval(() => {
      c--;
      if (c <= 0) { clearInterval(t); setCount(null); captureFrame(); }
      else setCount(c);
    }, 1000);
  };

  const captureFrame = () => {
    const canvas = canvasRef.current;
    const video  = videoRef.current;
    if (!canvas || !video) return;
    canvas.width  = video.videoWidth  || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext('2d');
    ctx.translate(canvas.width, 0);    // flip mirror
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0);
    ctx.setTransform(1,0,0,1,0,0);
    const b64 = canvas.toDataURL('image/jpeg', 0.92).split(',')[1];
    setCaptured(b64);
    setStep(2);

    // Tips for good enrollment
    setTips([
      '✓ Good lighting on your face',
      '✓ Look directly at the camera',
      '✓ No glasses if possible',
      '✓ Neutral expression',
    ]);
  };

  const handleEnroll = async () => {
    if (!captured) return;
    setLoading(true);
    setError('');
    try {
      await authAPI.enrollFace({ face_image_base64: captured });
      setStep(3);
      stopCamera();
    } catch (e) {
      const msg = e.response?.data?.detail || 'Enrollment failed. Try again.';
      setError(msg);
      setStep(2);
    } finally {
      setLoading(false);
    }
  };

  const retake = () => {
    setCaptured(null);
    setStep(0);
    setError('');
    setTips([]);
    startCamera();
  };

  const levelColors = { 0:'var(--muted)', 1:'var(--muted)', 2:'var(--accent)', 3:'var(--safe)' };

  return (
    <div style={{
      minHeight:'100vh', background:'var(--bg)',
      display:'flex', flexDirection:'column', alignItems:'center',
      justifyContent:'center', padding:'24px',
    }}>
      <div style={{ width:'100%', maxWidth:'520px' }}>

        {/* Header */}
        <div style={{ textAlign:'center', marginBottom:'24px' }}>
          <div style={{ fontSize:'32px', marginBottom:'8px' }}>👤</div>
          <h1 style={{ fontSize:'22px', marginBottom:'4px' }}>Face Enrollment</h1>
          <p style={{ color:'var(--muted)', fontSize:'12px' }}>
            Required once before your first exam
          </p>
        </div>

        {/* Steps */}
        <div style={{ display:'flex', alignItems:'center', marginBottom:'24px', padding:'0 10px' }}>
          {STEPS.map((s, i) => (
            <React.Fragment key={s}>
              <div style={{ display:'flex', flexDirection:'column', alignItems:'center', gap:'4px' }}>
                <div style={{
                  width:28, height:28, borderRadius:'50%', fontSize:'12px',
                  fontWeight:700, display:'flex', alignItems:'center', justifyContent:'center',
                  background: i < step ? 'var(--safe)' : i === step ? 'var(--accent)' : 'var(--bg3)',
                  color: i <= step ? 'white' : 'var(--muted)',
                  border: i === step ? '2px solid var(--accent)' : 'none',
                  transition:'all 0.3s',
                }}>
                  {i < step ? '✓' : i + 1}
                </div>
                <span style={{ fontSize:'10px', color: i <= step ? 'var(--text)' : 'var(--muted)' }}>
                  {s}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div style={{
                  flex:1, height:2, margin:'0 4px', marginBottom:'14px',
                  background: i < step ? 'var(--safe)' : 'var(--border)',
                  transition:'background 0.3s',
                }}/>
              )}
            </React.Fragment>
          ))}
        </div>

        <div className="card">

          {/* Steps 0, 1, 2 — Camera */}
          {step < 3 && (
            <>
              <div style={{
                position:'relative', borderRadius:'10px', overflow:'hidden',
                background:'#000', marginBottom:'16px', aspectRatio:'4/3',
              }}>
                {/* Live video */}
                <video ref={videoRef} autoPlay playsInline muted
                  style={{
                    width:'100%', height:'100%', objectFit:'cover',
                    display: captured ? 'none' : 'block',
                    transform:'scaleX(-1)',
                  }}
                />
                {/* Captured still */}
                {captured && (
                  <img src={`data:image/jpeg;base64,${captured}`}
                    alt="captured face"
                    style={{ width:'100%', height:'100%', objectFit:'cover' }}
                  />
                )}

                {/* Guide oval */}
                {!captured && (
                  <div style={{
                    position:'absolute', inset:0, pointerEvents:'none',
                    display:'flex', alignItems:'center', justifyContent:'center',
                  }}>
                    <div style={{
                      width:170, height:210,
                      border:'2px dashed rgba(59,130,246,0.7)',
                      borderRadius:'50%', boxShadow:'0 0 0 9999px rgba(0,0,0,0.25)',
                    }}/>
                  </div>
                )}

                {/* Countdown */}
                {countdown !== null && (
                  <div style={{
                    position:'absolute', inset:0,
                    display:'flex', alignItems:'center', justifyContent:'center',
                    background:'rgba(0,0,0,0.55)',
                  }}>
                    <div style={{
                      fontSize:'88px', fontFamily:'Syne', fontWeight:800,
                      color:'white', animation:'pulse 1s infinite',
                      textShadow:'0 0 40px rgba(59,130,246,0.8)',
                    }}>
                      {countdown}
                    </div>
                  </div>
                )}

                {/* Status chip */}
                <div style={{
                  position:'absolute', bottom:10, left:10,
                  background:'rgba(0,0,0,0.75)', borderRadius:'20px',
                  padding:'4px 12px', fontSize:'10px',
                  color: captured ? 'var(--safe)' : 'var(--accent)',
                }}>
                  {captured ? '✓ Photo ready for enrollment' : '● Live — position your face'}
                </div>

                {/* Processing overlay */}
                {loading && (
                  <div style={{
                    position:'absolute', inset:0,
                    display:'flex', flexDirection:'column',
                    alignItems:'center', justifyContent:'center',
                    background:'rgba(8,12,20,0.85)',
                    gap:12,
                  }}>
                    <div style={{
                      width:44, height:44, border:'3px solid var(--border)',
                      borderTopColor:'var(--accent)', borderRadius:'50%',
                      animation:'spin 0.8s linear infinite',
                    }}/>
                    <div style={{ color:'var(--text)', fontSize:'13px', fontFamily:'Syne' }}>
                      Extracting face embedding...
                    </div>
                    <div style={{ color:'var(--muted)', fontSize:'11px' }}>
                      Running AI model on server
                    </div>
                    <style>{`@keyframes spin { to { transform:rotate(360deg) } }`}</style>
                  </div>
                )}
              </div>

              {/* Tips after capture */}
              {tips.length > 0 && captured && (
                <div style={{
                  background:'var(--bg3)', borderRadius:'8px',
                  padding:'12px 16px', marginBottom:'14px',
                  display:'grid', gridTemplateColumns:'1fr 1fr', gap:'4px',
                }}>
                  {tips.map(t => (
                    <div key={t} style={{ fontSize:'11px', color:'var(--safe)' }}>{t}</div>
                  ))}
                </div>
              )}

              {/* Instructions */}
              {!captured && step === 0 && (
                <div style={{
                  background:'var(--bg3)', borderRadius:'8px',
                  padding:'12px 16px', marginBottom:'14px',
                  fontSize:'12px', color:'var(--muted)', lineHeight:1.9,
                }}>
                  <div style={{ color:'var(--text)', fontFamily:'Syne', fontSize:'13px', marginBottom:'6px', fontWeight:600 }}>
                    For best results
                  </div>
                  • Center your face inside the oval<br/>
                  • Sit in good lighting — avoid bright backgrounds<br/>
                  • Remove glasses if possible<br/>
                  • Look straight at the camera, neutral expression<br/>
                  • Blink naturally — liveness is detected automatically
                </div>
              )}

              {/* Error */}
              {error && (
                <div style={{
                  background:'#1f0a0a', border:'1px solid #7f1d1d',
                  borderRadius:'8px', padding:'10px 14px',
                  color:'#f87171', fontSize:'12px', marginBottom:'14px',
                }}>
                  ⚠ {error}
                </div>
              )}

              {/* Action buttons */}
              <div style={{ display:'flex', gap:'10px' }}>
                {!captured ? (
                  <button className="btn-primary"
                    style={{ flex:1, padding:'12px', fontSize:'14px' }}
                    onClick={captureWithCountdown}
                    disabled={countdown !== null}
                  >
                    {countdown !== null ? `📸 Capturing in ${countdown}s...` : '📸 Capture Photo'}
                  </button>
                ) : (
                  <>
                    <button className="btn-ghost" style={{ flex:1 }}
                      onClick={retake} disabled={loading}>
                      ↩ Retake
                    </button>
                    <button className="btn-primary"
                      style={{ flex:2, padding:'12px', fontSize:'14px' }}
                      onClick={handleEnroll}
                      disabled={loading}
                    >
                      {loading ? 'Processing...' : 'Enroll Face →'}
                    </button>
                  </>
                )}
              </div>
            </>
          )}

          {/* Step 3 — Success */}
          {step === 3 && (
            <div style={{ textAlign:'center', padding:'24px 0' }}>
              <div style={{
                width:80, height:80, borderRadius:'50%',
                background:'#052e16', border:'2px solid var(--safe)',
                display:'flex', alignItems:'center', justifyContent:'center',
                fontSize:'36px', margin:'0 auto 20px',
                animation:'fadeIn 0.5s ease',
              }}>
                ✓
              </div>
              <h2 style={{ fontSize:'20px', color:'var(--safe)', marginBottom:'8px' }}>
                Enrollment Successful!
              </h2>
              <p style={{ color:'var(--muted)', fontSize:'13px', lineHeight:1.7, marginBottom:'8px' }}>
                Your face has been registered in the system.<br/>
                The AI model extracted a 512-dimensional embedding.
              </p>
              <p style={{ color:'var(--muted)', fontSize:'11px', marginBottom:'28px' }}>
                You can now start any available exam.
              </p>
              <button className="btn-primary" style={{ padding:'12px 36px' }}
                onClick={() => navigate('/dashboard')}>
                Go to Dashboard →
              </button>
            </div>
          )}
        </div>

        <canvas ref={canvasRef} style={{ display:'none' }}/>

        {step < 3 && (
          <button className="btn-ghost"
            style={{ width:'100%', marginTop:'12px' }}
            onClick={() => navigate('/dashboard')}>
            ← Back to Dashboard
          </button>
        )}
      </div>
    </div>
  );
}