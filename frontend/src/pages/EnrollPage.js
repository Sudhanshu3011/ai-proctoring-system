// // src/pages/EnrollPage.js — MULTI-FRAME LIVENESS VERSION
// // Captures 3 seconds of video (25 frames at ~8 FPS)
// // Shows real-time liveness feedback to user
// // Sends frame sequence to backend instead of single photo

// import React, { useRef, useState, useEffect, useCallback } from 'react';
// import { useNavigate } from 'react-router-dom';
// import { authAPI } from '../services/api';

// const STEPS      = ['Position', 'Liveness', 'Processing', 'Done'];
// const CAPTURE_FPS        = 8;     // frames per second
// const CAPTURE_SECONDS    = 3;     // total capture duration
// const TOTAL_FRAMES       = CAPTURE_FPS * CAPTURE_SECONDS;  // = 24
// const FRAME_INTERVAL_MS  = 1000 / CAPTURE_FPS;

// // Liveness instruction shown during capture
// const INSTRUCTIONS = [
//   { icon:'👁', text:'Look straight at camera', time:0   },
//   { icon:'😑', text:'Blink naturally',          time:800 },
//   { icon:'↔',  text:'Slowly turn head slightly',time:1600},
//   { icon:'😊', text:'Return to center',         time:2400},
// ];

// export default function EnrollPage() {
//   const navigate   = useNavigate();
//   const videoRef   = useRef(null);
//   const canvasRef  = useRef(null);
//   const streamRef  = useRef(null);
//   const captureRef = useRef(null);  // interval ref

//   const [step,      setStep]     = useState(0);   // 0=position,1=capturing,2=processing,3=done
//   const [frames,    setFrames]   = useState([]);  // collected base64 frames
//   const [progress,  setProgress] = useState(0);  // 0-100 capture progress
//   const [currentInstr, setInstr] = useState(0);  // current instruction index
//   const [loading,   setLoading]  = useState(false);
//   const [error,     setError]    = useState('');
//   const [liveness,  setLiveness] = useState(null); // result from backend
//   const [countdown, setCount]    = useState(null);

//   useEffect(() => { startCamera(); return () => stopCapture(); }, []);

//   // const startCamera = async () => {
//   //   try {
//   //     const stream = await navigator.mediaDevices.getUserMedia({
//   //       video: { width: 640, height: 480, facingMode: 'user', frameRate: CAPTURE_FPS },
//   //     });
//   //     streamRef.current = stream;
//   //     if (videoRef.current) videoRef.current.srcObject = stream;
//   //   } catch {
//   //     setError('Camera access denied. Please allow camera permissions.');
//   //   }
//   // };

//   const startCamera = async () => {
//     try {
//       const stream = await navigator.mediaDevices.getUserMedia({
//         video: { width: 640, height: 480, facingMode: "user" },
//       });

//       if (videoRef.current) {
//         videoRef.current.srcObject = stream;

//         // Add this event listener to know exactly when video is ready to play frames
//         videoRef.current.addEventListener("canplay", () => {
//           console.log("✅ Video canplay event fired, video readyState:", videoRef.current.readyState);
//           // You can now start the countdown or capture here or set a flag
//         }, { once: true }); // only fire once, then remove listener
//       }
//     } catch (error) {
//       setError("Camera access denied or unavailable.");
//     }
//   };

//   const stopCapture = () => {
//     if (captureRef.current) clearInterval(captureRef.current);
//     streamRef.current?.getTracks().forEach(t => t.stop());
//   };

//   // Start 3-second countdown then begin capture
//   // const startCaptureWithCountdown = () => {
//   //   console.log("Start capture clicked");
//   //   let c = 3;
//   //   setCount(c);
//   //   const timer = setInterval(() => {
//   //     c--;
//   //     if (c <= 0) {
//   //       clearInterval(timer);
//   //       setCount(null);
//   //       beginCapture();
//   //     } else {
//   //       setCount(c);
//   //     }
//   //   }, 1000);
//   // };
  
//   const startCaptureWithCountdown = () => {
//     if (videoRef.current.readyState >= 2) {
//       // Ready: start countdown immediately
//       doStartCountdown();
//     } else {
//       // Not ready: wait for canplay event
//       videoRef.current.addEventListener(
//         "canplay",
//         () => {
//           console.log("✅ Video ready, starting countdown");
//           doStartCountdown();
//         },
//         { once: true }
//       );
//     }
//   };

