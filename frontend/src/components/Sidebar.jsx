import React from 'react';
import {
  Plus, MessageSquare, Trash2, LayoutGrid, LogIn, LogOut,
  Sun, Moon, MonitorSmartphone, Pin, PinOff,
} from 'lucide-react';

const THEME_NEXT_LABEL = {
  auto: 'Açık temaya geç',
  light: 'Koyu temaya geç',
  dark: 'Otomatik temaya geç',
};

function ThemeIcon({ theme, size = 15 }) {
  if (theme === 'light') return <Sun size={size} />;
  if (theme === 'dark') return <Moon size={size} />;
  return <MonitorSmartphone size={size} />;
}

export default function Sidebar({
  sessions,
  currentSession,
  isOpen,
  onClose,
  onSelectSession,
  onNewSession,
  onDeleteSession,
  view,
  onViewChange,
  user,
  onLoginClick,
  onLogout,
  theme = 'auto',
  onCycleTheme,
  onTogglePin,
}) {
  const userInitial = user?.email ? user.email[0].toUpperCase() : '?';
  const pinnedSessions = sessions.filter((s) => s.pinned);
  const otherSessions = sessions.filter((s) => !s.pinned);

  const renderSession = (session) => (
    <div
      key={session.id}
      className={`session-item ${currentSession?.id === session.id ? 'active' : ''}`}
      onClick={() => onSelectSession(session)}
    >
      <MessageSquare size={16} className="session-item-icon" />
      <div className="session-item-text">{session.title}</div>
      <div className="session-item-actions">
        <button
          type="button"
          className="session-action-btn"
          title={session.pinned ? 'Pinden çıkar' : 'Pinle'}
          aria-label={session.pinned ? 'Pinden çıkar' : 'Pinle'}
          onClick={(e) => {
            e.stopPropagation();
            onTogglePin?.(session);
          }}
        >
          {session.pinned ? <PinOff size={14} /> : <Pin size={14} />}
        </button>
        <button
          type="button"
          className="session-action-btn session-delete-btn"
          title="Sohbeti sil"
          aria-label={`${session.title} sohbetini sil`}
          onClick={(e) => {
            e.stopPropagation();
            onDeleteSession(session);
          }}
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
  );
  return (
    <div className={`sidebar ${isOpen ? 'open' : ''}`}>
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="sidebar-logo-icon">⚒</div>
          <div>
            <div className="sidebar-logo-text">BSC Forge</div>
            <div className="sidebar-logo-version">v0.1.0 Beta</div>
          </div>
        </div>
        <button className="new-chat-btn" onClick={onNewSession}>
          <Plus size={16} /> Yeni Sohbet
        </button>
      </div>

      <div className="sidebar-nav">
        <button
          className={`sidebar-nav-btn ${view === 'chat' ? 'active' : ''}`}
          onClick={() => onViewChange('chat')}
        >
          <MessageSquare size={15} /> Sohbet
        </button>
        <button
          className={`sidebar-nav-btn ${view === 'products' ? 'active' : ''}`}
          onClick={() => onViewChange('products')}
        >
          <LayoutGrid size={15} /> Ürünler
        </button>
      </div>

      {view === 'chat' && (
        <div className="sidebar-sessions">
          {pinnedSessions.length > 0 && (
            <>
              <div className="sidebar-section-title">
                <Pin size={11} /> Pinli
              </div>
              {pinnedSessions.map(renderSession)}
            </>
          )}
          {otherSessions.length > 0 && (
            <>
              <div className="sidebar-section-title">
                {pinnedSessions.length > 0 ? 'Diğer Sohbetler' : 'Son Sohbetler'}
              </div>
              {otherSessions.map(renderSession)}
            </>
          )}
          {sessions.length === 0 && (
            <div style={{ padding: '12px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Henüz geçmiş sohbet yok.
            </div>
          )}
        </div>
      )}

      <div className="sidebar-footer">
        {user ? (
          <div className="sidebar-user">
            <div className="sidebar-user-avatar">{userInitial}</div>
            <div className="sidebar-user-info">
              <div className="sidebar-user-email" title={user.email}>{user.email}</div>
              <div className="sidebar-user-label">Üye</div>
            </div>
            <button
              type="button"
              className="sidebar-user-action"
              onClick={onLogout}
              title="Çıkış yap"
              aria-label="Çıkış yap"
            >
              <LogOut size={15} />
            </button>
          </div>
        ) : (
          <button type="button" className="sidebar-login-btn" onClick={onLoginClick}>
            <LogIn size={15} /> Giriş Yap / Kayıt Ol
          </button>
        )}
        <button
          type="button"
          className="sidebar-theme-btn"
          onClick={onCycleTheme}
          title={THEME_NEXT_LABEL[theme] || 'Tema değiştir'}
          aria-label={THEME_NEXT_LABEL[theme] || 'Tema değiştir'}
        >
          <ThemeIcon theme={theme} />
          <span>
            Tema: {theme === 'auto' ? 'Otomatik' : theme === 'light' ? 'Açık' : 'Koyu'}
          </span>
        </button>
      </div>
    </div>
  );
}
