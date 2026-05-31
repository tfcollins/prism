import { createSystem, defaultConfig } from '@chakra-ui/react';

// Design tokens are declared as CSS custom properties and selected via the
// top-level `[data-color-mode]` attribute so every component can reference
// them with plain `var(--prism-…)` strings. Chakra's own built-in tokens flip
// separately — the `.dark` / `.light` class that ColorModeProvider adds does
// that — so Chakra-styled components (Heading, Table, Input) stay readable.
//
// Values are picked from Tailwind's palette for tested-against-each-other
// contrast ratios (every body text <-> canvas pair is ≥ 7:1, secondary/
// muted text is ≥ 4.5:1, faint decorative text is ~3:1).
export const system = createSystem(defaultConfig, {
  globalCss: {
    ':root': {
      '--prism-bg-canvas': '#0b1220',
      '--prism-bg-surface': '#111827',
      '--prism-bg-plot': '#04060c',
      '--prism-bg-hover': '#1f2937',
      '--prism-bg-sel': '#1e40af',
      '--prism-border': '#374151',
      '--prism-border-strong': '#4b5563',
      '--prism-text': '#f9fafb',
      '--prism-text-muted': '#e5e7eb',
      '--prism-text-subtle': '#cbd5e0',
      '--prism-text-faint': '#9ca3af',
      '--prism-brand': '#60a5fa',
      '--prism-brand-strong': '#3b82f6',
      '--prism-danger-bg': '#450a0a',
      '--prism-danger-fg': '#fecaca',
      // Active rail item: a translucent brand wash (was a heavy solid block).
      // The saturated cue is carried by a spectral left bar in the Sidebar.
      '--prism-sidebar-active-bg': 'rgba(96, 165, 250, 0.12)',
      '--prism-sidebar-active-fg': '#dbeafe',
      // Semantic status tokens (pass / warn / fail). Reused by margin chips,
      // case-status badges, and trend spec lines so status reads identically
      // across the app. Paired with glyphs in UI so hue is never the sole signal.
      '--prism-status-pass-bg': '#052e16',
      '--prism-status-pass-fg': '#86efac',
      '--prism-status-warn-bg': '#422006',
      '--prism-status-warn-fg': '#fcd34d',
      '--prism-status-fail-bg': '#450a0a',
      '--prism-status-fail-fg': '#fca5a5',
      // Card elevation + signature value glow (dark).
      '--prism-shadow-card':
        '0 1px 0 rgba(255,255,255,0.03) inset, 0 12px 28px -18px rgba(0,0,0,0.85)',
      '--prism-glow-brand': '0 0 22px -8px var(--prism-brand)',
      // Atmosphere: a faint spectral bloom anchored top-left of the canvas.
      '--prism-canvas-glow':
        'radial-gradient(900px 500px at 12% -8%, rgba(96,165,250,0.10), transparent 60%), radial-gradient(700px 460px at 92% -12%, rgba(167,139,250,0.07), transparent 55%)',
    },
    ':root[data-color-mode="light"]': {
      '--prism-bg-canvas': '#f9fafb',
      '--prism-bg-surface': '#ffffff',
      '--prism-bg-plot': '#0c1322',
      '--prism-bg-hover': '#f3f4f6',
      '--prism-bg-sel': '#dbeafe',
      '--prism-border': '#e5e7eb',
      '--prism-border-strong': '#d1d5db',
      '--prism-text': '#111827',
      '--prism-text-muted': '#1f2937',
      '--prism-text-subtle': '#374151',
      '--prism-text-faint': '#6b7280',
      '--prism-brand': '#2563eb',
      '--prism-brand-strong': '#1d4ed8',
      '--prism-danger-bg': '#fee2e2',
      '--prism-danger-fg': '#991b1b',
      '--prism-sidebar-active-bg': 'rgba(37, 99, 235, 0.10)',
      '--prism-sidebar-active-fg': '#1e3a8a',
      '--prism-status-pass-bg': '#dcfce7',
      '--prism-status-pass-fg': '#166534',
      '--prism-status-warn-bg': '#fef3c7',
      '--prism-status-warn-fg': '#92400e',
      '--prism-status-fail-bg': '#fee2e2',
      '--prism-status-fail-fg': '#991b1b',
      '--prism-shadow-card': '0 1px 2px rgba(16,24,40,0.06), 0 12px 28px -20px rgba(16,24,40,0.22)',
      '--prism-glow-brand': '0 0 0 transparent',
      '--prism-canvas-glow':
        'radial-gradient(900px 500px at 12% -8%, rgba(37,99,235,0.05), transparent 60%)',
    },

    // Spectral ramp — the "Prism" refraction signature. Mode-independent hues
    // (they read on both canvases); used for the shell hairline, sidebar active
    // bar, and as a saturated accent. The gradient is the brand's one bold move.
    ':root, :root[data-color-mode="light"]': {
      '--prism-spectrum-r': '#f87171',
      '--prism-spectrum-o': '#fb923c',
      '--prism-spectrum-y': '#fbbf24',
      '--prism-spectrum-g': '#34d399',
      '--prism-spectrum-c': '#22d3ee',
      '--prism-spectrum-b': '#60a5fa',
      '--prism-spectrum-v': '#a78bfa',
      '--prism-spectrum-gradient':
        'linear-gradient(90deg, #f87171, #fb923c, #fbbf24, #34d399, #22d3ee, #60a5fa, #a78bfa)',
      '--prism-font-sans': "'IBM Plex Sans', ui-sans-serif, system-ui, -apple-system, sans-serif",
      '--prism-font-mono': "'IBM Plex Mono', ui-monospace, 'SF Mono', Menlo, monospace",
    },

    'html, body': {
      backgroundColor: 'var(--prism-bg-canvas)',
      backgroundImage: 'var(--prism-canvas-glow)',
      backgroundAttachment: 'fixed',
      color: 'var(--prism-text)',
      fontFamily: 'var(--prism-font-sans)',
    },

    // Headings: same family, tightened tracking for an engineered look.
    '.chakra-heading, h1, h2, h3, h4': {
      fontFamily: 'var(--prism-font-sans)',
      letterSpacing: '-0.015em',
    },

    // Numerics readout: tabular mono. Applied to metrics, run ids, counts.
    '.prism-num': {
      fontFamily: 'var(--prism-font-mono)',
      fontVariantNumeric: 'tabular-nums',
      letterSpacing: '-0.01em',
    },

    // Force Chakra-composed components to adopt our foreground when they'd
    // otherwise use a Chakra default that doesn't swap.
    '.chakra-heading': { color: 'var(--prism-text)' },
    '.chakra-table__row > .chakra-table__cell, .chakra-table__row > .chakra-table__header': {
      color: 'var(--prism-text)',
      borderColor: 'var(--prism-border)',
    },
    // Column headers read like an instrument channel legend.
    '.chakra-table__row > .chakra-table__header': {
      textTransform: 'uppercase',
      fontSize: '10.5px',
      letterSpacing: '0.08em',
      fontWeight: '600',
      fontFamily: 'var(--prism-font-mono)',
      color: 'var(--prism-text-faint)',
    },
    '.chakra-input, input.chakra-input, .chakra-textarea': {
      color: 'var(--prism-text)',
      borderColor: 'var(--prism-border-strong)',
      backgroundColor: 'var(--prism-bg-surface)',
    },
    '.chakra-input::placeholder': {
      color: 'var(--prism-text-faint)',
    },

    // Tabs: force readable inactive/active colors in both modes.
    '[role="tab"]': {
      color: 'var(--prism-text-muted)',
      fontWeight: '500',
    },
    '[role="tab"][data-state="active"], [role="tab"][aria-selected="true"]': {
      color: 'var(--prism-brand)',
      fontWeight: '600',
    },
    '[role="tab"]:hover:not([data-state="active"]):not([aria-selected="true"])': {
      color: 'var(--prism-text)',
    },

    // Outline-variant buttons (e.g. TopBar actions).
    'button.chakra-button[data-variant="outline"], button[data-variant="outline"]': {
      borderColor: 'var(--prism-border-strong)',
      color: 'var(--prism-text)',
    },
    'button.chakra-button[data-variant="outline"]:hover, button[data-variant="outline"]:hover': {
      borderColor: 'var(--prism-text-subtle)',
      backgroundColor: 'var(--prism-bg-hover)',
    },

    // Checkbox border.
    '[data-scope="checkbox"][data-part="control"]': {
      borderColor: 'var(--prism-border-strong)',
    },
  },
  theme: {
    tokens: {
      // Make Chakra's own font tokens resolve to our self-hosted IBM Plex faces,
      // so every `fontFamily="mono"` / heading / body across the app picks up
      // the instrument typography without per-call edits.
      fonts: {
        body: { value: "'IBM Plex Sans', ui-sans-serif, system-ui, -apple-system, sans-serif" },
        heading: { value: "'IBM Plex Sans', ui-sans-serif, system-ui, -apple-system, sans-serif" },
        mono: { value: "'IBM Plex Mono', ui-monospace, 'SF Mono', Menlo, monospace" },
      },
    },
    keyframes: {
      // Shimmer for loading skeletons (PlotSkeleton).
      'prism-shimmer': {
        '0%': { backgroundPosition: '200% 0' },
        '100%': { backgroundPosition: '-200% 0' },
      },
    },
  },
});
