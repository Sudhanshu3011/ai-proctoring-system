// // src/pages/EnrollPage.js — light theme + multi-frame liveness
// // Captures 3 seconds of video (25 frames at ~8 FPS)
// // Shows real-time liveness feedback to user
// // Camera logic from working version + light theme UI

// import React, { useRef, useState, useEffect, useCallback } from 'react';
// import { useNavigate } from 'react-router-dom';
// import { authAPI } from '../services/api';

// const STEPS            = ['Position', 'Liveness', 'Processing', 'Complete'];
// const CAPTURE_FPS      = 8;
// const CAPTURE_SECONDS  = 3;
// const TOTAL_FRAMES     = CAPTURE_FPS * CAPTURE_SECONDS;   // 24
// const FRAME_INTERVAL_MS= 1000 / CAPTURE_FPS;              // 125ms

// const INSTRUCTIONS = [
//   { text: 'Look straight at the camera', time: 0    },
//   { text: 'Blink naturally once',         time: 800  },
//   { text: 'Slowly turn your head',        time: 1600 },
//   { text: 'Return to centre',             time: 2400 },
// ];

// export default function EnrollPage() {
//   const navigate = useNavigate();

//   // ── Refs (never cause re-render) ────────────────────────────────
//   const videoRef   = useRef(null);
//   const canvasRef  = useRef(null);
//   const streamRef  = useRef(null);
//   const captureRef = useRef(null);   // interval handle

//   // ── State ───────────────────────────────────────────────────────
//   const [step,      setStep]    = useState(0);
//   const [progress,  setProgress]= useState(0);
//   const [instrIdx,  setInstrIdx]= useState(0);
//   const [countdown, setCount]   = useState(null);
//   const [loading,   setLoading] = useState(false);
//   const [error,     setError]   = useState('');
//   const [liveness,  setLiveness]= useState(null);

//   // ── Camera lifecycle ────────────────────────────────────────────
//   useEffect(() => {
//     startCamera();
//     return stopCapture;          // cleanup on unmount
//   }, []);

//   // ── WORKING camera start (from document 2) ─────────────────────
//   const startCamera = async () => {
//     console.log('[Enroll] Starting camera...');
//     try {
//       // Stop any existing stream first
//       if (streamRef.current) {
//         streamRef.current.getTracks().forEach(t => t.stop());
//         streamRef.current = null;
//       }

//       const stream = await navigator.mediaDevices.getUserMedia({
//         video: { width: 640, height: 480, facingMode: 'user' },
//         audio: false,
//       });

//       console.log('[Enroll] Stream received');
//       streamRef.current = stream;

//       if (videoRef.current) {
//         videoRef.current.srcObject = stream;

//         // ← KEY from doc 2: wait for metadata THEN play
//         videoRef.current.onloadedmetadata = () => {
//           console.log('[Enroll] Metadata loaded');
//           videoRef.current.play()
//             .then(() => console.log('[Enroll] Video playing'))
//             .catch(e  => console.error('[Enroll] play() error:', e));
//         };

//         videoRef.current.oncanplay = () => {
//           console.log('[Enroll] canplay fired —', videoRef.current.videoWidth, 'x', videoRef.current.videoHeight);
//         };
//       }
//     } catch (err) {
//       console.error('[Enroll] Camera error:', err.name, err.message);
//       const msg =
//         err.name === 'NotAllowedError'  ? 'Camera permission denied. Allow access in browser settings.' :
//         err.name === 'NotFoundError'    ? 'No camera found. Connect a webcam and retry.' :
//         err.name === 'NotReadableError' ? 'Camera is in use by another application.' :
//         `Camera error: ${err.message}`;
//       setError(msg);
//     }
//   };

//   const stopCapture = () => {
//     if (captureRef.current) { clearInterval(captureRef.current); captureRef.current = null; }
//     streamRef.current?.getTracks().forEach(t => t.stop());
//   };

//   // ── WORKING readiness check (from document 2) ──────────────────
//   const isVideoReady = () => {
//     const v = videoRef.current;
//     return v && v.videoWidth > 0 && v.videoHeight > 0;
//   };

//   // ── Countdown (from document 2 — polls until video is ready) ───
//   const startCaptureWithCountdown = () => {
//     console.log('[Enroll] Start clicked');
//     setError('');

//     if (isVideoReady()) {
//       console.log('[Enroll] Video ready immediately');
//       doStartCountdown();
//     } else {
//       console.log('[Enroll] Video not ready yet — polling...');
//       const check = setInterval(() => {
//         if (isVideoReady()) {
//           console.log('[Enroll] Video dimensions ready → countdown');
//           clearInterval(check);
//           doStartCountdown();
//         }
//       }, 100);
//     }
//   };

