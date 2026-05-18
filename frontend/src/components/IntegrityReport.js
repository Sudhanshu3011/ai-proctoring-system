import React from 'react';

const C = {
    navy: '#1e3a5f',
    navyMid: '#2d5282',
    navyLt: '#ebf4ff',
    navyBd: '#bfdbfe',
    orange: '#ea580c',
    orangeMd: '#f97316',
    orangeLt: '#fff7ed',
    orangeBd: '#fed7aa',
    white: '#ffffff',
    gray50: '#fafafa',
    gray100: '#f4f4f5',
    gray200: '#e4e4e7',
    gray300: '#d4d4d8',
    gray400: '#a1a1aa',
    gray500: '#71717a',
    gray600: '#52525b',
    gray700: '#3f3f46',
    gray900: '#18181b',
    safe: '#059669',
    safeLt: '#ecfdf5',
    safeBd: '#a7f3d0',
    danger: '#dc2626',
    dangerLt: '#fff1f2',
    dangerBd: '#fecdd3',
};

const VERDICT_CFG = {
    LIKELY_HONEST: { col: C.safe, bg: C.safeLt, bd: C.safeBd, label: 'Likely Honest', icon: '✓', bar: '#10b981' },
    SUSPICIOUS: { col: C.orange, bg: C.orangeLt, bd: C.orangeBd, label: 'Suspicious', icon: '?', bar: C.orange },
    LIKELY_CHEATING: { col: C.danger, bg: C.dangerLt, bd: C.dangerBd, label: 'Likely Cheating', icon: '!', bar: C.danger },
    CONFIRMED_CHEATING: { col: '#991b1b', bg: '#fef2f2', bd: '#fca5a5', label: 'Confirmed Cheating', icon: '✗', bar: '#991b1b' },
};

const ACTION_CFG = {
    REVIEW: { col: C.safe, label: 'No Action Required' },
    INVESTIGATE: { col: C.orange, label: 'Manual Review Required' },
    ESCALATE: { col: C.danger, label: 'Escalate to Department' },
    INVALIDATE: { col: '#991b1b', label: 'Invalidate Exam Result' },
};

const CAT_CFG = {
    IDENTITY: { col: '#7c3aed', bg: '#f5f3ff' },
    ATTENTION: { col: '#0891b2', bg: '#ecfeff' },
    OBJECTS: { col: C.danger, bg: C.dangerLt },
    AUDIO: { col: C.orange, bg: C.orangeLt },
    BROWSER: { col: C.gray600, bg: C.gray100 },
    LIVENESS: { col: C.safe, bg: C.safeLt },
    BEHAVIOUR: { col: C.navy, bg: C.navyLt },
};

function ProbBar({ value }) {
    const pct = Math.round((value || 0) * 100);
    const col = value < 0.25 ? C.safe
        : value < 0.55 ? C.orange
            : value < 0.80 ? C.danger
                : '#991b1b';

    return (
        <div>
            <div style={{
                display: 'flex', justifyContent: 'space-between',
                fontSize: '11px', color: C.gray500, marginBottom: '5px'
            }}>
                <span>Cheating probability</span>
                <span style={{
                    fontWeight: 700, color: col,
                    fontFamily: 'IBM Plex Mono, monospace'
                }}>{pct}%</span>
            </div>
            {/* Segmented track */}
            <div style={{
                height: 8, borderRadius: '99px', overflow: 'hidden',
                display: 'flex', gap: 2, background: C.gray100
            }}>
                {[
                    { w: '25%', bg: '#10b981', op: 0.25 },
                    { w: '30%', bg: C.orange, op: 0.25 },
                    { w: '25%', bg: C.danger, op: 0.25 },
                    { w: '20%', bg: '#991b1b', op: 0.25 },
                ].map(({ w, bg, op }, i) => (
                    <div key={i} style={{ width: w, height: '100%', background: bg, opacity: op }} />
                ))}
            </div>
            {/* Needle */}
            <div style={{ position: 'relative', height: 0 }}>
                <div style={{
                    position: 'absolute',
                    left: `${Math.min(98, Math.max(1, pct))}%`,
                    transform: 'translateX(-50%)',
                    width: 3, height: 14, background: col,
                    borderRadius: '2px', marginTop: '-13px',
                }} />
            </div>
            <div style={{
                display: 'flex', justifyContent: 'space-between',
                fontSize: '9px', color: C.gray400, marginTop: '8px',
                fontFamily: 'IBM Plex Mono, monospace'
            }}>
                <span>Low</span><span>Medium</span><span>High</span><span>Very High</span>
            </div>
        </div>
    );
}

