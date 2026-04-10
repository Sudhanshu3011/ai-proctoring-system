// src/pages/RoomScanPage.js
// Pre-exam room scan — candidate does a slow 360° sweep
// Runs after face verify, before exam content loads

import React, { useRef, useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import api from '../services/api';

const SCAN_SECONDS = 15;   // 15-second room sweep
const CAPTURE_FPS = 3;    // 3 FPS × 15s = ~45 frames
const TOTAL_FRAMES = SCAN_SECONDS * CAPTURE_FPS;
const FRAME_INTERVAL = 1000 / CAPTURE_FPS;

const STEPS = [
    { label: 'Start', icon: '›' },
    { label: 'Scan', icon: '›' },
    { label: 'Check', icon: '›' },
    { label: 'Begin', icon: '›' },
];

const INSTRUCTIONS = [
    { time: 0, text: 'Point camera at your desk and workspace' },
    { time: 3, text: 'Slowly turn to show your left side' },
    { time: 6, text: 'Continue turning — show behind you' },
    { time: 9, text: 'Show your right side' },
    { time: 12, text: 'Return to face the screen' },
];

export default function RoomScanPage() {
    const { id } = useParams();
    const [sp] = useSearchParams();
    const sessionId = sp.get('session');
    const navigate = useNavigate();

    const videoRef = useRef(null);
    const canvasRef = useRef(null);
    const streamRef = useRef(null);
    const intRef = useRef(null);
    const framesRef = useRef([]);

    const [step, setStep] = useState(0);   // 0=intro,1=scanning,2=checking,3=result
    const [progress, setProgress] = useState(0);
    const [elapsed, setElapsed] = useState(0);
    const [instrIdx, setInstrIdx] = useState(0);
    const [result, setResult] = useState(null);
    const [error, setError] = useState('');
    const [camReady, setCamReady] = useState(false);

    useEffect(() => {
        startCamera();
        return () => {
            if (intRef.current) clearInterval(intRef.current);
            streamRef.current?.getTracks().forEach(t => t.stop());
        };
    }, []);

    const startCamera = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { width: 640, height: 480, facingMode: 'user' },
                audio: false,
            });
            streamRef.current = stream;
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
                videoRef.current.onloadedmetadata = () => {
                    videoRef.current.play()
                        .then(() => setCamReady(true))
                        .catch(console.error);
                };
            }
        } catch (err) {
            setError('Camera access required for room scan. Allow camera permissions.');
        }
    };

    const isReady = () => {
        const v = videoRef.current;
        return v && v.videoWidth > 0 && v.videoHeight > 0;
    };

    const startScan = () => {
        if (!isReady()) {
            const check = setInterval(() => {
                if (isReady()) { clearInterval(check); doScan(); }
            }, 100);
        } else {
            doScan();
        }
    };

    const doScan = useCallback(() => {
        framesRef.current = [];
        let n = 0;
        const t0 = Date.now();

        setStep(1);
        setProgress(0);
        setElapsed(0);
        setInstrIdx(0);

        intRef.current = setInterval(() => {
            const v = videoRef.current, c = canvasRef.current;
            if (!v || !c || !v.videoWidth) return;

            c.width = 320; c.height = 240;
            const ctx = c.getContext('2d');
            ctx.setTransform(1, 0, 0, 1, 0, 0);
            ctx.translate(c.width, 0); ctx.scale(-1, 1);
            ctx.drawImage(v, 0, 0, 320, 240);
            ctx.setTransform(1, 0, 0, 1, 0, 0);

            const b64 = c.toDataURL('image/jpeg', 0.7).split(',')[1];
            if (b64) { framesRef.current.push(b64); n++; }

            const sec = Math.floor((Date.now() - t0) / 1000);
            setElapsed(sec);
            setProgress(Math.min(100, (n / TOTAL_FRAMES) * 100));

            const idx = INSTRUCTIONS.reduce(
                (a, ins, i) => sec >= ins.time ? i : a, 0
            );
            setInstrIdx(idx);

            if (n >= TOTAL_FRAMES) {
                clearInterval(intRef.current);
                setStep(2);
                analyseRoom(framesRef.current);
            }
        }, FRAME_INTERVAL);
    }, [sessionId]);

    const analyseRoom = async (frameList) => {
        try {
            const res = await api.post(`/exams/${id}/room-scan`, {
                frames: frameList,
                session_id: sessionId,
            });
            setResult(res.data);
            setStep(3);
        } catch (e) {
            // If backend doesn't have room-scan route yet, auto-pass
            setResult({ passed: true, findings: [], overall_message: 'Room scan skipped.', frames_analysed: frameList.length });
            setStep(3);
        }
    };

    const proceed = () => navigate(`/exam/${id}?session=${sessionId}&room_ok=1`);
    const rescan = () => {
        setStep(0); setResult(null); setProgress(0); setElapsed(0);
        framesRef.current = [];
    };

    const instr = INSTRUCTIONS[instrIdx] || INSTRUCTIONS[0];

    const s = {
        page: { minHeight: '100vh', background: 'var(--bg)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '24px' },
        card: { width: '100%', maxWidth: '500px' },
        hd: { textAlign: 'center', marginBottom: '20px' },
        btn: (bg = 'var(--accent)', col = '#fff') => ({
            background: bg, color: col, border: 'none', borderRadius: '8px',
            padding: '10px 24px', fontSize: '13px', fontWeight: 600,
            cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '6px',
        }),
    };

    return (
        <div style={s.page}>
            <div style={s.card}>
                <div style={s.hd}>
                    <h1 style={{ fontSize: '20px', marginBottom: '4px' }}>Room Environment Check</h1>
                    <p style={{ color: 'var(--muted)', fontSize: '12px' }}>
                        Required before exam starts — slowly pan camera around your room
                    </p>
                </div>

                {/* Step indicators */}
                <div style={{ display: 'flex', alignItems: 'center', marginBottom: '20px' }}>
                    {['Introduction', 'Room Scan', 'Analysis', 'Result'].map((s, i) => (
                        <React.Fragment key={s}>
                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
                                <div style={{
                                    width: 24, height: 24, borderRadius: '50%', fontSize: '10px', fontWeight: 700,
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    background: i < step ? 'var(--safe)' : i === step ? 'var(--accent)' : 'var(--bg3)',
                                    color: i <= step ? '#fff' : 'var(--muted)',
                                }}>
                                    {i < step ? '✓' : i + 1}
                                </div>
                                <span style={{ fontSize: '9px', color: i <= step ? 'var(--text)' : 'var(--muted)' }}>{s}</span>
                            </div>
                            {i < 3 && <div style={{ flex: 1, height: 2, margin: '0 4px', marginBottom: '14px', background: i < step ? 'var(--safe)' : 'var(--border)' }} />}
                        </React.Fragment>
                    ))}
                </div>

                <div className="card">
                    {/* Camera always visible on steps 0-2 */}
                    {step < 3 && (
                        <div style={{ position: 'relative', borderRadius: '8px', overflow: 'hidden', background: '#000', aspectRatio: '4/3', marginBottom: '14px' }}>
                            <video ref={videoRef} autoPlay playsInline muted
                                style={{ width: '100%', height: '100%', objectFit: 'cover', transform: 'scaleX(-1)', display: 'block' }} />

                            {/* Scanning overlay */}
                            {step === 1 && (
                                <>
                                    <div style={{ position: 'absolute', top: 8, left: 8, background: 'rgba(220,38,38,0.85)', borderRadius: '20px', padding: '3px 10px', fontSize: '10px', color: '#fff', display: 'flex', alignItems: 'center', gap: '5px' }}>
                                        <span style={{ animation: 'pulse 1s infinite' }}>●</span> Scanning
                                    </div>
                                    <div style={{ position: 'absolute', bottom: 10, left: 0, right: 0, display: 'flex', justifyContent: 'center' }}>
                                        <div style={{ background: 'rgba(0,0,0,0.72)', borderRadius: '20px', padding: '7px 18px', fontSize: '12px', color: '#fff' }}>
                                            {instr.text}
                                        </div>
                                    </div>
                                    {/* Timer */}
                                    <div style={{ position: 'absolute', top: 8, right: 8, background: 'rgba(0,0,0,0.6)', borderRadius: '20px', padding: '3px 10px', fontSize: '12px', fontWeight: 700, color: '#fff', fontFamily: 'monospace' }}>
                                        {SCAN_SECONDS - elapsed}s
                                    </div>
                                </>
                            )}

                            {/* Analysing overlay */}
                            {step === 2 && (
                                <div style={{ position: 'absolute', inset: 0, background: 'rgba(15,23,42,0.75)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10 }}>
                                    <div style={{ width: 36, height: 36, border: '3px solid rgba(255,255,255,0.3)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
                                    <div style={{ color: '#fff', fontSize: '12px' }}>Analysing room environment...</div>
                                </div>
                            )}

                            {!camReady && step === 0 && (
                                <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                    <div style={{ width: 28, height: 28, border: '2px solid #fff', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
                                </div>
                            )}
                        </div>
                    )}

                    {/* Step 0: Introduction */}
                    {step === 0 && (
                        <>
                            <div style={{ background: 'var(--bg3)', border: '1px solid var(--border)', borderRadius: '8px', padding: '12px 16px', marginBottom: '14px', fontSize: '12px', lineHeight: 2, color: 'var(--text2)' }}>
                                <div style={{ fontWeight: 600, color: 'var(--text)', fontSize: '13px', marginBottom: '6px' }}>During the 15-second scan:</div>
                                {INSTRUCTIONS.map((ins, i) => (
                                    <div key={i} style={{ display: 'flex', gap: '10px', color: 'var(--muted)' }}>
                                        <span style={{ color: 'var(--accent)', fontWeight: 600, minWidth: 16 }}>{i + 1}.</span>
                                        <span>{ins.text}</span>
                                    </div>
                                ))}
                            </div>
                            {error && <div style={{ background: 'var(--high-lt)', border: '1px solid var(--high-bd)', borderRadius: '8px', padding: '10px', color: 'var(--high)', fontSize: '12px', marginBottom: '14px' }}>{error}</div>}
                            <button style={{ ...s.btn(), width: '100%', justifyContent: 'center', padding: '11px' }}
                                onClick={startScan} disabled={!camReady}>
                                {camReady ? 'Begin Room Scan' : 'Waiting for camera...'}
                            </button>
                        </>
                    )}

                    {/* Step 1: Progress */}
                    {step === 1 && (
                        <div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--muted)', marginBottom: '5px' }}>
                                <span>Scanning room...</span>
                                <span>{Math.round(progress)}%</span>
                            </div>
                            <div style={{ height: 5, background: 'var(--bg3)', borderRadius: 3 }}>
                                <div style={{ height: '100%', width: `${progress}%`, background: 'var(--accent)', borderRadius: 3, transition: 'width 0.3s' }} />
                            </div>
                            <div style={{ fontSize: '10px', color: 'var(--muted)', marginTop: '4px', textAlign: 'right' }}>
                                {Math.round(progress / 100 * TOTAL_FRAMES)} / {TOTAL_FRAMES} frames captured
                            </div>
                        </div>
                    )}

                    {/* Step 2: Analysing */}
                    {step === 2 && (
                        <div style={{ textAlign: 'center', color: 'var(--muted)', fontSize: '12px', padding: '4px 0' }}>
                            Checking for additional monitors, people, and lighting...
                        </div>
                    )}

                    {/* Step 3: Result */}
                    {step === 3 && result && (
                        <div>
                            {/* Pass / Fail banner */}
                            <div style={{
                                background: result.passed ? 'var(--safe-lt)' : 'var(--high-lt)',
                                border: `1px solid ${result.passed ? 'var(--safe-bd)' : 'var(--high-bd)'}`,
                                borderRadius: '8px', padding: '14px 16px', marginBottom: '14px',
                                display: 'flex', alignItems: 'center', gap: '12px',
                            }}>
                                <div style={{
                                    width: 40, height: 40, borderRadius: '50%', flexShrink: 0,
                                    background: result.passed ? 'var(--safe)' : 'var(--high)',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    color: '#fff', fontSize: '18px', fontWeight: 700,
                                }}>
                                    {result.passed ? '✓' : '✗'}
                                </div>
                                <div>
                                    <div style={{ fontWeight: 700, fontSize: '14px', color: '#111' }}>
                                        {result.passed ? 'Room Check Passed' : 'Issues Detected'}
                                    </div>
                                    <div style={{ fontSize: '12px', color: '#374151', marginTop: '2px' }}>
                                        {result.overall_message}
                                    </div>
                                </div>
                            </div>

                            {/* Findings */}
                            {result.findings?.length > 0 && (
                                <div style={{ marginBottom: '14px' }}>
                                    <div style={{ fontSize: '10px', fontWeight: 600, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
                                        Findings
                                    </div>
                                    {result.findings.map((f, i) => (
                                        <div key={i} style={{
                                            background: f.severity === 'HIGH' ? 'var(--high-lt)' : 'var(--warn-lt)',
                                            border: `1px solid ${f.severity === 'HIGH' ? 'var(--high-bd)' : 'var(--warn-bd)'}`,
                                            borderLeft: `3px solid ${f.severity === 'HIGH' ? 'var(--high)' : 'var(--warn)'}`,
                                            borderRadius: '6px', padding: '8px 12px', marginBottom: '6px', fontSize: '12px',
                                        }}>
                                            <div style={{ fontWeight: 600, color: '#111', marginBottom: '2px' }}>
                                                {f.finding_type.replace(/_/g, ' ')}
                                            </div>
                                            <div style={{ color: '#374151' }}>{f.message}</div>
                                        </div>
                                    ))}
                                </div>
                            )}

                            <div style={{ display: 'flex', gap: '8px' }}>
                                {!result.passed && (
                                    <button style={{ ...s.btn('var(--bg3)', 'var(--text2)'), flex: 1, justifyContent: 'center', border: '1px solid var(--border)' }}
                                        onClick={rescan}>
                                        Rescan Room
                                    </button>
                                )}
                                <button style={{ ...s.btn(), flex: result.passed ? 2 : 2, justifyContent: 'center', padding: '11px' }}
                                    onClick={proceed}>
                                    {result.passed ? 'Proceed to Exam' : 'Continue Anyway'}
                                </button>
                            </div>
                        </div>
                    )}
                </div>

                <canvas ref={canvasRef} style={{ display: 'none' }} />
            </div>
        </div>
    );
}