import { createSystem, defaultConfig } from '@chakra-ui/react';

export const system = createSystem(defaultConfig, {
  globalCss: {
    'html, body': { backgroundColor: '#0f1419', color: '#e2e8f0' },

    // Tabs: Chakra v3's default inactive-tab text color is too dark against our
    // dark-theme bg. Give inactive tabs a readable gray and keep active tabs
    // visually distinct with brand cyan + bold weight.
    '[role="tab"]': {
      color: '#cbd5e0',
      fontWeight: '500',
    },
    '[role="tab"][data-state="active"], [role="tab"][aria-selected="true"]': {
      color: '#63b3ed',
      fontWeight: '600',
    },
    '[role="tab"]:hover:not([data-state="active"]):not([aria-selected="true"])': {
      color: '#ffffff',
    },

    // Outline-variant buttons (e.g. TopBar "Sign out"): Chakra's default
    // border is too low-contrast on our dark bg — raise both border and text
    // so the button is legible without shouting.
    'button.chakra-button[data-variant="outline"], button[data-variant="outline"]': {
      borderColor: '#4a5568',
      color: '#e2e8f0',
    },
    'button.chakra-button[data-variant="outline"]:hover, button[data-variant="outline"]:hover': {
      borderColor: '#718096',
      backgroundColor: 'rgba(255,255,255,0.04)',
    },

    // Checkbox default border is almost invisible on the dark table bg. Raise
    // the unchecked border; checked state already has its own (blue) color.
    '[data-scope="checkbox"][data-part="control"]': {
      borderColor: '#4a5568',
    },
  },
});