//   const doStartCountdown = () => {
//     let c = 3;
//     setCount(c);
//     const timer = setInterval(() => {
//       c--;
//       if (c <= 0) { clearInterval(timer); setCount(null); beginCapture(); }
//       else setCount(c);
//     }, 1000);
//   };

//   // ── WORKING capture (from document 2 — ctx.setTransform reset) ─
//   const beginCapture = useCallback(() => {
//     console.log('[Enroll] Capture started');
//     const collected = [];
//     let frameCount  = 0;
//     const startTime = Date.now();

//     setStep(1);
//     setProgress(0);
//     setInstrIdx(0);

//     captureRef.current = setInterval(() => {
//       const canvas = canvasRef.current;
//       const video  = videoRef.current;

//       if (!canvas || !video) { console.error('[Enroll] Missing ref'); return; }
//       if (!video.videoWidth || !video.videoHeight) { console.warn('[Enroll] No video dims yet'); return; }

//       canvas.width  = 320;
//       canvas.height = 240;
//       const ctx = canvas.getContext('2d');

//       // ← KEY from doc 2: full transform reset before and after
//       ctx.setTransform(1, 0, 0, 1, 0, 0);
//       ctx.translate(canvas.width, 0);
//       ctx.scale(-1, 1);
//       ctx.drawImage(video, 0, 0, 320, 240);
//       ctx.setTransform(1, 0, 0, 1, 0, 0);   // reset after draw

//       const b64 = canvas.toDataURL('image/jpeg', 0.8).split(',')[1];
//       if (!b64) { console.error('[Enroll] base64 empty'); return; }

//       collected.push(b64);
//       frameCount++;

//       const pct = Math.min(100, (frameCount / TOTAL_FRAMES) * 100);
//       setProgress(pct);

//       // Update instruction based on elapsed time
//       const elapsed  = Date.now() - startTime;
//       const instrIdx = INSTRUCTIONS.findIndex(
//         (ins, i) => elapsed >= ins.time && (i === INSTRUCTIONS.length - 1 || elapsed < INSTRUCTIONS[i + 1].time)
//       );
//       if (instrIdx >= 0) setInstrIdx(instrIdx);

//       if (frameCount <= 3 || frameCount % 6 === 0 || frameCount === TOTAL_FRAMES) {
//         console.log(`[Enroll] Frame ${frameCount}/${TOTAL_FRAMES} — size:${b64.length}chars`);
//       }

//       if (frameCount >= TOTAL_FRAMES) {
//         console.log('[Enroll] Capture complete —', collected.length, 'frames');
//         clearInterval(captureRef.current);
//         setStep(2);
//         submitFrames(collected);
//       }
//     }, FRAME_INTERVAL_MS);
//   }, []);

//   // ── Submit to backend ───────────────────────────────────────────
//   const submitFrames = async (frameList) => {
//     console.log('[Enroll] Submitting', frameList.length, 'frames');
//     setLoading(true); setError('');
//     try {
//       const res = await authAPI.enrollFace({ frame_sequence: frameList, fps: CAPTURE_FPS });
//       console.log('[Enroll] Response:', res.data);
//       setLiveness({ signals: res.data.liveness_signals, message: res.data.message });
//       setStep(3);
//       stopCapture();
//     } catch (e) {
//       console.error('[Enroll] API error:', e.response?.data || e.message);
//       setError(e.response?.data?.detail || 'Enrollment failed. Please try again.');
//       setStep(0); setProgress(0);
//       startCamera();
//     } finally { setLoading(false); }
//   };

//   const instr = INSTRUCTIONS[instrIdx] || INSTRUCTIONS[0];

//   // ── Render ──────────────────────────────────────────────────────
//   return (
//     <div style={{
//       minHeight:'100vh', background:'var(--bg)',
//       display:'flex', flexDirection:'column',
//       alignItems:'center', justifyContent:'center', padding:'24px',
//     }}>
//       <div style={{ width:'100%', maxWidth:'480px' }}>

//         {/* Header */}
//         <div style={{ textAlign:'center', marginBottom:'22px' }}>
//           <h1 style={{ fontSize:'20px', marginBottom:'4px' }}>Face Enrollment</h1>
//           <p style={{ color:'var(--muted)', fontSize:'12px' }}>
//             Required once before your first exam. Takes approximately 10 seconds.
//           </p>
//         </div>

