// BSC Forge — Tema servisi
//
// Tema değerleri: 'auto' | 'light' | 'dark'
// 'auto' = sistemden algıla (prefers-color-scheme)

const THEME_KEY = 'bsc.theme';
const VALID = ['auto', 'light', 'dark'];

export const getStoredTheme = () => {
  try {
    const t = localStorage.getItem(THEME_KEY);
    return VALID.includes(t) ? t : 'auto';
  } catch {
    return 'auto';
  }
};

export const setStoredTheme = (theme) => {
  if (!VALID.includes(theme)) return;
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    /* yok say */
  }
};

export const applyTheme = (theme) => {
  if (!VALID.includes(theme)) theme = 'auto';
  document.documentElement.setAttribute('data-theme', theme);
};

export const cycleTheme = (current) => {
  const idx = VALID.indexOf(current);
  return VALID[(idx + 1) % VALID.length];
};

export const THEME_LABELS = {
  auto: 'Otomatik',
  light: 'Açık',
  dark: 'Koyu',
};
