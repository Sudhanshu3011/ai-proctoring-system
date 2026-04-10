// src/styles/styles.js
// Reusable style objects — import these instead of writing inline styles
// All logic-free: pure presentation objects

import { colors, fonts, radius, shadow, spacing } from './theme';

// ── Layout ────────────────────────────────────────────────────────
export const layout = {
    page: {
        minHeight: '100vh',
        background: colors.gray50,
        fontFamily: fonts.ui,
        color: colors.gray900,
    },
    pageCenter: {
        minHeight: '100vh',
        background: colors.gray50,
        fontFamily: fonts.ui,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: spacing[6],
    },
    container: {
        maxWidth: '880px',
        margin: '0 auto',
        padding: `${spacing[10]} ${spacing[6]}`,
    },
    containerWide: {
        maxWidth: '1100px',
        margin: '0 auto',
        padding: `${spacing[8]} ${spacing[6]}`,
    },
};

// ── Navigation ────────────────────────────────────────────────────
export const nav = {
    root: {
        background: colors.white,
        borderBottom: `1px solid ${colors.gray200}`,
        padding: `0 ${spacing[6]}`,
        height: '56px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'sticky',
        top: 0,
        zIndex: 50,
        boxShadow: shadow.xs,
    },
    brand: {
        display: 'flex',
        alignItems: 'center',
        gap: spacing[3],
    },
    brandLogo: {
        width: '32px',
        height: '32px',
        background: colors.brand,
        borderRadius: radius.md,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexShrink: 0,
    },
    brandName: {
        fontSize: '15px',
        fontWeight: 700,
        color: colors.gray900,
        fontFamily: fonts.display,
        letterSpacing: '-0.02em',
    },
    actions: {
        display: 'flex',
        alignItems: 'center',
        gap: spacing[2],
    },
};

// ── Cards ─────────────────────────────────────────────────────────
export const card = {
    base: {
        background: colors.white,
        border: `1px solid ${colors.gray200}`,
        borderRadius: radius.lg,
        padding: spacing[6],
        boxShadow: shadow.sm,
    },
    compact: {
        background: colors.white,
        border: `1px solid ${colors.gray200}`,
        borderRadius: radius.lg,
        padding: spacing[4],
        boxShadow: shadow.xs,
    },
    elevated: {
        background: colors.white,
        border: `1px solid ${colors.gray200}`,
        borderRadius: radius.xl,
        padding: spacing[6],
        boxShadow: shadow.md,
    },
};

// ── Buttons ───────────────────────────────────────────────────────
export const btn = {
    // Shared base
    _base: {
        fontFamily: fonts.ui,
        fontWeight: 600,
        border: 'none',
        borderRadius: radius.md,
        cursor: 'pointer',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: spacing[2],
        transition: 'all 0.15s ease',
        letterSpacing: '-0.01em',
        lineHeight: 1,
    },
    primary: {
        fontFamily: fonts.ui,
        fontWeight: 600,
        fontSize: '14px',
        border: 'none',
        borderRadius: radius.md,
        cursor: 'pointer',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: spacing[2],
        padding: `10px ${spacing[5]}`,
        background: colors.accent,
        color: colors.white,
        boxShadow: `0 1px 2px rgba(37,99,235,0.2)`,
        letterSpacing: '-0.01em',
    },
    secondary: {
        fontFamily: fonts.ui,
        fontWeight: 500,
        fontSize: '14px',
        border: `1px solid ${colors.gray300}`,
        borderRadius: radius.md,
        cursor: 'pointer',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: spacing[2],
        padding: `9px ${spacing[5]}`,
        background: colors.white,
        color: colors.gray700,
    },
    danger: {
        fontFamily: fonts.ui,
        fontWeight: 600,
        fontSize: '14px',
        border: `1px solid ${colors.dangerBorder}`,
        borderRadius: radius.md,
        cursor: 'pointer',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: spacing[2],
        padding: `9px ${spacing[5]}`,
        background: colors.dangerLight,
        color: colors.dangerMid,
    },
    ghost: {
        fontFamily: fonts.ui,
        fontWeight: 500,
        fontSize: '13px',
        border: 'none',
        borderRadius: radius.md,
        cursor: 'pointer',
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: spacing[2],
        padding: `8px ${spacing[4]}`,
        background: 'transparent',
        color: colors.gray500,
    },
};

// ── Form ──────────────────────────────────────────────────────────
export const form = {
    group: {
        display: 'flex',
        flexDirection: 'column',
        gap: spacing[1],
        marginBottom: spacing[4],
    },
    label: {
        fontSize: '12px',
        fontWeight: 600,
        color: colors.gray600,
        letterSpacing: '0.04em',
        textTransform: 'uppercase',
    },
    input: {
        fontFamily: fonts.ui,
        fontSize: '14px',
        background: colors.white,
        border: `1px solid ${colors.gray300}`,
        borderRadius: radius.md,
        color: colors.gray900,
        padding: `9px ${spacing[3]}`,
        width: '100%',
        outline: 'none',
        transition: 'border-color 0.15s, box-shadow 0.15s',
    },
    select: {
        fontFamily: fonts.ui,
        fontSize: '14px',
        background: colors.white,
        border: `1px solid ${colors.gray300}`,
        borderRadius: radius.md,
        color: colors.gray900,
        padding: `9px ${spacing[3]}`,
        width: '100%',
        outline: 'none',
    },
    error: {
        background: colors.dangerLight,
        border: `1px solid ${colors.dangerBorder}`,
        borderRadius: radius.md,
        padding: `${spacing[3]} ${spacing[4]}`,
        fontSize: '13px',
        color: colors.dangerMid,
        lineHeight: 1.5,
    },
};

