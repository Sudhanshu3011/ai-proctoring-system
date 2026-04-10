// src/components/IntegrityReport.js
// Shows the ML integrity assessment at bottom of report page

import React from 'react';

const VERDICT_META = {
    LIKELY_HONEST: { color: '#059669', bg: '#ecfdf5', border: '#a7f3d0', label: 'Likely Honest', icon: '✓' },
    SUSPICIOUS: { color: '#d97706', bg: '#fffbeb', border: '#fcd34d', label: 'Suspicious', icon: '?' },
    LIKELY_CHEATING: { color: '#dc2626', bg: '#fef2f2', border: '#fca5a5', label: 'Likely Cheating', icon: '!' },
    CONFIRMED_CHEATING: { color: '#991b1b', bg: '#fef2f2', border: '#f87171', label: 'Confirmed Cheating', icon: '✗' },
};

const ACTION_META = {
    REVIEW: { color: '#059669', label: 'No Action Required' },
    INVESTIGATE: { color: '#d97706', label: 'Manual Review Required' },
    ESCALATE: { color: '#dc2626', label: 'Escalate to Department' },
    INVALIDATE: { color: '#991b1b', label: 'Invalidate Exam Result' },
};

const CATEGORY_META = {
    IDENTITY: { color: '#7c3aed', bg: '#f5f3ff' },
    ATTENTION: { color: '#0891b2', bg: '#ecfeff' },
    OBJECTS: { color: '#dc2626', bg: '#fef2f2' },
    AUDIO: { color: '#d97706', bg: '#fffbeb' },
    BROWSER: { color: '#374151', bg: '#f9fafb' },
    LIVENESS: { color: '#059669', bg: '#ecfdf5' },
    BEHAVIOUR: { color: '#6b7280', bg: '#f3f4f6' },
};

function ProbabilityBar({ value }) {
    const pct = Math.round(value * 100);
    const col = value < 0.25 ? '#059669' : value < 0.55 ? '#d97706' : value < 0.80 ? '#dc2626' : '#991b1b';
    return (
        <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#6b7280', marginBottom: '4px' }}>
                <span>Cheating probability</span>
                <span style={{ fontWeight: 700, color: col }}>{pct}%</span>
            </div>
            <div style={{ height: 8, background: '#f1f5f9', borderRadius: 4, overflow: 'hidden' }}>
                {/* Coloured segments */}
                <div style={{ display: 'flex', height: '100%' }}>
                    <div style={{ width: '25%', background: '#059669', opacity: 0.25, borderRight: '1px solid #fff' }} />
                    <div style={{ width: '30%', background: '#d97706', opacity: 0.25, borderRight: '1px solid #fff' }} />
                    <div style={{ width: '25%', background: '#dc2626', opacity: 0.25, borderRight: '1px solid #fff' }} />
                    <div style={{ width: '20%', background: '#991b1b', opacity: 0.25 }} />
                </div>
            </div>
            {/* Needle */}
            <div style={{ position: 'relative', height: 0, marginTop: '-4px' }}>
                <div style={{
                    position: 'absolute', left: `${pct}%`,
                    transform: 'translateX(-50%)',
                    width: 3, height: 12, background: col,
                    borderRadius: 2, marginTop: '-12px',
                }} />
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '9px', color: '#9ca3af', marginTop: '6px' }}>
                <span>Low</span><span>Medium</span><span>High</span><span>Very High</span>
            </div>
        </div>
    );
}