// const doStartCountdown = () => {
//   let c = 3;
//   setCount(c);
//   const timer = setInterval(() => {
//     c--;
//     if (c <= 0) {
//       clearInterval(timer);
//       setCount(null);
//       beginCapture();
//     } else {
//       setCount(c);
//     }
//   }, 1000);
// };

//   const beginCapture = useCallback(() => {
//     const collected = [];
//     let frameCount  = 0;
//     setStep(1);
//     setFrames([]);
//     setProgress(0);
//     setError('');

//     const startTime = Date.now();

//     captureRef.current = setInterval(() => {
//       const canvas = canvasRef.current;
//       const video  = videoRef.current;
//       // if (!canvas || !video || video.readyState < 2) return;
//       if (!canvas || !video) {
//        console.log("Canvas or video missing");
//        return;
//       }
//       console.log("Video readyState:", video.readyState);
//       if (video.readyState < 2) {
//       console.log("Video not ready yet");
//       return;
//       }
//       // Capture frame
//       canvas.width  = 320;  // smaller = faster upload
//       canvas.height = 240;
//       const ctx = canvas.getContext('2d');
//       ctx.translate(canvas.width, 0);  // mirror
//       ctx.scale(-1, 1);
//       ctx.drawImage(video, 0, 0, 320, 240);
//       ctx.setTransform(1, 0, 0, 1, 0, 0);

//       const b64 = canvas.toDataURL('image/jpeg', 0.8).split(',')[1];
//       collected.push(b64);
//       frameCount++;

//       // Update progress bar
//       const pct = Math.min(100, (frameCount / TOTAL_FRAMES) * 100);
//       setProgress(pct);

//       // Update instruction based on elapsed time
//       const elapsed = Date.now() - startTime;
//       const instrIdx = INSTRUCTIONS.findIndex(
//         (ins, i) => elapsed >= ins.time && (i === INSTRUCTIONS.length - 1 || elapsed < INSTRUCTIONS[i+1].time)
//       );
//       if (instrIdx >= 0) setInstr(instrIdx);

//       // Capture complete
//       if (frameCount >= TOTAL_FRAMES) {
//         clearInterval(captureRef.current);
//         setFrames(collected);
//         setStep(2);
//         submitFrames(collected);
//       }
//       console.log(`Captured frame ${frameCount + 1}/${TOTAL_FRAMES}`);
//     }, FRAME_INTERVAL_MS);
//   }, []);

//   const submitFrames = async (frameList) => {
//     setLoading(true);
//     setError('');
//     try {
//       console.log("Calling enrollFace API...");
//       const res = await authAPI.enrollFace({
//         frame_sequence: frameList,
//         fps:            CAPTURE_FPS,
//       });
//       setLiveness({ signals: res.data.liveness_signals, message: res.data.message });
//       setStep(3);
//       stopCapture();
//       console.log("Submitting frames:", frameList.length);
//     } catch (e) {
//       const detail = e.response?.data?.detail || 'Enrollment failed.';
//       setError(detail);
//       setStep(0);       // go back to start
//       setProgress(0);
//       // Restart camera for retry
//       startCamera();
//     } finally {
//       setLoading(false);
//     }
//   };

//   const retake = () => {
//     setError('');
//     setFrames([]);
//     setProgress(0);
//     setStep(0);
//     startCamera();
//   };

//   const instr = INSTRUCTIONS[currentInstr] || INSTRUCTIONS[0];

//   return (
//     <div style={{
//       minHeight: '100vh', background: 'var(--bg)',
//       display: 'flex', flexDirection: 'column',
//       alignItems: 'center', justifyContent: 'center', padding: '24px',
//     }}>
//       <div style={{ width: '100%', maxWidth: '520px' }}>

//         {/* Header */}
//         <div style={{ textAlign: 'center', marginBottom: '20px' }}>
//           <div style={{ fontSize: '32px', marginBottom: '8px' }}>👤</div>
//           <h1 style={{ fontSize: '22px', marginBottom: '4px' }}>Face Enrollment</h1>
//           <p style={{ color: 'var(--muted)', fontSize: '12px' }}>
//             Multi-frame liveness detection — required once before your first exam
//           </p>
//         </div>

