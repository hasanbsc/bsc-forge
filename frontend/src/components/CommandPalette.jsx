import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Plus, MessageSquare, LayoutGrid, Sun, Moon, MonitorSmartphone,
  LogOut, LogIn, Search,
} from 'lucide-react';

const matches = (text, query) => {
  if (!query) return true;
  return String(text || '').toLowerCase().includes(query.toLowerCase());
};

export default function CommandPalette({
  open,
  onClose,
  // Actions
  onNewSession,
  onSelectSession,
  onStartProduct,
  onViewChange,
  onCycleTheme,
  onLoginClick,
  onLogout,
  // Data
  sessions = [],
  products = [],
  user = null,
  theme = 'auto',
}) {
  const [query, setQuery] = useState('');
  const [selectedIdx, setSelectedIdx] = useState(0);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  const baseActions = useMemo(() => {
    const themeLabels = { auto: 'Otomatik', light: 'Açık', dark: 'Koyu' };
    const themeNextLabel = { auto: 'Açık temaya', light: 'Koyu temaya', dark: 'Otomatik temaya' };
    const ThemeIcon = theme === 'light' ? Sun : theme === 'dark' ? Moon : MonitorSmartphone;
    return [
      {
        id: 'new-session',
        title: 'Yeni sohbet',
        hint: 'Boş bir sohbet aç',
        icon: <Plus size={16} />,
        run: () => onNewSession?.('forge'),
      },
      {
        id: 'go-chat',
        title: 'Sohbete dön',
        hint: 'Ana sohbet ekranı',
        icon: <MessageSquare size={16} />,
        run: () => onViewChange?.('chat'),
      },
      {
        id: 'go-products',
        title: 'Ürünlere git',
        hint: 'Ürün galerisi',
        icon: <LayoutGrid size={16} />,
        run: () => onViewChange?.('products'),
      },
      {
        id: 'cycle-theme',
        title: `Tema: ${themeLabels[theme]}`,
        hint: `${themeNextLabel[theme]} geç`,
        icon: <ThemeIcon size={16} />,
        run: () => onCycleTheme?.(),
      },
      user
        ? {
            id: 'logout',
            title: 'Çıkış yap',
            hint: user.email,
            icon: <LogOut size={16} />,
            run: () => onLogout?.(),
          }
        : {
            id: 'login',
            title: 'Giriş yap / Kayıt ol',
            hint: 'Anonim sohbetler hesabına bağlanır',
            icon: <LogIn size={16} />,
            run: () => onLoginClick?.(),
          },
    ];
  }, [theme, user, onNewSession, onViewChange, onCycleTheme, onLogout, onLoginClick]);

  const items = useMemo(() => {
    const groups = [];
    const actions = baseActions.filter((a) => matches(a.title, query) || matches(a.hint, query));
    if (actions.length) groups.push({ label: 'Komutlar', items: actions });

    const filteredSessions = sessions
      .filter((s) => matches(s.title, query))
      .slice(0, 8)
      .map((s) => ({
        id: `session-${s.id}`,
        title: s.title || 'Adsız sohbet',
        hint: 'Sohbeti aç',
        icon: <MessageSquare size={16} />,
        run: () => onSelectSession?.(s),
      }));
    if (filteredSessions.length) groups.push({ label: 'Sohbetler', items: filteredSessions });

    const filteredProducts = products
      .filter((p) => matches(p.title || p.name, query) || matches(p.id, query))
      .slice(0, 8)
      .map((p) => ({
        id: `product-${p.id}`,
        title: p.title || p.name || p.id,
        hint: 'Ürünü başlat',
        icon: <LayoutGrid size={16} />,
        run: () => onStartProduct?.(p),
      }));
    if (filteredProducts.length) groups.push({ label: 'Ürünler', items: filteredProducts });

    return groups;
  }, [baseActions, sessions, products, query, onSelectSession, onStartProduct]);

  const flatItems = useMemo(() => items.flatMap((g) => g.items), [items]);

  useEffect(() => {
    if (open) {
      setQuery('');
      setSelectedIdx(0);
      setTimeout(() => inputRef.current?.focus(), 0);
    }
  }, [open]);

  useEffect(() => {
    setSelectedIdx(0);
  }, [query]);

  // Klavye gezimi
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose?.();
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIdx((i) => Math.min(i + 1, flatItems.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIdx((i) => Math.max(i - 1, 0));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const item = flatItems[selectedIdx];
        if (item) {
          item.run();
          onClose?.();
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, flatItems, selectedIdx, onClose]);

  // Seçili öğeyi görünür alana kaydır
  useEffect(() => {
    const el = listRef.current?.querySelector('[data-selected="true"]');
    if (el) el.scrollIntoView({ block: 'nearest' });
  }, [selectedIdx]);

  if (!open) return null;

  let idx = -1;
  return (
    <div className="cmdk-overlay" onClick={onClose}>
      <div className="cmdk-panel glass-panel" onClick={(e) => e.stopPropagation()}>
        <div className="cmdk-search">
          <Search size={16} />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Komut, sohbet veya ürün ara…"
            className="cmdk-input"
          />
          <kbd className="cmdk-kbd">Esc</kbd>
        </div>
        <div ref={listRef} className="cmdk-list">
          {items.length === 0 && (
            <div className="cmdk-empty">Eşleşme bulunamadı</div>
          )}
          {items.map((group) => (
            <div key={group.label} className="cmdk-group">
              <div className="cmdk-group-label">{group.label}</div>
              {group.items.map((item) => {
                idx += 1;
                const isSelected = idx === selectedIdx;
                const myIdx = idx;
                return (
                  <button
                    type="button"
                    key={item.id}
                    data-selected={isSelected}
                    className={`cmdk-item ${isSelected ? 'cmdk-item-selected' : ''}`}
                    onMouseEnter={() => setSelectedIdx(myIdx)}
                    onClick={() => { item.run(); onClose?.(); }}
                  >
                    <span className="cmdk-icon">{item.icon}</span>
                    <span className="cmdk-title">{item.title}</span>
                    {item.hint && <span className="cmdk-hint">{item.hint}</span>}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
        <div className="cmdk-footer">
          <span><kbd>↑↓</kbd> gezin</span>
          <span><kbd>↵</kbd> seç</span>
          <span><kbd>Esc</kbd> kapat</span>
        </div>
      </div>
    </div>
  );
}