export default function IntegrityReport({ assessment }) {
    if (!assessment) return null;

    const vm = VERDICT_CFG[assessment.verdict] || VERDICT_CFG.SUSPICIOUS;
    const am = ACTION_CFG[assessment.action_priority] || ACTION_CFG.REVIEW;

    return (
        <div style={{
            background: C.white,
            border: `1px solid ${vm.bd}`,
            borderTop: `3px solid ${vm.col}`,
            borderRadius: '10px',
            overflow: 'hidden',
            marginTop: '16px',
        }}>
            {/* Header */}
            <div style={{
                background: vm.bg, padding: '16px 20px',
                borderBottom: `1px solid ${vm.bd}`,
                display: 'flex', alignItems: 'center', gap: '16px'
            }}>
                <div style={{
                    width: 48, height: 48, borderRadius: '50%',
                    background: vm.col, flexShrink: 0,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: C.white, fontSize: '20px', fontWeight: 800,
                }}>
                    {vm.icon}
                </div>
                <div style={{ flex: 1 }}>
                    <div style={{
                        fontSize: '11px', fontWeight: 700, color: C.gray500,
                        textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '2px'
                    }}>
                        AI Integrity Assessment
                    </div>
                    <div style={{
                        fontFamily: 'DM Serif Display, Georgia, serif',
                        fontSize: '16px', color: C.gray900, letterSpacing: '-0.02em'
                    }}>
                        {vm.label}
                    </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                    <div style={{
                        fontFamily: 'IBM Plex Mono, monospace',
                        fontSize: '32px', fontWeight: 700, color: vm.col, lineHeight: 1
                    }}>
                        {assessment.integrity_score?.toFixed(0)}
                    </div>
                    <div style={{ fontSize: '10px', color: C.gray400, marginTop: '2px' }}>
                        Integrity / 100
                    </div>
                </div>
            </div>

            <div style={{ padding: '18px 20px' }}>
                {/* Probability bar */}
                <div style={{ marginBottom: '18px' }}>
                    <ProbBar value={assessment.cheat_probability} />
                </div>

                {/* Stats grid */}
                <div style={{
                    display: 'grid', gridTemplateColumns: 'repeat(3,1fr)',
                    gap: '10px', marginBottom: '18px'
                }}>
                    {[
                        { l: 'Confidence', v: `${Math.round((assessment.confidence || 0) * 100)}%`, c: C.gray900 },
                        { l: 'Violations', v: assessment.total_violations, c: C.gray900 },
                        { l: 'Duration', v: `${(assessment.exam_duration_min || 0).toFixed(0)}m`, c: C.gray900 },
                    ].map(({ l, v, c }) => (
                        <div key={l} style={{
                            background: C.gray50, border: `1px solid ${C.gray200}`,
                            borderRadius: '8px', padding: '10px', textAlign: 'center',
                        }}>
                            <div style={{
                                fontFamily: 'IBM Plex Mono, monospace',
                                fontSize: '18px', fontWeight: 700, color: c
                            }}>{v}</div>
                            <div style={{
                                fontSize: '10px', color: C.gray400,
                                fontWeight: 600, marginTop: '3px', textTransform: 'uppercase',
                                letterSpacing: '0.04em'
                            }}>{l}</div>
                        </div>
                    ))}
                </div>

                {/* Evidence findings */}
                {assessment.findings?.length > 0 && (
                    <div style={{ marginBottom: '16px' }}>
                        <div style={{
                            fontSize: '11px', fontWeight: 700, color: C.gray400,
                            textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '10px'
                        }}>
                            Evidence
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                            {assessment.findings.map((f, i) => {
                                const cm = CAT_CFG[f.category] || CAT_CFG.BEHAVIOUR;
                                const hi = f.weight >= 20;
                                return (
                                    <div key={i} style={{
                                        background: hi ? '#fff7ed' : C.gray50,
                                        border: `1px solid ${hi ? C.orangeBd : C.gray200}`,
                                        borderLeft: `3px solid ${hi ? C.orange : cm.col}`,
                                        borderRadius: '7px', padding: '9px 12px',
                                        display: 'flex', gap: '10px', alignItems: 'flex-start',
                                    }}>
                                        <div style={{
                                            background: cm.bg, color: cm.col,
                                            borderRadius: '5px', padding: '2px 8px',
                                            fontSize: '9px', fontWeight: 700,
                                            textTransform: 'uppercase', letterSpacing: '0.05em',
                                            flexShrink: 0, marginTop: '1px',
                                        }}>
                                            {f.category}
                                        </div>
                                        <div style={{ flex: 1 }}>
                                            <div style={{
                                                fontSize: '12px', fontWeight: 600,
                                                color: C.gray900, marginBottom: '2px'
                                            }}>
                                                {f.finding}
                                            </div>
                                            {f.evidence && (
                                                <div style={{ fontSize: '11px', color: C.gray500 }}>
                                                    {f.evidence}
                                                </div>
                                            )}
                                        </div>
                                        <div style={{
                                            fontFamily: 'IBM Plex Mono, monospace',
                                            fontSize: '10px', fontWeight: 700,
                                            color: f.weight >= 20 ? C.orange : f.weight >= 10 ? C.orange : C.gray400,
                                            flexShrink: 0,
                                        }}>
                                            −{f.weight?.toFixed(0)}pts
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}

                {/* Recommended action */}
                <div style={{
                    background: `${am.col}10`,
                    border: `1px solid ${am.col}40`,
                    borderLeft: `3px solid ${am.col}`,
                    borderRadius: '7px', padding: '12px 14px',
                }}>
                    <div style={{
                        fontSize: '10px', fontWeight: 700, color: C.gray400,
                        textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '4px'
                    }}>
                        Recommended Action
                    </div>
                    <div style={{
                        fontWeight: 700, fontSize: '13px',
                        color: am.col, marginBottom: '4px'
                    }}>
                        {am.label}
                    </div>
                    <div style={{ fontSize: '12px', color: C.gray600 }}>
                        {assessment.recommended_action}
                    </div>
                </div>

                <div style={{
                    fontSize: '10px', color: C.gray400,
                    marginTop: '12px', lineHeight: 1.6
                }}>
                    AI-generated assessment. Human review required before disciplinary action.
                    Confidence: {Math.round((assessment.confidence || 0) * 100)}%.
                </div>
            </div>
        </div>
    );
}