//         {/* Steps */}
//         <div style={{ display: 'flex', alignItems: 'center', marginBottom: '20px', padding: '0 10px' }}>
//           {STEPS.map((s, i) => (
//             <React.Fragment key={s}>
//               <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
//                 <div style={{
//                   width: 26, height: 26, borderRadius: '50%', fontSize: '11px',
//                   fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center',
//                   background: i < step ? 'var(--safe)' : i === step ? 'var(--accent)' : 'var(--bg3)',
//                   color: i <= step ? 'white' : 'var(--muted)',
//                   transition: 'all 0.3s',
//                 }}>
//                   {i < step ? '✓' : i + 1}
//                 </div>
//                 <span style={{ fontSize: '10px', color: i <= step ? 'var(--text)' : 'var(--muted)' }}>
//                   {s}
//                 </span>
//               </div>
//               {i < STEPS.length - 1 && (
//                 <div style={{
//                   flex: 1, height: 2, margin: '0 4px', marginBottom: '14px',
//                   background: i < step ? 'var(--safe)' : 'var(--border)',
//                   transition: 'background 0.3s',
//                 }} />
//               )}
//             </React.Fragment>
//           ))}
//         </div>

//         <div className="card">

//           {/* Step 0 — Position */}
//           {step === 0 && (
//             <>
//               <div style={{
//                 position: 'relative', borderRadius: '10px', overflow: 'hidden',
//                 background: '#000', aspectRatio: '4/3', marginBottom: '14px',
//               }}>
//                 <video ref={videoRef} autoPlay playsInline muted
//                   style={{ width: '100%', height: '100%', objectFit: 'cover',
//                     transform: 'scaleX(-1)', display: 'block' }}
//                 />
//                 {/* Face guide oval */}
//                 <div style={{
//                   position: 'absolute', inset: 0, pointerEvents: 'none',
//                   display: 'flex', alignItems: 'center', justifyContent: 'center',
//                 }}>
//                   <div style={{
//                     width: 170, height: 210,
//                     border: '2px dashed rgba(59,130,246,0.7)',
//                     borderRadius: '50%',
//                     boxShadow: '0 0 0 9999px rgba(0,0,0,0.25)',
//                   }} />
//                 </div>
//                 {/* Countdown overlay */}
//                 {countdown !== null && (
//                   <div style={{
//                     position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.6)',
//                     display: 'flex', alignItems: 'center', justifyContent: 'center',
//                   }}>
//                     <div style={{
//                       fontSize: '80px', fontFamily: 'Syne', fontWeight: 800,
//                       color: 'white', animation: 'pulse 1s infinite',
//                     }}>
//                       {countdown}
//                     </div>
//                   </div>
//                 )}
//               </div>

//               {/* What will happen */}
//               <div style={{
//                 background: 'var(--bg3)', borderRadius: '8px', padding: '12px 16px',
//                 marginBottom: '14px', fontSize: '12px', lineHeight: 2,
//               }}>
//                 <div style={{ color: 'var(--text)', fontFamily: 'Syne', fontWeight: 600, marginBottom: '6px' }}>
//                   What happens during capture (3 seconds):
//                 </div>
//                 {INSTRUCTIONS.map((ins, i) => (
//                   <div key={i} style={{ color: 'var(--muted)', display: 'flex', gap: '8px' }}>
//                     <span>{ins.icon}</span>
//                     <span>{ins.text}</span>
//                   </div>
//                 ))}
//               </div>

//               {error && (
//                 <div style={{
//                   background: '#1f0a0a', border: '1px solid #7f1d1d',
//                   borderRadius: '8px', padding: '10px 14px',
//                   color: '#f87171', fontSize: '12px', marginBottom: '14px',
//                 }}>
//                   ⚠ {error}
//                 </div>
//               )}

//               <button className="btn-primary"
//                 style={{ width: '100%', padding: '12px', fontSize: '14px' }}
//                 onClick={startCaptureWithCountdown}
//                 disabled={countdown !== null}>
//                 {countdown !== null ? `Starting in ${countdown}...` : '▶ Start Liveness Capture'}
//               </button>
//             </>
//           )}

