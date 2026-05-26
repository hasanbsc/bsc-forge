import React from 'react';
import { Plus, MessageSquare, Flame, Trash2, LayoutGrid, LogIn, LogOut } from 'lucide-react';

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
}) {
  const userInitial = user?.email ? user.email[0].toUpperCase() : '?';
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
          <div className="sidebar-section-title">Son Sohbetler</div>
          {sessions.map(session => (
            <div
              key={session.id}
              className={`session-item ${currentSession?.id === session.id ? 'active' : ''}`}
              onClick={() => onSelectSession(session)}
            >
              <MessageSquare size={16} className="session-item-icon" />
              <div className="session-item-text">{session.title}</div>
              <button
                type="button"
                className="session-delete-btn"
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
          ))}
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
        <div className="session-item" style={{ marginBottom: 0 }}>
          <Flame size={16} className="session-item-icon" color="var(--accent-amber)" />
          <div className="session-item-text" style={{ color: 'var(--text-secondary)' }}>Ajan Ayarları</div>
        </div>
      </div>
    </div>
  );
}