//         {/* Step progress */}
//         <div style={{ display:'flex', alignItems:'center', marginBottom:'20px' }}>
//           {STEPS.map((s, i) => (
//             <React.Fragment key={s}>
//               <div style={{ display:'flex', flexDirection:'column', alignItems:'center', gap:'5px' }}>
//                 <div style={{
//                   width:26, height:26, borderRadius:'50%', fontSize:'11px',
//                   fontWeight:700, display:'flex', alignItems:'center', justifyContent:'center',
//                   background: i < step ? 'var(--safe)' : i === step ? 'var(--accent)' : 'var(--bg3)',
//                   color: i <= step ? '#fff' : 'var(--muted)',
//                   border: i === step ? '2px solid var(--accent)' : '2px solid transparent',
//                   transition:'all 0.3s',
//                 }}>
//                   {i < step ? '✓' : i + 1}
//                 </div>
//                 <span style={{ fontSize:'10px', fontWeight:500, color: i <= step ? 'var(--text)' : 'var(--muted)' }}>
//                   {s}
//                 </span>
//               </div>
//               {i < STEPS.length - 1 && (
//                 <div style={{
//                   flex:1, height:2, margin:'0 4px', marginBottom:'16px',
//                   background: i < step ? 'var(--safe)' : 'var(--border)',
//                   transition:'background 0.3s',
//                 }}/>
//               )}
//             </React.Fragment>
//           ))}
//         </div>

//         <div className="card">

//           {/* ── SINGLE PERSISTENT VIDEO (doc 2 pattern) ── */}
//           {/* Visible on steps 0, 1, 2 — hidden only on step 3 */}
//           {step < 3 && (
//             <div style={{
//               position:'relative', borderRadius:'8px', overflow:'hidden',
//               background:'#000', aspectRatio:'4/3', marginBottom:'16px',
//             }}>
//               {/* Video always mounted — never unmounted between steps */}
//               <video
//                 ref={videoRef}
//                 autoPlay
//                 playsInline
//                 muted
//                 style={{
//                   width:'100%', height:'100%',
//                   objectFit:'cover',
//                   transform:'scaleX(-1)',
//                   display:'block',
//                 }}
//               />

//               {/* Face guide oval — step 0 only */}
//               {step === 0 && (
//                 <div style={{
//                   position:'absolute', inset:0, pointerEvents:'none',
//                   display:'flex', alignItems:'center', justifyContent:'center',
//                 }}>
//                   <div style={{
//                     width:160, height:200,
//                     border:'2px dashed rgba(37,99,235,0.6)',
//                     borderRadius:'50%',
//                     boxShadow:'0 0 0 9999px rgba(0,0,0,0.2)',
//                   }}/>
//                 </div>
//               )}

//               {/* Countdown overlay */}
//               {countdown !== null && (
//                 <div style={{
//                   position:'absolute', inset:0,
//                   background:'rgba(0,0,0,0.55)',
//                   display:'flex', alignItems:'center', justifyContent:'center',
//                 }}>
//                   <span style={{
//                     fontSize:'80px', fontWeight:800, color:'#fff',
//                   }}>
//                     {countdown}
//                   </span>
//                 </div>
//               )}

//               {/* Recording badge + instruction — step 1 */}
//               {step === 1 && (
//                 <>
//                   <div style={{
//                     position:'absolute', top:10, left:10,
//                     background:'rgba(220,38,38,0.85)', borderRadius:'20px',
//                     padding:'3px 12px', fontSize:'10px', color:'#fff',
//                     display:'flex', alignItems:'center', gap:'5px',
//                   }}>
//                     <span style={{ animation:'pulse 1s infinite' }}>●</span>
//                     Recording
//                   </div>
//                   <div style={{
//                     position:'absolute', bottom:10, left:0, right:0,
//                     display:'flex', justifyContent:'center',
//                   }}>
//                     <div style={{
//                       background:'rgba(0,0,0,0.72)', borderRadius:'20px',
//                       padding:'7px 18px', fontSize:'12px', color:'#fff', fontWeight:500,
//                     }}>
//                       {instr.text}
//                     </div>
//                   </div>
//                 </>
//               )}

//               {/* Processing overlay — step 2 */}
//               {step === 2 && (
//                 <div style={{
//                   position:'absolute', inset:0,
//                   background:'rgba(15,23,42,0.72)',
//                   display:'flex', flexDirection:'column',
//                   alignItems:'center', justifyContent:'center', gap:12,
//                 }}>
//                   <div style={{
//                     width:40, height:40,
//                     border:'3px solid rgba(255,255,255,0.3)',
//                     borderTopColor:'#fff', borderRadius:'50%',
//                     animation:'spin 0.8s linear infinite',
//                   }}/>
//                   <div style={{ color:'#fff', fontSize:'12px', fontWeight:500 }}>
//                     Analysing liveness...
//                   </div>
//                 </div>
//               )}
//             </div>
//           )}

