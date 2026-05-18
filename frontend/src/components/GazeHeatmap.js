import React from 'react';

const C = {
    navy: '#1e3a5f',
    navyMid: '#2d5282',
    orange: '#ea580c',
    orangeLt: '#fff7ed',
    orangeBd: '#fed7aa',
    white: '#ffffff',
    gray50: '#fafafa',
    gray100: '#f4f4f5',
    gray200: '#e4e4e7',
    gray400: '#a1a1aa',
    gray500: '#71717a',
    gray700: '#3f3f46',
    gray900: '#18181b',
    safe: '#059669',
    safeLt: '#ecfdf5',
    warn: '#d97706',
    warnLt: '#fffbeb',
};

const REGION_LABELS = {
    TL: 'Top-Left', TC: 'Top-Centre', TR: 'Top-Right',
    CL: 'Left', CENTER: 'Centre', CR: 'Right',
    BL: 'Bot-Left', BC: 'Bot-Centre', BR: 'Bot-Right',
};
const GRID = [
    ['TL', 'TC', 'TR'],
    ['CL', 'CENTER', 'CR'],
    ['BL', 'BC', 'BR'],
];
const CORNERS = new Set(['TL', 'TR', 'BL', 'BR']);

export default function GazeHeatmap({ gazeData }) {
    if (!gazeData || !gazeData.region_pct) return null;

    const pct = gazeData.region_pct || {};
    const maxPct = Math.max(...Object.values(pct).filter(v => typeof v === 'number'), 1);

    const cellBg = (region) => {
        const p = parseFloat(pct[region] || 0);
        const ratio = p / maxPct;
        // Navy-tinted heat: low → gray50, high → navy
        const r = Math.round(250 - ratio * 220);
        const g = Math.round(250 - ratio * 160);
        const b = Math.round(250 - ratio * 100);
        return `rgba(${r},${g},${b},${0.25 + ratio * 0.75})`;
    };

    const offPct = parseFloat(gazeData.off_screen_pct || 0);
    const cornerPct = parseFloat(gazeData.corner_pct || 0);
    const dominant = gazeData.dominant_region || 'CENTER';
    const suspicious = gazeData.suspicion_note || '';

    return (
        <div>
            <div style={{
                fontSize: '11px', fontWeight: 700, color: C.gray400,
                textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '14px'
            }}>
                Gaze Distribution
            </div>

            <div style={{ display: 'flex', gap: '24px', alignItems: 'flex-start', flexWrap: 'wrap' }}>

                {/* 3×3 heatmap grid */}
                <div style={{ flexShrink: 0 }}>
                    <div style={{
                        fontSize: '10px', color: C.gray400, textAlign: 'center',
                        marginBottom: '6px', letterSpacing: '0.04em'
                    }}>
                        Screen regions — dwell %
                    </div>
                    <div style={{
                        display: 'grid', gridTemplateColumns: 'repeat(3,62px)',
                        gridTemplateRows: 'repeat(3,48px)', gap: '2px',
                        border: `1px solid ${C.gray200}`, borderRadius: '8px', overflow: 'hidden'
                    }}>
                        {GRID.map(row => row.map(region => {
                            const p = parseFloat(pct[region] || 0);
                            const isHot = p >= maxPct * 0.7;
                            const isDom = region === dominant;
                            return (
                                <div key={region} style={{
                                    background: cellBg(region),
                                    display: 'flex', flexDirection: 'column',
                                    alignItems: 'center', justifyContent: 'center',
                                    outline: isDom ? `2px solid ${C.orange}` : 'none',
                                    outlineOffset: '-2px',
                                    position: 'relative',
                                }}>
                                    <div style={{
                                        fontFamily: 'IBM Plex Mono, monospace',
                                        fontSize: '13px', fontWeight: 700,
                                        color: isHot ? C.white : C.navy,
                                    }}>
                                        {p.toFixed(0)}%
                                    </div>
                                    <div style={{
                                        fontSize: '8px', color: isHot ? 'rgba(255,255,255,0.85)' : C.gray500,
                                        letterSpacing: '0.02em',
                                    }}>
                                        {REGION_LABELS[region]}
                                    </div>
                                    {CORNERS.has(region) && p > 20 && (
                                        <div style={{
                                            position: 'absolute', top: 2, right: 3,
                                            width: 6, height: 6, borderRadius: '50%',
                                            background: C.orange,
                                        }} />
                                    )}
                                </div>
                            );
                        }))}
                    </div>
                    <div style={{
                        fontSize: '9px', color: C.gray400, textAlign: 'center',
                        marginTop: '6px'
                    }}>
                        ◆ Orange dot = elevated corner attention
                    </div>
                </div>

                {/* Stats column */}
                <div style={{ flex: 1, minWidth: '180px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {[
                        {
                            label: 'Off-screen gaze',
                            value: `${offPct.toFixed(1)}%`,
                            warn: offPct > 25,
                            note: offPct > 25 ? `Above threshold (>25%)` : 'Normal (<25%)',
                        },
                        {
                            label: 'Corner gaze',
                            value: `${cornerPct.toFixed(1)}%`,
                            warn: cornerPct > 25,
                            note: cornerPct > 25 ? 'Elevated — possible peripheral notes' : 'Normal',
                        },
                        {
                            label: 'Dominant region',
                            value: REGION_LABELS[dominant] || dominant,
                            warn: false,
                            note: '',
                        },
                    ].map(({ label, value, warn, note }) => (
                        <div key={label} style={{
                            background: warn ? C.orangeLt : C.gray50,
                            border: `1px solid ${warn ? C.orangeBd : C.gray200}`,
                            borderLeft: `3px solid ${warn ? C.orange : C.gray200}`,
                            borderRadius: '7px', padding: '8px 12px',
                        }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <span style={{ fontSize: '12px', color: C.gray700 }}>{label}</span>
                                <span style={{
                                    fontWeight: 700, fontSize: '13px',
                                    color: warn ? C.orange : C.gray900,
                                    fontFamily: 'IBM Plex Mono, monospace'
                                }}>
                                    {value}
                                </span>
                            </div>
                            {note && (
                                <div style={{
                                    fontSize: '10px', color: warn ? C.orange : C.gray400,
                                    marginTop: '2px'
                                }}>
                                    {note}
                                </div>
                            )}
                        </div>
                    ))}

                    {suspicious && (
                        <div style={{
                            background: '#fff7ed',
                            border: `1px solid ${C.orangeBd}`,
                            borderLeft: `3px solid ${C.orange}`,
                            borderRadius: '7px', padding: '10px 12px',
                            fontSize: '11px', color: C.orange, lineHeight: 1.6,
                        }}>
                            <strong>⚠ Suspicion:</strong> {suspicious}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}