//           {/* Step 1 — Capturing */}
//           {step === 1 && (
//             <>
//               <div style={{
//                 position: 'relative', borderRadius: '10px', overflow: 'hidden',
//                 background: '#000', aspectRatio: '4/3', marginBottom: '14px',
//               }}>
//                 <video ref={videoRef} autoPlay playsInline muted
//                   style={{ width: '100%', height: '100%', objectFit: 'cover',
//                     transform: 'scaleX(-1)', display: 'block' }}
//                 />
//                 {/* Recording indicator */}
//                 <div style={{
//                   position: 'absolute', top: 10, left: 10,
//                   background: 'rgba(220,38,38,0.85)', borderRadius: '20px',
//                   padding: '4px 12px', fontSize: '11px', color: 'white',
//                   display: 'flex', alignItems: 'center', gap: '6px',
//                 }}>
//                   <span style={{ animation: 'pulse 1s infinite' }}>●</span>
//                   Recording liveness
//                 </div>
//                 {/* Current instruction */}
//                 <div style={{
//                   position: 'absolute', bottom: 12, left: 0, right: 0,
//                   display: 'flex', justifyContent: 'center',
//                 }}>
//                   <div style={{
//                     background: 'rgba(0,0,0,0.75)', borderRadius: '20px',
//                     padding: '8px 20px', fontSize: '13px', fontFamily: 'Syne',
//                     color: 'white', display: 'flex', alignItems: 'center', gap: '8px',
//                     animation: 'slideIn 0.3s ease',
//                   }}>
//                     <span style={{ fontSize: '18px' }}>{instr.icon}</span>
//                     {instr.text}
//                   </div>
//                 </div>
//               </div>

//               {/* Progress bar */}
//               <div style={{ marginBottom: '8px' }}>
//                 <div style={{
//                   display: 'flex', justifyContent: 'space-between',
//                   fontSize: '11px', color: 'var(--muted)', marginBottom: '6px',
//                 }}>
//                   <span>Capturing frames...</span>
//                   <span>{Math.round(progress)}%</span>
//                 </div>
//                 <div style={{ height: 6, background: 'var(--border)', borderRadius: 3 }}>
//                   <div style={{
//                     height: '100%', borderRadius: 3,
//                     width: `${progress}%`,
//                     background: 'var(--accent)',
//                     transition: 'width 0.15s',
//                   }} />
//                 </div>
//               </div>

//               <div style={{ fontSize: '11px', color: 'var(--muted)', textAlign: 'center' }}>
//                 {Math.round(progress / 100 * TOTAL_FRAMES)} / {TOTAL_FRAMES} frames captured
//               </div>
//             </>
//           )}

//           {/* Step 2 — Processing */}
//           {step === 2 && (
//             <div style={{ padding: '20px 0', textAlign: 'center' }}>
//               <div style={{
//                 width: 60, height: 60,
//                 border: '3px solid var(--border)', borderTopColor: 'var(--accent)',
//                 borderRadius: '50%', animation: 'spin 0.8s linear infinite',
//                 margin: '0 auto 16px',
//               }} />
//               <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
//               <div style={{ fontFamily: 'Syne', fontSize: '16px', marginBottom: '8px' }}>
//                 Analysing liveness...
//               </div>
//               <div style={{ color: 'var(--muted)', fontSize: '12px', lineHeight: 1.8 }}>
//                 Running 3 liveness signals on {TOTAL_FRAMES} frames<br/>
//                 Checking blink cycle, head movement, temporal variation<br/>
//                 Extracting FaceNet embedding from best frame
//               </div>
//             </div>
//           )}

//           {/* Step 3 — Done */}
//           {step === 3 && (
//             <div style={{ textAlign: 'center', padding: '20px 0' }}>
//               <div style={{
//                 width: 80, height: 80, borderRadius: '50%',
//                 background: '#052e16', border: '2px solid var(--safe)',
//                 display: 'flex', alignItems: 'center', justifyContent: 'center',
//                 fontSize: '36px', margin: '0 auto 16px',
//               }}>✓</div>
//               <h2 style={{ fontSize: '20px', color: 'var(--safe)', marginBottom: '8px' }}>
//                 Enrollment Successful
//               </h2>
//               {liveness && (
//                 <div style={{
//                   display: 'inline-flex', alignItems: 'center', gap: '8px',
//                   background: '#052e16', border: '1px solid #14532d',
//                   borderRadius: '20px', padding: '4px 16px',
//                   marginBottom: '12px', fontSize: '12px', color: 'var(--safe)',
//                 }}>
//                   Liveness: {liveness.signals}/3 signals passed
//                 </div>
//               )}
//               <p style={{ color: 'var(--muted)', fontSize: '13px', lineHeight: 1.7, marginBottom: '24px' }}>
//                 Multi-frame liveness verified.<br/>
//                 512-dimensional FaceNet embedding stored.
//               </p>
//               <button className="btn-primary" style={{ padding: '12px 36px' }}
//                 onClick={() => navigate('/dashboard')}>
//                 Go to Dashboard →
//               </button>
//             </div>
//           )}
//         </div>