//           {/* ── Step 0: Instructions + start button ── */}
//           {step === 0 && (
//             <>
//               <div style={{
//                 background:'var(--bg3)', border:'1px solid var(--border)',
//                 borderRadius:'8px', padding:'12px 16px',
//                 marginBottom:'14px', fontSize:'12px',
//                 color:'var(--text2)', lineHeight:2,
//               }}>
//                 <div style={{
//                   fontWeight:600, color:'var(--text)',
//                   fontSize:'13px', marginBottom:'6px',
//                 }}>
//                   During the 3-second capture:
//                 </div>
//                 {INSTRUCTIONS.map((ins, i) => (
//                   <div key={i} style={{ display:'flex', gap:'10px', color:'var(--muted)' }}>
//                     <span style={{ fontWeight:600, color:'var(--accent)', minWidth:16 }}>
//                       {i + 1}.
//                     </span>
//                     <span>{ins.text}</span>
//                   </div>
//                 ))}
//               </div>

//               {error && (
//                 <div style={{
//                   background:'var(--high-lt)', border:'1px solid var(--high-bd)',
//                   borderRadius:'8px', padding:'10px 14px',
//                   color:'var(--high)', fontSize:'12px',
//                   marginBottom:'14px', lineHeight:1.6,
//                 }}>
//                   {error}
//                   <div
//                     onClick={startCamera}
//                     style={{
//                       color:'var(--accent)', cursor:'pointer',
//                       marginTop:'5px', fontWeight:600, fontSize:'11px',
//                     }}>
//                     Try opening camera again
//                   </div>
//                 </div>
//               )}

//               <button
//                 className="btn-primary"
//                 style={{ width:'100%', padding:'11px', justifyContent:'center' }}
//                 onClick={startCaptureWithCountdown}
//                 disabled={countdown !== null}
//               >
//                 {countdown !== null
//                   ? `Starting in ${countdown}...`
//                   : 'Begin Liveness Capture'}
//               </button>
//             </>
//           )}

//           {/* ── Step 1: Progress bar ── */}
//           {step === 1 && (
//             <div>
//               <div style={{
//                 display:'flex', justifyContent:'space-between',
//                 fontSize:'11px', color:'var(--muted)', marginBottom:'5px',
//               }}>
//                 <span>Capturing frames...</span>
//                 <span>{Math.round(progress)}%</span>
//               </div>
//               <div style={{ height:5, background:'var(--bg3)', borderRadius:3 }}>
//                 <div style={{
//                   height:'100%', width:`${progress}%`,
//                   background:'var(--accent)', borderRadius:3,
//                   transition:`width ${FRAME_INTERVAL_MS}ms linear`,
//                 }}/>
//               </div>
//               <div style={{
//                 fontSize:'10px', color:'var(--muted)',
//                 marginTop:'4px', textAlign:'right',
//               }}>
//                 {Math.round(progress / 100 * TOTAL_FRAMES)} / {TOTAL_FRAMES} frames
//               </div>
//             </div>
//           )}

//           {/* ── Step 2: Processing text (video overlay handles spinner) ── */}
//           {step === 2 && (
//             <div style={{ textAlign:'center', color:'var(--muted)', fontSize:'12px', padding:'4px 0' }}>
//               Running liveness signals on {TOTAL_FRAMES} frames...
//             </div>
//           )}

//           {/* ── Step 3: Success ── */}
//           {step === 3 && (
//             <div style={{ textAlign:'center', padding:'20px 0' }}>
//               <div style={{
//                 width:72, height:72, borderRadius:'50%',
//                 background:'var(--safe-lt)', border:'2px solid var(--safe-bd)',
//                 display:'flex', alignItems:'center', justifyContent:'center',
//                 fontSize:'28px', margin:'0 auto 16px', color:'var(--safe)',
//               }}>
//                 ✓
//               </div>
//               <h2 style={{ fontSize:'18px', color:'var(--safe)', marginBottom:'6px' }}>
//                 Enrollment Complete
//               </h2>
//               {liveness && (
//                 <div style={{
//                   display:'inline-block',
//                   background:'var(--safe-lt)', border:'1px solid var(--safe-bd)',
//                   borderRadius:'20px', padding:'4px 16px',
//                   marginBottom:'12px', fontSize:'11px',
//                   color:'var(--safe)', fontWeight:600,
//                 }}>
//                   Liveness: {liveness.signals}/3 signals passed
//                 </div>
//               )}
//               <p style={{
//                 color:'var(--muted)', fontSize:'12px',
//                 marginBottom:'24px', lineHeight:1.7,
//               }}>
//                 Your face has been registered.<br/>
//                 You can now start any available exam.
//               </p>
//               <button
//                 className="btn-primary"
//                 style={{ padding:'10px 28px', justifyContent:'center' }}
//                 onClick={() => navigate('/dashboard')}
//               >
//                 Go to Dashboard
//               </button>
//             </div>
//           )}
//         </div>

