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
    const el = document.documentElement;
    el.dataset.colorMode = colorMode;
    // Chakra v3 follows a `light`/`dark` class on the root element — adding it
    // here makes Chakra's own components (Heading, Table, Input, Button) pick
    // the right built-in tokens so their text stays readable in both modes.
    el.classList.remove('light', 'dark');
    el.classList.add(colorMode);
    // Hints to the browser for native form controls + scrollbars.
    el.style.colorScheme = colorMode;
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
