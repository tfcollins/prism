import { createSystem, defaultConfig } from '@chakra-ui/react';

// Design tokens are declared as CSS custom properties so individual components
// can reference them with plain `var(--prism-…)` strings (works everywhere —
// inline styles, Chakra props, Plotly layouts, etc.). Values swap when the
// top-level `[data-color-mode]` attribute changes.
export const system = createSystem(defaultConfig, {
  globalCss: {
    ':root': {
      '--prism-bg-canvas': '#0f1419',
      '--prism-bg-surface': '#171923',
      '--prism-bg-plot': '#0a0e13',
      '--prism-bg-hover': '#1a2438',
      '--prism-bg-sel': '#1e3a5f',
      '--prism-border': '#2d3748',
      '--prism-border-strong': '#4a5568',
      '--prism-text': '#e2e8f0',
      '--prism-text-muted': '#cbd5e0',
      '--prism-text-subtle': '#a0aec0',
      '--prism-text-faint': '#4a5568',
      '--prism-brand': '#63b3ed',
      '--prism-brand-strong': '#3182ce',
      '--prism-danger-bg': '#2d1a1a',
      '--prism-sidebar-active-bg': '#2d3748',
      '--prism-sidebar-active-fg': '#ffffff',
    },
    ':root[data-color-mode="light"]': {
      '--prism-bg-canvas': '#f7fafc',
      '--prism-bg-surface': '#ffffff',
      '--prism-bg-plot': '#f7fafc',
      '--prism-bg-hover': '#edf2f7',
      '--prism-bg-sel': '#bee3f8',
      '--prism-border': '#e2e8f0',
      '--prism-border-strong': '#cbd5e0',
      '--prism-text': '#1a202c',
      '--prism-text-muted': '#2d3748',
      '--prism-text-subtle': '#4a5568',
      '--prism-text-faint': '#a0aec0',
      '--prism-brand': '#2b6cb0',
      '--prism-brand-strong': '#2c5282',
      '--prism-danger-bg': '#fff5f5',
      '--prism-sidebar-active-bg': '#bee3f8',
      '--prism-sidebar-active-fg': '#1a365d',
    },

    'html, body': {
      backgroundColor: 'var(--prism-bg-canvas)',
      color: 'var(--prism-text)',
    },

    // Tabs: force readable inactive/active colors in both modes
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

    // Outline-variant buttons
    'button.chakra-button[data-variant="outline"], button[data-variant="outline"]': {
      borderColor: 'var(--prism-border-strong)',
      color: 'var(--prism-text)',
    },
    'button.chakra-button[data-variant="outline"]:hover, button[data-variant="outline"]:hover': {
      borderColor: 'var(--prism-text-subtle)',
      backgroundColor: 'var(--prism-bg-hover)',
    },

    // Checkbox border
    '[data-scope="checkbox"][data-part="control"]': {
      borderColor: 'var(--prism-border-strong)',
    },
  },
});