//         {/* Hidden canvas */}
//         <canvas ref={canvasRef} style={{ display:'none' }}/>

//         {/* Back button */}
//         {(step === 0 || step === 3) && (
//           <button
//             className="btn-ghost"
//             style={{ width:'100%', marginTop:'10px', justifyContent:'center' }}
//             onClick={() => navigate('/dashboard')}
//           >
//             Back to Dashboard
//           </button>
//         )}
//       </div>
//     </div>
//   );
// }


// src/pages/EnrollPage.js — FINAL with multi-face error handling
import React, { useRef, useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI } from '../services/api';
import { colors, fonts, radius, shadow } from '../styles/theme';
import { btn } from '../styles/styles';

const STEPS = ['Position', 'Capture', 'Processing', 'Complete'];
const CAPTURE_FPS = 8;
const CAPTURE_SECONDS = 3;
const TOTAL_FRAMES = CAPTURE_FPS * CAPTURE_SECONDS;   // 24
const FRAME_INTERVAL_MS = 1000 / CAPTURE_FPS;

const INSTRUCTIONS = [
  { text: 'Look straight at the camera', time: 0 },
  { text: 'Blink naturally once', time: 800 },
  { text: 'Slowly turn your head slightly', time: 1600 },
  { text: 'Return to centre', time: 2400 },
];

const S = {
  page: {
    minHeight: '100vh', background: colors.gray50,
    display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center',
    fontFamily: fonts.ui, padding: '24px',
  },
  wrap: { width: '100%', maxWidth: '480px' },
  title: {
    fontFamily: fonts.display, fontSize: '22px', fontWeight: 400,
    color: colors.gray900, letterSpacing: '-0.03em', textAlign: 'center', marginBottom: '4px',
  },
  sub: { fontSize: '13px', color: colors.gray500, textAlign: 'center', marginBottom: '24px' },
  card: {
    background: colors.white, border: `1px solid ${colors.gray200}`,
    borderRadius: radius.xl, padding: '20px', boxShadow: shadow.sm,
  },
  stepRow: { display: 'flex', alignItems: 'center', marginBottom: '22px' },
  stepDot: (i, cur) => ({
    width: 26, height: 26, borderRadius: '50%', fontSize: '11px', fontWeight: 700,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    background: i < cur ? colors.successMid : i === cur ? colors.accent : colors.gray200,
    color: i <= cur ? '#fff' : colors.gray400, transition: 'all 0.3s', flexShrink: 0,
  }),
  stepLabel: (i, cur) => ({
    fontSize: '10px', fontWeight: 500, marginTop: '4px', textAlign: 'center',
    color: i <= cur ? colors.gray700 : colors.gray400,
  }),
  stepLine: (i, cur) => ({
    flex: 1, height: 2, margin: '0 4px', marginBottom: '16px',
    background: i < cur ? colors.successMid : colors.gray200, transition: 'background 0.3s',
  }),
  camWrap: {
    position: 'relative', borderRadius: radius.lg, overflow: 'hidden',
    background: '#000', aspectRatio: '4/3', marginBottom: '14px',
  },
  countdownOverlay: {
    position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.55)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  recBadge: {
    position: 'absolute', top: 8, left: 8,
    background: 'rgba(220,38,38,0.85)', borderRadius: '99px',
    padding: '3px 10px', fontSize: '10px', color: '#fff',
    display: 'flex', alignItems: 'center', gap: '5px',
  },
  instrPill: {
    position: 'absolute', bottom: 10, left: 0, right: 0,
    display: 'flex', justifyContent: 'center',
  },
  instrText: {
    background: 'rgba(0,0,0,0.72)', borderRadius: '99px',
    padding: '6px 16px', fontSize: '12px', color: '#fff',
  },
  processingOverlay: {
    position: 'absolute', inset: 0, background: 'rgba(15,23,42,0.72)',
    display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center', gap: 12,
  },
  instrBox: {
    background: colors.gray50, border: `1px solid ${colors.gray200}`,
    borderRadius: radius.md, padding: '12px 16px', marginBottom: '14px',
    fontSize: '12px', lineHeight: 2, color: colors.gray700,
  },
  instrTitle: { fontWeight: 600, color: colors.gray900, fontSize: '13px', marginBottom: '6px' },
  instrItem: { display: 'flex', gap: '10px' },
  instrNum: { fontWeight: 600, color: colors.accent, minWidth: 16 },
  errorBox: {
    background: colors.dangerLight, border: `1px solid ${colors.dangerBorder}`,
    borderRadius: radius.md, padding: '12px 14px',
    color: colors.dangerMid, fontSize: '12px', marginBottom: '14px', lineHeight: 1.6,
  },
  multiFaceBox: {
    background: '#fff3cd', border: '1px solid #ffc107',
    borderLeft: `3px solid #d97706`,
    borderRadius: radius.md, padding: '12px 14px',
    color: '#92400e', fontSize: '12px', marginBottom: '14px', lineHeight: 1.6,
    fontWeight: 600,
  },
  progressLabel: {
    display: 'flex', justifyContent: 'space-between',
    fontSize: '11px', color: colors.gray500, marginBottom: '5px',
  },
  progressTrack: { height: 5, background: colors.gray200, borderRadius: '99px' },
  progressFill: (pct) => ({
    height: '100%', width: `${pct}%`, background: colors.accent,
    borderRadius: '99px', transition: `width 200ms linear`,
  }),
  successIcon: {
    width: 72, height: 72, borderRadius: '50%',
    background: colors.successLight, border: `2px solid ${colors.successBorder}`,
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    fontSize: '28px', margin: '0 auto 16px', color: colors.successMid,
  },
  livenessTag: {
    display: 'inline-block',
    background: colors.successLight, border: `1px solid ${colors.successBorder}`,
    borderRadius: '99px', padding: '4px 16px',
    marginBottom: '12px', fontSize: '11px', color: colors.successMid, fontWeight: 600,
  },
};

