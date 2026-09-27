tailwind.config = {
    darkMode: 'class',
    theme: {
        extend: {
            fontFamily: {
                sans: ['Inter', 'sans-serif'],
                mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
            },
            colors: {
                brand: {
                    dark:         '#0B0F19',
                    bg:           '#0B0F19',
                    surface:      '#111827',
                    surfaceLight: 'rgba(255,255,255,0.04)',
                    panel:        'rgba(11,15,25,0.80)',
                    border:       'rgba(255,255,255,0.08)',
                    neon:         '#10B981',
                    accent:       '#6EE7B7',
                    blue:         '#3B82F6',
                    indigo:       '#6366F1',
                    purple:       '#A78BFA',
                    red:          '#EF4444',
                    gold:         '#F59E0B',
                    amber:        '#FBBF24',
                    silver:       '#CBD5E1',
                }
            },
            boxShadow: {
                'glow-green':  '0 0 15px -3px rgba(16,185,129,0.5)',
                'glow-blue':   '0 0 15px -3px rgba(59,130,246,0.5)',
                'glow-red':    '0 0 15px -3px rgba(239,68,68,0.5)',
                'glow-gold':   '0 0 15px -3px rgba(245,158,11,0.5)',
                'glass':       '0 8px 32px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.06)',
            },
            backdropBlur: {
                xs: '2px',
                sm: '4px',
                md: '12px',
                lg: '20px',
            },
            animation: {
                'pulse-slow':  'pulse 3s cubic-bezier(0.4,0,0.6,1) infinite',
                'spin-slow':   'spin 8s linear infinite',
                'fade-in':     'fadeIn 0.4s ease forwards',
                'slide-up':    'slideUp 0.35s ease forwards',
            },
            keyframes: {
                fadeIn:  { from: { opacity: 0 }, to: { opacity: 1 } },
                slideUp: { from: { opacity: 0, transform: 'translateY(8px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
            },
        }
    }
}
