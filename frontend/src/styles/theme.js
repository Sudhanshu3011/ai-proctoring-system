// src/styles/theme.js
// Single source of truth for all design tokens
// Import this in every component — never hardcode colors or spacing

export const colors = {
    // Brand — slate-blue, institutional, trustworthy
    brand: '#1e3a5f',
    brandMid: '#2d5282',
    brandLight: '#ebf4ff',
    brandBorder: '#bfdbfe',
    accent: '#2563eb',
    accentHov: '#1d4ed8',

    // Neutrals — zinc scale
    white: '#ffffff',
    gray50: '#fafafa',
    gray100: '#f4f4f5',
    gray200: '#e4e4e7',
    gray300: '#d4d4d8',
    gray400: '#a1a1aa',
    gray500: '#71717a',
    gray600: '#52525b',
    gray700: '#3f3f46',
    gray800: '#27272a',
    gray900: '#18181b',

    // Status
    success: '#166534',
    successLight: '#f0fdf4',
    successBorder: '#bbf7d0',
    successMid: '#16a34a',

    warning: '#92400e',
    warningLight: '#fffbeb',
    warningBorder: '#fde68a',
    warningMid: '#d97706',

    danger: '#991b1b',
    dangerLight: '#fff1f2',
    dangerBorder: '#fecdd3',
    dangerMid: '#dc2626',

    critical: '#7f1d1d',
    criticalLight: '#fef2f2',
    criticalBorder: '#fca5a5',
};

export const fonts = {
    display: "'DM Serif Display', Georgia, serif",  // headings — has gravitas
    ui: "'DM Sans', 'Helvetica Neue', sans-serif",  // all UI text
    mono: "'IBM Plex Mono', 'Courier New', monospace", // ids, scores, timers
};

export const radius = {
    sm: '4px',
    md: '8px',
    lg: '12px',
    xl: '16px',
    full: '9999px',
};

export const shadow = {
    xs: '0 1px 2px rgba(0,0,0,0.04)',
    sm: '0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04)',
    md: '0 4px 6px rgba(0,0,0,0.06), 0 2px 4px rgba(0,0,0,0.04)',
    lg: '0 10px 15px rgba(0,0,0,0.08), 0 4px 6px rgba(0,0,0,0.04)',
    xl: '0 20px 25px rgba(0,0,0,0.10), 0 10px 10px rgba(0,0,0,0.04)',
};

export const spacing = {
    '1': '4px',
    '2': '8px',
    '3': '12px',
    '4': '16px',
    '5': '20px',
    '6': '24px',
    '8': '32px',
    '10': '40px',
    '12': '48px',
    '16': '64px',
};

// Status badge config — used across risk levels
export const statusConfig = {
    SAFE: { color: colors.success, bg: colors.successLight, border: colors.successBorder, label: 'Safe' },
    WARNING: { color: colors.warningMid, bg: colors.warningLight, border: colors.warningBorder, label: 'Warning' },
    HIGH: { color: colors.dangerMid, bg: colors.dangerLight, border: colors.dangerBorder, label: 'High Risk' },
    CRITICAL: { color: colors.critical, bg: colors.criticalLight, border: colors.criticalBorder, label: 'Critical' },
};