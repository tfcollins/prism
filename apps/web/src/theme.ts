import { createSystem, defaultConfig } from '@chakra-ui/react';

export const system = createSystem(defaultConfig, {
  globalCss: {
    'html, body': { backgroundColor: '#0f1419', color: '#e2e8f0' },
  },
});