export default function EnrollPage() {
  const navigate = useNavigate();
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const intervalRef = useRef(null);
  const framesRef = useRef([]);

  const [step, setStep] = useState(0);
  const [progress, setProgress] = useState(0);
  const [instrIdx, setInstrIdx] = useState(0);
  const [countdown, setCount] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [isMultiFace, setMultiFace] = useState(false);
  const [liveness, setLiveness] = useState(null);
  const [camReady, setCamReady] = useState(false);

  useEffect(() => { startCamera(); return cleanup; }, []);

  const startCamera = async () => {
    setCamReady(false); setError(''); setMultiFace(false);
    try {
      if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' }, audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.onloadedmetadata = () => {
          videoRef.current.play()
            .then(() => { console.log('[Enroll] Camera ready'); setCamReady(true); })
            .catch(e => { console.error('[Enroll] play() error:', e); setError('Camera failed to start.'); });
        };
      }
    } catch (err) {
      const msg =
        err.name === 'NotAllowedError' ? 'Camera permission denied. Allow access in browser settings.' :
          err.name === 'NotFoundError' ? 'No camera found. Connect a webcam.' :
            err.name === 'NotReadableError' ? 'Camera is in use by another application.' :
              `Camera error: ${err.message}`;
      setError(msg);
    }
  };

  const cleanup = () => {
    if (intervalRef.current) clearInterval(intervalRef.current);
    streamRef.current?.getTracks().forEach(t => t.stop());
  };

  const isVideoReady = () => {
    const v = videoRef.current;
    return v && v.videoWidth > 0 && v.videoHeight > 0;
  };

  const startCountdown = () => {
    setError(''); setMultiFace(false);
    if (!isVideoReady()) {
      const check = setInterval(() => {
        if (isVideoReady()) { clearInterval(check); doStartCountdown(); }
      }, 100);
    } else {
      doStartCountdown();
    }
  };

  const doStartCountdown = () => {
    let c = 3; setCount(c);
    const t = setInterval(() => {
      c--;
      if (c <= 0) { clearInterval(t); setCount(null); beginCapture(); }
      else setCount(c);
    }, 1000);
  };

  const beginCapture = () => {
    console.log('[Enroll] Capture started');
    framesRef.current = [];
    let n = 0;
    const startTime = Date.now();

    setStep(1); setProgress(0); setInstrIdx(0);

    intervalRef.current = setInterval(() => {
      const v = videoRef.current, c = canvasRef.current;
      if (!v || !c || !v.videoWidth || !v.videoHeight) return;

      c.width = 320; c.height = 240;
      const ctx = c.getContext('2d');
      ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.translate(c.width, 0); ctx.scale(-1, 1);
      ctx.drawImage(v, 0, 0, 320, 240); ctx.setTransform(1, 0, 0, 1, 0, 0);

      const b64 = c.toDataURL('image/jpeg', 0.8).split(',')[1];
      if (!b64 || b64.length < 100) return;

      framesRef.current.push(b64); n++;

      const pct = Math.min(100, (n / TOTAL_FRAMES) * 100);
      setProgress(pct);

      const elapsed = Date.now() - startTime;
      const instrI = INSTRUCTIONS.findIndex(
        (ins, i) => elapsed >= ins.time && (i === INSTRUCTIONS.length - 1 || elapsed < INSTRUCTIONS[i + 1].time)
      );
      if (instrI >= 0) setInstrIdx(instrI);

      if (n >= TOTAL_FRAMES) {
        clearInterval(intervalRef.current);
        setStep(2);
        submitFrames(framesRef.current);
      }
    }, FRAME_INTERVAL_MS);
  };

  const submitFrames = async (frameList) => {
    console.log('[Enroll] Submitting', frameList.length, 'frames');
    setLoading(true); setError(''); setMultiFace(false);
    try {
      const res = await authAPI.enrollFace({ frame_sequence: frameList, fps: CAPTURE_FPS });
      console.log('[Enroll] Response:', res.data);
      setLiveness({ signals: res.data.liveness_signals, message: res.data.message });
      setStep(3);
      streamRef.current?.getTracks().forEach(t => t.stop());
    } catch (e) {
      console.error('[Enroll] API error:', e.response?.data || e.message);
      const detail = e.response?.data?.detail || e.message || 'Enrollment failed.';

      // Detect multi-face error from backend — show specific warning
      const isMulti = detail.toLowerCase().includes('multiple people') ||
        detail.toLowerCase().includes('multiple faces') ||
        detail.toLowerCase().includes('more than one');

      if (isMulti) {
        setMultiFace(true);
        setError('');
      } else {
        setError(detail);
        setMultiFace(false);
      }

      setStep(0); setProgress(0);
      framesRef.current = [];
      startCamera();
    } finally {
      setLoading(false);
    }
  };

  const instr = INSTRUCTIONS[instrIdx] || INSTRUCTIONS[0];

  return (
    <div style={S.page}>
      <div style={S.wrap}>
        <h1 style={S.title}>Face Enrollment</h1>
        <p style={S.sub}>Required once before your first exam. Takes 10 seconds.</p>

        {/* Step indicators */}
        <div style={S.stepRow}>
          {STEPS.map((label, i) => (
            <React.Fragment key={label}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4 }}>
                <div style={S.stepDot(i, step)}>{i < step ? '✓' : i + 1}</div>
                <span style={S.stepLabel(i, step)}>{label}</span>
              </div>
              {i < STEPS.length - 1 && <div style={S.stepLine(i, step)} />}
            </React.Fragment>
          ))}
        </div>

        <div style={S.card}>
          {/* Camera — always mounted on steps 0-2 */}
          {step < 3 && (
            <div style={S.camWrap}>
              <video ref={videoRef} autoPlay playsInline muted
                style={{
                  width: '100%', height: '100%', objectFit: 'cover',
                  transform: 'scaleX(-1)', display: 'block'
                }} />

              {/* Camera loading */}
              {!camReady && step === 0 && (
                <div style={S.processingOverlay}>
                  <div style={{
                    width: 28, height: 28,
                    border: '3px solid rgba(255,255,255,0.3)', borderTopColor: '#fff',
                    borderRadius: '50%', animation: 'spin 0.8s linear infinite'
                  }} />
                </div>
              )}

              {/* Face guide oval — step 0 */}
              {step === 0 && camReady && (
                <div style={{
                  position: 'absolute', inset: 0, pointerEvents: 'none',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}>
                  <div style={{
                    width: 160, height: 200,
                    border: `2px dashed ${isMultiFace ? '#d97706' : 'rgba(37,99,235,0.6)'}`,
                    borderRadius: '50%',
                    boxShadow: '0 0 0 9999px rgba(0,0,0,0.2)',
                  }} />
                </div>
              )}

              {/* Countdown */}
              {countdown !== null && (
                <div style={S.countdownOverlay}>
                  <span style={{
                    fontSize: '72px', fontWeight: 800, color: '#fff',
                    fontFamily: fonts.mono
                  }}>{countdown}</span>
                </div>
              )}

              {/* Recording overlay */}
              {step === 1 && (
                <>
                  <div style={S.recBadge}><span>●</span> Recording</div>
                  <div style={S.instrPill}>
                    <div style={S.instrText}>{instr.text}</div>
                  </div>
                </>
              )}

              {/* Processing overlay */}
              {step === 2 && (
                <div style={S.processingOverlay}>
                  <div style={{
                    width: 36, height: 36,
                    border: '3px solid rgba(255,255,255,0.3)', borderTopColor: '#fff',
                    borderRadius: '50%', animation: 'spin 0.8s linear infinite'
                  }} />
                  <div style={{ color: '#fff', fontSize: '12px' }}>Analysing liveness…</div>
                </div>
              )}
            </div>
          )}

          {/* Step 0 — instructions */}
          {step === 0 && (
            <>
              {/* Multi-face warning — prominent, above start button */}
              {isMultiFace && (
                <div style={S.multiFaceBox}>
                  Multiple people detected in the camera frame.
                  Please ensure <strong>only one person</strong> is visible and try again.
                </div>
              )}

              <div style={S.instrBox}>
                <div style={S.instrTitle}>During the 3-second capture:</div>
                {INSTRUCTIONS.map((ins, i) => (
                  <div key={i} style={S.instrItem}>
                    <span style={S.instrNum}>{i + 1}.</span>
                    <span>{ins.text}</span>
                  </div>
                ))}
              </div>

              {error && (
                <div style={S.errorBox}>
                  {error}
                  <div onClick={startCamera}
                    style={{ color: colors.accent, cursor: 'pointer', marginTop: 5, fontWeight: 600, fontSize: '11px' }}>
                    Retry camera
                  </div>
                </div>
              )}

              <button
                style={{
                  ...btn.primary, width: '100%', padding: '11px', justifyContent: 'center',
                  opacity: camReady && countdown === null ? 1 : 0.5,
                  cursor: camReady && countdown === null ? 'pointer' : 'not-allowed'
                }}
                onClick={startCountdown}
                disabled={!camReady || countdown !== null}>
                {countdown !== null ? `Starting in ${countdown}…`
                  : camReady ? 'Begin Liveness Capture'
                    : 'Waiting for camera…'}
              </button>
            </>
          )}

          {/* Step 1 — progress */}
          {step === 1 && (
            <>
              <div style={S.progressLabel}>
                <span>Capturing frames…</span>
                <span style={{ fontFamily: fonts.mono }}>{Math.round(progress)}%</span>
              </div>
              <div style={S.progressTrack}>
                <div style={S.progressFill(progress)} />
              </div>
              <div style={{ fontSize: '10px', color: colors.gray400, textAlign: 'right', marginTop: 3, fontFamily: fonts.mono }}>
                {Math.round(progress / 100 * TOTAL_FRAMES)} / {TOTAL_FRAMES} frames
              </div>
            </>
          )}

          {/* Step 2 — analysing */}
          {step === 2 && (
            <div style={{ textAlign: 'center', color: colors.gray500, fontSize: '12px', padding: '4px 0' }}>
              Running liveness signals on {TOTAL_FRAMES} frames…
            </div>
          )}

          {/* Step 3 — success */}
          {step === 3 && (
            <div style={{ textAlign: 'center', padding: '20px 0' }}>
              <div style={S.successIcon}>✓</div>
              <h2 style={{
                fontFamily: fonts.display, fontSize: '18px', fontWeight: 400,
                color: colors.successMid, marginBottom: '6px', letterSpacing: '-0.02em'
              }}>
                Enrollment Complete
              </h2>
              {liveness && (
                <div style={S.livenessTag}>
                  Liveness: {liveness.signals}/3 signals passed
                </div>
              )}
              <p style={{ color: colors.gray500, fontSize: '12px', marginBottom: '24px', lineHeight: 1.7 }}>
                Your face has been registered.<br />
                You can now start any available exam.
              </p>
              <button style={{ ...btn.primary, padding: '10px 28px', justifyContent: 'center' }}
                onClick={() => navigate('/dashboard')}>
                Go to Dashboard
              </button>
            </div>
          )}
        </div>

        <canvas ref={canvasRef} style={{ display: 'none' }} />

        {(step === 0 || step === 3) && (
          <button style={{ ...btn.ghost, width: '100%', marginTop: '10px', justifyContent: 'center' }}
            onClick={() => navigate('/dashboard')}>
            Back to Dashboard
          </button>
        )}

        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
      </div>
    </div>
  );
}