// ── Typography ────────────────────────────────────────────────────
export const text = {
    pageTitle: {
        fontFamily: fonts.display,
        fontSize: '26px',
        fontWeight: 400,
        color: colors.gray900,
        letterSpacing: '-0.03em',
        lineHeight: 1.2,
        marginBottom: spacing[1],
    },
    sectionTitle: {
        fontFamily: fonts.ui,
        fontSize: '13px',
        fontWeight: 700,
        color: colors.gray400,
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        marginBottom: spacing[3],
    },
    cardTitle: {
        fontFamily: fonts.display,
        fontSize: '16px',
        fontWeight: 400,
        color: colors.gray900,
        letterSpacing: '-0.02em',
        marginBottom: spacing[1],
    },
    body: {
        fontFamily: fonts.ui,
        fontSize: '14px',
        color: colors.gray600,
        lineHeight: 1.6,
    },
    mono: {
        fontFamily: fonts.mono,
        fontSize: '12px',
        color: colors.gray500,
    },
    caption: {
        fontFamily: fonts.ui,
        fontSize: '11px',
        color: colors.gray400,
        lineHeight: 1.5,
    },
};

// ── Badges / Pills ────────────────────────────────────────────────
export const badge = {
    base: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: '5px',
        padding: `2px 10px`,
        borderRadius: '99px',
        fontSize: '11px',
        fontWeight: 600,
        letterSpacing: '0.02em',
        fontFamily: fonts.ui,
    },
    admin: {
        background: colors.brandLight,
        color: colors.brand,
        border: `1px solid ${colors.brandBorder}`,
    },
    safe: {
        background: colors.successLight,
        color: colors.success,
        border: `1px solid ${colors.successBorder}`,
    },
    warning: {
        background: colors.warningLight,
        color: colors.warning,
        border: `1px solid ${colors.warningBorder}`,
    },
    danger: {
        background: colors.dangerLight,
        color: colors.dangerMid,
        border: `1px solid ${colors.dangerBorder}`,
    },
};

// ── Status bar (monitoring) ───────────────────────────────────────
export const statusPill = (ok) => ({
    display: 'flex',
    alignItems: 'center',
    gap: '5px',
    background: ok ? colors.successLight : colors.dangerLight,
    border: `1px solid ${ok ? colors.successBorder : colors.dangerBorder}`,
    borderRadius: '99px',
    padding: `3px 10px`,
    fontSize: '11px',
    fontWeight: 600,
    color: ok ? colors.success : colors.dangerMid,
    fontFamily: fonts.ui,
});

// ── Tables ────────────────────────────────────────────────────────
export const table = {
    root: {
        width: '100%',
        borderCollapse: 'collapse',
        fontFamily: fonts.ui,
        fontSize: '13px',
    },
    th: {
        padding: `${spacing[2]} ${spacing[4]}`,
        textAlign: 'left',
        fontSize: '11px',
        fontWeight: 700,
        color: colors.gray400,
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        borderBottom: `1px solid ${colors.gray200}`,
        background: colors.gray50,
    },
    td: {
        padding: `${spacing[3]} ${spacing[4]}`,
        color: colors.gray700,
        borderBottom: `1px solid ${colors.gray100}`,
        fontSize: '13px',
    },
};

// ── Modal overlay ─────────────────────────────────────────────────
export const modal = {
    overlay: {
        position: 'fixed',
        inset: 0,
        zIndex: 200,
        background: 'rgba(15,23,42,0.5)',
        backdropFilter: 'blur(2px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: spacing[6],
    },
    panel: {
        background: colors.white,
        borderRadius: radius.xl,
        padding: spacing[8],
        maxWidth: '440px',
        width: '100%',
        boxShadow: shadow.xl,
    },
};

// ── Progress bar ──────────────────────────────────────────────────
export const progress = {
    track: {
        height: '5px',
        background: colors.gray200,
        borderRadius: '99px',
        overflow: 'hidden',
    },
    fill: (pct, color) => ({
        height: '100%',
        width: `${Math.min(100, pct)}%`,
        background: color || colors.accent,
        borderRadius: '99px',
        transition: 'width 0.3s ease',
    }),
};

// ── Divider ───────────────────────────────────────────────────────
export const divider = {
    horizontal: {
        height: '1px',
        background: colors.gray200,
        border: 'none',
        margin: `${spacing[5]} 0`,
    },
};