export default function IntegrityReport({ assessment }) {
    if (!assessment) return null;

    const vm = VERDICT_META[assessment.verdict] || VERDICT_META.SUSPICIOUS;
    const am = ACTION_META[assessment.action_priority] || ACTION_META.REVIEW;

    return (
        <div style={{
            background: 'var(--bg2)', border: `1px solid ${vm.border}`,
            borderRadius: '10px', overflow: 'hidden',
            marginTop: '16px',
        }}>
            {/* Header */}
            <div style={{ background: vm.bg, padding: '16px 20px', borderBottom: `1px solid ${vm.border}` }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                    <div style={{
                        width: 48, height: 48, borderRadius: '50%',
                        background: vm.color, display: 'flex', alignItems: 'center',
                        justifyContent: 'center', color: '#fff', fontSize: '20px', fontWeight: 800, flexShrink: 0,
                    }}>
                        {vm.icon}
                    </div>
                    <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 700, fontSize: '16px', color: '#111', marginBottom: '2px' }}>
                            AI Integrity Assessment
                        </div>
                        <div style={{ fontWeight: 700, fontSize: '14px', color: vm.color }}>
                            {vm.label}
                        </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: '28px', fontWeight: 800, color: vm.color, lineHeight: 1 }}>
                            {assessment.integrity_score.toFixed(0)}
                        </div>
                        <div style={{ fontSize: '11px', color: '#6b7280' }}>Integrity / 100</div>
                    </div>
                </div>
            </div>

            <div style={{ padding: '16px 20px' }}>

                {/* Probability bar */}
                <div style={{ marginBottom: '16px' }}>
                    <ProbabilityBar value={assessment.cheat_probability} />
                </div>

                {/* Stats row */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: '10px', marginBottom: '16px' }}>
                    {[
                        { l: 'Confidence', v: `${Math.round(assessment.confidence * 100)}%`, c: '#374151' },
                        { l: 'Violations', v: assessment.total_violations, c: '#374151' },
                        { l: 'Duration', v: `${assessment.exam_duration_min.toFixed(0)}m`, c: '#374151' },
                    ].map(({ l, v, c }) => (
                        <div key={l} style={{
                            background: 'var(--bg3)', border: '1px solid var(--border)',
                            borderRadius: '7px', padding: '10px', textAlign: 'center',
                        }}>
                            <div style={{ fontWeight: 700, fontSize: '18px', color: c }}>{v}</div>
                            <div style={{ fontSize: '10px', color: '#6b7280', marginTop: '2px' }}>{l}</div>
                        </div>
                    ))}
                </div>

                {/* Evidence findings */}
                {assessment.findings?.length > 0 && (
                    <div style={{ marginBottom: '14px' }}>
                        <div style={{ fontSize: '10px', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
                            Evidence
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                            {assessment.findings.map((f, i) => {
                                const cm = CATEGORY_META[f.category] || CATEGORY_META.BEHAVIOUR;
                                return (
                                    <div key={i} style={{
                                        background: 'var(--bg3)', border: '1px solid var(--border)',
                                        borderRadius: '7px', padding: '10px 12px',
                                        display: 'flex', gap: '10px', alignItems: 'flex-start',
                                    }}>
                                        <div style={{
                                            background: cm.bg, color: cm.color,
                                            borderRadius: '5px', padding: '2px 8px',
                                            fontSize: '9px', fontWeight: 700, textTransform: 'uppercase',
                                            letterSpacing: '0.04em', flexShrink: 0, marginTop: '1px',
                                        }}>
                                            {f.category}
                                        </div>
                                        <div style={{ flex: 1 }}>
                                            <div style={{ fontSize: '12px', fontWeight: 600, color: '#111', marginBottom: '2px' }}>
                                                {f.finding}
                                            </div>
                                            {f.evidence && (
                                                <div style={{ fontSize: '11px', color: '#6b7280' }}>{f.evidence}</div>
                                            )}
                                        </div>
                                        <div style={{
                                            fontSize: '10px', fontWeight: 700,
                                            color: f.weight > 20 ? 'var(--high)' : f.weight > 10 ? 'var(--warn)' : 'var(--muted)',
                                            flexShrink: 0,
                                        }}>
                                            -{f.weight.toFixed(0)}pts
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}

                {/* Recommended action */}
                <div style={{
                    background: `${am.color}15`,
                    border: `1px solid ${am.color}40`,
                    borderLeft: `3px solid ${am.color}`,
                    borderRadius: '7px', padding: '12px 14px',
                }}>
                    <div style={{ fontSize: '10px', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>
                        Recommended Action
                    </div>
                    <div style={{ fontWeight: 700, fontSize: '13px', color: am.color, marginBottom: '3px' }}>
                        {am.label}
                    </div>
                    <div style={{ fontSize: '12px', color: '#374151' }}>
                        {assessment.recommended_action}
                    </div>
                </div>

                <div style={{ fontSize: '10px', color: '#9ca3af', marginTop: '12px', lineHeight: 1.5 }}>
                    This assessment is generated by AI and should be reviewed by a human invigilator
                    before any disciplinary action is taken. Confidence: {Math.round(assessment.confidence * 100)}%.
                </div>
            </div>
        </div>
    );
}