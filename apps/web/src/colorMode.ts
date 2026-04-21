import { createContext, useContext } from 'react';

export type ColorMode = 'light' | 'dark';

export interface ColorModeContextValue {
  colorMode: ColorMode;
  setColorMode: (m: ColorMode) => void;
  toggleColorMode: () => void;
}

export const ColorModeContext = createContext<ColorModeContextValue | null>(null);

export function useColorMode(): ColorModeContextValue {
  const ctx = useContext(ColorModeContext);
  if (!ctx) throw new Error('useColorMode must be used inside ColorModeProvider');
  return ctx;
}