//         <canvas ref={canvasRef} style={{ display: 'none' }} />

//         {step < 3 && step !== 1 && (
//           <button className="btn-ghost" style={{ width: '100%', marginTop: '12px' }}
//             onClick={() => navigate('/dashboard')}>
//             ← Back to Dashboard
//           </button>
//         )}
//       </div>
//     </div>
//   );
// }
// -----------------------------
// src/pages/EnrollPage.js — MULTI-FRAME LIVENESS VERSION
// Refactored startCamera for proper video playback
// -----------------------------
// src/pages/EnrollPage.js — FIXED MULTI-FRAME LIVENESS VERSION

import React, { useRef, useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { authAPI } from '../services/api';

const STEPS = ['Position', 'Liveness', 'Processing', 'Done'];

const CAPTURE_FPS = 8;
const CAPTURE_SECONDS = 3;
const TOTAL_FRAMES = CAPTURE_FPS * CAPTURE_SECONDS; // 24
const FRAME_INTERVAL_MS = 1000 / CAPTURE_FPS;

const INSTRUCTIONS = [
  { icon: '👁', text: 'Look straight at camera', time: 0 },
  { icon: '😑', text: 'Blink naturally', time: 800 },
  { icon: '↔', text: 'Slowly turn head slightly', time: 1600 },
  { icon: '😊', text: 'Return to center', time: 2400 },
];

export default function EnrollPage() {
  const navigate = useNavigate();

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const captureRef = useRef(null);

  const [step, setStep] = useState(0);
  const [frames, setFrames] = useState([]);
  const [progress, setProgress] = useState(0);
  const [currentInstr, setInstr] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [liveness, setLiveness] = useState(null);
  const [countdown, setCount] = useState(null);

  useEffect(() => {
    startCamera();
    return () => stopCapture();
  }, []);

  // ✅ START CAMERA (FIXED)
  const startCamera = async () => {
    console.log("📷 Starting camera...");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480, facingMode: "user" },
        audio: false
      });

      console.log("✅ Camera stream received");

      streamRef.current = stream;

      if (videoRef.current) {
        videoRef.current.srcObject = stream;

        videoRef.current.onloadedmetadata = () => {
          console.log("🎥 Video metadata loaded");
          videoRef.current.play()
            .then(() => console.log("▶ Video playing"))
            .catch(err => console.error("❌ Video play error:", err));
        };

        videoRef.current.oncanplay = () => {
          console.log("✅ Video ready (canplay)");
        };
      }

    } catch (err) {
      console.error("❌ Camera error:", err);
      setError("Camera access denied or unavailable.");
    }
  };

  // ✅ STOP CAMERA
  const stopCapture = () => {
    console.log("🛑 Stopping capture");

    if (captureRef.current) clearInterval(captureRef.current);

    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => {
        console.log("🛑 Stopping track:", track.kind);
        track.stop();
      });
    }
  };

  // ✅ COUNTDOWN START
  const startCaptureWithCountdown = () => {
    console.log("⏳ Start capture clicked");

    if (isVideoReady()) {
      console.log("✅ Video fully ready");
      doStartCountdown();
    } else {
      console.log("⏳ Waiting for real video readiness...");

      const checkReady = setInterval(() => {
        if (isVideoReady()) {
          console.log("✅ Video dimensions ready → starting countdown");
          clearInterval(checkReady);
          doStartCountdown();
        }
      }, 100);
    }
  };
  const isVideoReady = () => {
  const v = videoRef.current;
  return v && v.videoWidth > 0 && v.videoHeight > 0;
};

  const doStartCountdown = () => {
    let c = 3;
    setCount(c);

    const timer = setInterval(() => {
      c--;
      if (c <= 0) {
        clearInterval(timer);
        setCount(null);
        beginCapture();
      } else {
        setCount(c);
      }
    }, 1000);
  };

  // ✅ CAPTURE LOGIC (FIXED)
  const beginCapture = useCallback(() => {
    console.log("🎬 Capture started");

    const collected = [];
    let frameCount = 0;

    setStep(1);
    setFrames([]);
    setProgress(0);
    setError('');

    const startTime = Date.now();

    captureRef.current = setInterval(() => {
      const canvas = canvasRef.current;
      const video = videoRef.current;

      console.log("Video size:", video.videoWidth, video.videoHeight);

      if (!canvas || !video) {
        console.error("❌ Missing canvas/video");
        return;
      }

      if (!video.videoWidth || !video.videoHeight) {
        console.warn("⚠ Video not producing frames yet");
        return;
      }

      canvas.width = 320;
      canvas.height = 240;

      const ctx = canvas.getContext('2d');

      // reset transform
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.translate(canvas.width, 0);
      ctx.scale(-1, 1);

      ctx.drawImage(video, 0, 0, 320, 240);

      // reset again
      ctx.setTransform(1, 0, 0, 1, 0, 0);

      const b64 = canvas.toDataURL('image/jpeg', 0.8).split(',')[1];

      if (!b64) {
        console.error("❌ Base64 extraction failed");
        return;
      }

      collected.push(b64);
      frameCount++;

      console.log(`📸 Frame ${frameCount}/${TOTAL_FRAMES}`);

      const pct = Math.min(100, (frameCount / TOTAL_FRAMES) * 100);
      setProgress(pct);

      const elapsed = Date.now() - startTime;

      const instrIdx = INSTRUCTIONS.findIndex(
        (ins, i) =>
          elapsed >= ins.time &&
          (i === INSTRUCTIONS.length - 1 || elapsed < INSTRUCTIONS[i + 1].time)
      );

      if (instrIdx >= 0) setInstr(instrIdx);

      if (frameCount >= TOTAL_FRAMES) {
        console.log("✅ Capture complete");

        clearInterval(captureRef.current);

        setFrames(collected);
        setStep(2);

        submitFrames(collected);
      }

    }, FRAME_INTERVAL_MS);
  }, []);

  // ✅ SUBMIT
  const submitFrames = async (frameList) => {
    console.log("📤 Sending frames:", frameList.length);

    setLoading(true);
    setError('');

    try {
      const res = await authAPI.enrollFace({
        frame_sequence: frameList,
        fps: CAPTURE_FPS,
      });

      console.log("✅ Backend response:", res.data);

      setLiveness({
        signals: res.data.liveness_signals,
        message: res.data.message,
      });

      setStep(3);
      stopCapture();

    } catch (e) {
      console.error("❌ API Error:", e);

      const detail =
        e.response?.data?.detail ||
        e.message ||
        "Enrollment failed.";

      setError(detail);

      setStep(0);
      setProgress(0);

      startCamera();

    } finally {
      setLoading(false);
    }
  };

  const instr = INSTRUCTIONS[currentInstr];

  return (
    <div style={{
      minHeight: '100vh', background: 'var(--bg)',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center', padding: '24px',
    }}>
      <div style={{ width: '100%', maxWidth: '520px' }}>

        {/* Header */}
        <div style={{ textAlign: 'center', marginBottom: '20px' }}>
          <div style={{ fontSize: '32px', marginBottom: '8px' }}>👤</div>
          <h1 style={{ fontSize: '22px', marginBottom: '4px' }}>Face Enrollment</h1>
          <p style={{ color: 'var(--muted)', fontSize: '12px' }}>
            Multi-frame liveness detection — required once before your first exam
          </p>
        </div>

        {/* Steps */}
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '20px', padding: '0 10px' }}>
          {STEPS.map((s, i) => (
            <React.Fragment key={s}>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
                <div style={{
                  width: 26, height: 26, borderRadius: '50%', fontSize: '11px',
                  fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: i < step ? 'var(--safe)' : i === step ? 'var(--accent)' : 'var(--bg3)',
                  color: i <= step ? 'white' : 'var(--muted)',
                }}>
                  {i < step ? '✓' : i + 1}
                </div>
                <span style={{ fontSize: '10px', color: i <= step ? 'var(--text)' : 'var(--muted)' }}>
                  {s}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div style={{
                  flex: 1, height: 2, margin: '0 4px', marginBottom: '14px',
                  background: i < step ? 'var(--safe)' : 'var(--border)',
                }} />
              )}
            </React.Fragment>
          ))}
        </div>
        
        <div className="card">

          {/* ✅ SINGLE PERSISTENT VIDEO (NEW) */}
          <div style={{
            position: 'relative',
            borderRadius: '10px',
            overflow: 'hidden',
            background: '#000',
            aspectRatio: '4/3',
            marginBottom: '14px',
          }}>
          
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              style={{
                width: '100%',
                height: '100%',
                objectFit: 'cover',
                transform: 'scaleX(-1)',
              }}
            />

            {/* FACE GUIDE (STEP 0) */}
            {step === 0 && (
              <div style={{
                position: 'absolute',
                inset: 0,
                pointerEvents: 'none',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                <div style={{
                  width: 170,
                  height: 210,
                  border: '2px dashed rgba(59,130,246,0.7)',
                  borderRadius: '50%',
                  boxShadow: '0 0 0 9999px rgba(0,0,0,0.25)',
                }} />
              </div>
            )}

            {/* COUNTDOWN */}
            {countdown !== null && (
              <div style={{
                position: 'absolute',
                inset: 0,
                background: 'rgba(0,0,0,0.6)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                <div style={{
                  fontSize: '80px',
                  fontWeight: 800,
                  color: 'white',
                }}>
                  {countdown}
                </div>
              </div>
            )}

            {/* STEP 1 OVERLAYS */}
            {step === 1 && (
              <>
                <div style={{
                  position: 'absolute',
                  top: 10,
                  left: 10,
                  background: 'red',
                  borderRadius: '20px',
                  padding: '4px 12px',
                  fontSize: '11px',
                  color: 'white',
                }}>
                  ● Recording
                </div>
              
                <div style={{
                  position: 'absolute',
                  bottom: 12,
                  left: 0,
                  right: 0,
                  textAlign: 'center',
                  color: 'white',
                }}>
                  {instr.icon} {instr.text}
                </div>
              </>
            )}

          </div>
          
          {/* 🔹 STEP 0 CONTENT (NO VIDEO NOW) */}
          {step === 0 && (
            <>
              <div style={{
                background: 'var(--bg3)',
                borderRadius: '8px',
                padding: '12px 16px',
                marginBottom: '14px',
                fontSize: '12px',
                lineHeight: 2,
              }}>
                <div style={{ fontWeight: 600, marginBottom: '6px' }}>
                  What happens during capture:
                </div>
            
                {INSTRUCTIONS.map((ins, i) => (
                  <div key={i} style={{ display: 'flex', gap: '8px' }}>
                    <span>{ins.icon}</span>
                    <span>{ins.text}</span>
                  </div>
                ))}
              </div>
              
              {error && (
                <div style={{
                  background: '#1f0a0a',
                  border: '1px solid #7f1d1d',
                  borderRadius: '8px',
                  padding: '10px',
                  color: '#f87171',
                  marginBottom: '14px',
                }}>
                  ⚠ {error}
                </div>
              )}

              <button
                className="btn-primary"
                style={{ width: '100%', padding: '12px' }}
                onClick={() => {
                  console.log("🟢 Start button clicked");
                  startCaptureWithCountdown();
                }}
                disabled={countdown !== null}
              >
                {countdown !== null
                  ? `Starting in ${countdown}...`
                  : '▶ Start Liveness Capture'}
              </button>
            </>
          )}

          {/* 🔹 STEP 1 CONTENT (NO VIDEO NOW) */}
          {step === 1 && (
            <>
              <div>
                <div>{Math.round(progress)}%</div>
                <div>
                  {Math.round(progress / 100 * TOTAL_FRAMES)} / {TOTAL_FRAMES} frames
                </div>
              </div>
            </>
          )}

          {/* STEP 2 */}
          {step === 2 && (
            <div style={{ textAlign: 'center', padding: '20px' }}>
              Processing...
            </div>
          )}

          {/* STEP 3 */}
          {step === 3 && (
            <div style={{ textAlign: 'center', padding: '20px' }}>
              <h2>✅ Enrollment Successful</h2>
              <p>Liveness: {liveness?.signals}/3</p>
          
              <button
                className="btn-primary"
                onClick={() => navigate('/dashboard')}
              >
                Go to Dashboard
              </button>
            </div>
          )}

        </div>

        <canvas ref={canvasRef} style={{ display: 'none' }} />

      </div>
    </div>
  );
}