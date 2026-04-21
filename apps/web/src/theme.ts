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
      '--prism-bg-plot': '#030712',
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
      '--prism-sidebar-active-bg': '#1e40af',
      '--prism-sidebar-active-fg': '#eff6ff',
    },
    ':root[data-color-mode="light"]': {
      '--prism-bg-canvas': '#f9fafb',
      '--prism-bg-surface': '#ffffff',
      '--prism-bg-plot': '#f3f4f6',
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
      '--prism-sidebar-active-bg': '#dbeafe',
      '--prism-sidebar-active-fg': '#1e3a8a',
    },

    'html, body': {
      backgroundColor: 'var(--prism-bg-canvas)',
      color: 'var(--prism-text)',
    },

    // Force Chakra-composed components to adopt our foreground when they'd
    // otherwise use a Chakra default that doesn't swap.
    '.chakra-heading': { color: 'var(--prism-text)' },
    '.chakra-table__row > .chakra-table__cell, .chakra-table__row > .chakra-table__header': {
      color: 'var(--prism-text)',
      borderColor: 'var(--prism-border)',
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
});
