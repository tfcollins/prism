import { useEffect, useState, type ReactNode } from 'react';

import { ColorModeContext, type ColorMode } from './colorMode';

const STORAGE_KEY = 'prism-color-mode';

function initialColorMode(): ColorMode {
  if (typeof window === 'undefined') return 'dark';
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === 'light' || stored === 'dark') return stored;
  return window.matchMedia?.('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

export function ColorModeProvider({ children }: { children: ReactNode }) {
  const [colorMode, setState] = useState<ColorMode>(initialColorMode);

  useEffect(() => {
    document.documentElement.dataset.colorMode = colorMode;
  }, [colorMode]);

  const setColorMode = (m: ColorMode) => {
    window.localStorage.setItem(STORAGE_KEY, m);
    setState(m);
  };
  const toggleColorMode = () => setColorMode(colorMode === 'light' ? 'dark' : 'light');

  return (
    <ColorModeContext.Provider value={{ colorMode, setColorMode, toggleColorMode }}>
      {children}
    </ColorModeContext.Provider>
  );
}
