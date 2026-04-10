// src/components/GazeHeatmap.js
// 3×3 grid showing where the student looked during exam

import React from 'react';

const REGION_LABELS = {
    TL: 'Top Left', TC: 'Top Centre', TR: 'Top Right',
    CL: 'Left', CENTER: 'Centre', CR: 'Right',
    BL: 'Bot Left', BC: 'Bot Centre', BR: 'Bot Right',
    OFF_SCREEN: 'Off Screen',
};

export default function GazeHeatmap({ gazeData }) {
    if (!gazeData || !gazeData.region_pct) return null;

    const pct = gazeData.region_pct;
    const maxPct = Math.max(...Object.values(pct).filter(v => typeof v === 'number'), 1);

    const GRID = [
        ['TL', 'TC', 'TR'],
        ['CL', 'CENTER', 'CR'],
        ['BL', 'BC', 'BR'],
    ];

    const cellColor = (region) => {
        const p = parseFloat(pct[region] || 0);
        const ratio = p / maxPct;
        // White → blue gradient
        const r = Math.round(255 - ratio * 210);
        const g = Math.round(255 - ratio * 160);
        const b = 255;
        return `rgba(${r},${g},${b},${0.3 + ratio * 0.7})`;
    };

    const offPct = parseFloat(gazeData.off_screen_pct || 0);
    const cornerPct = parseFloat(gazeData.corner_pct || 0);

    return (
        <div>
            <div style={{ fontSize: '10px', fontWeight: 700, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '10px' }}>
                Gaze Distribution
            </div>

            <div style={{ display: 'flex', gap: '20px', alignItems: 'flex-start' }}>
                {/* 3×3 grid */}
                <div>
                    <div style={{ fontSize: '10px', color: '#9ca3af', textAlign: 'center', marginBottom: '4px' }}>
                        Screen view
                    </div>
                    <div style={{
                        display: 'grid', gridTemplateColumns: 'repeat(3,56px)',
                        gridTemplateRows: 'repeat(3,42px)', gap: '2px',
                        border: '1px solid #e2e8f0', borderRadius: '6px', overflow: 'hidden',
                    }}>
                        {GRID.map(row => row.map(region => {
                            const p = parseFloat(pct[region] || 0);
                            return (
                                <div key={region} style={{
                                    background: cellColor(region),
                                    display: 'flex', flexDirection: 'column',
                                    alignItems: 'center', justifyContent: 'center',
                                    fontSize: '9px', lineHeight: 1.3,
                                }}>
                                    <div style={{ fontWeight: 700, color: '#1d4ed8', fontSize: '11px' }}>
                                        {p.toFixed(0)}%
                                    </div>
                                    <div style={{ color: '#6b7280', fontSize: '8px' }}>
                                        {REGION_LABELS[region]}
                                    </div>
                                </div>
                            );
                        }))}
                    </div>
                    <div style={{ fontSize: '9px', color: '#9ca3af', textAlign: 'center', marginTop: '4px' }}>
                        Colour intensity = dwell time
                    </div>
                </div>

                {/* Summary stats */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {[
                        { label: 'Off-screen gaze', value: `${offPct.toFixed(1)}%`, warn: offPct > 25, note: offPct > 25 ? 'Above normal (>25%)' : 'Normal range' },
                        { label: 'Corner gaze', value: `${cornerPct.toFixed(1)}%`, warn: cornerPct > 25, note: cornerPct > 25 ? 'Elevated corner attention' : 'Normal' },
                        { label: 'Dominant region', value: REGION_LABELS[gazeData.dominant_region] || gazeData.dominant_region, warn: false, note: '' },
                    ].map(({ label, value, warn, note }) => (
                        <div key={label} style={{
                            background: warn ? 'var(--warn-lt)' : 'var(--bg3)',
                            border: `1px solid ${warn ? 'var(--warn-bd)' : 'var(--border)'}`,
                            borderRadius: '6px', padding: '8px 10px',
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span style={{ fontSize: '11px', color: '#374151' }}>{label}</span>
                                <span style={{ fontWeight: 700, fontSize: '12px', color: warn ? 'var(--warn)' : '#111' }}>
                                    {value}
                                </span>
                            </div>
                            {note && <div style={{ fontSize: '10px', color: warn ? 'var(--warn)' : '#9ca3af', marginTop: '2px' }}>{note}</div>}
                        </div>
                    ))}

                    {gazeData.suspicion_note && (
                        <div style={{
                            background: 'var(--high-lt)', border: '1px solid var(--high-bd)',
                            borderLeft: '3px solid var(--high)',
                            borderRadius: '6px', padding: '8px 10px',
                            fontSize: '11px', color: 'var(--high)', lineHeight: 1.5,
                        }}>
                            {gazeData.suspicion_note}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}