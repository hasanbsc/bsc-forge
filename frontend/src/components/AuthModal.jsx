import React, { useState } from 'react';
import { X, Mail, Lock, LogIn, UserPlus } from 'lucide-react';
import { login as apiLogin, register as apiRegister } from '../services/auth';

export default function AuthModal({ open, onClose, onSuccess }) {
  const [mode, setMode] = useState('login'); // 'login' | 'register'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!open) return null;

  const isLogin = mode === 'login';
  const title = isLogin ? 'Giriş Yap' : 'Hesap Oluştur';
  const submitLabel = isLogin ? 'Giriş Yap' : 'Hesap Oluştur';
  const SubmitIcon = isLogin ? LogIn : UserPlus;

  const reset = () => {
    setError('');
    setPassword('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (!email.trim() || !password) {
      setError('E-posta ve şifre zorunlu.');
      return;
    }
    if (!isLogin && password.length < 8) {
      setError('Şifre en az 8 karakter olmalı.');
      return;
    }
    setLoading(true);
    try {
      const data = isLogin
        ? await apiLogin(email.trim(), password)
        : await apiRegister(email.trim(), password);
      onSuccess?.(data);
    } catch (err) {
      setError(err.message || 'İşlem başarısız oldu.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-modal-overlay" onClick={onClose}>
      <div className="auth-modal" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="auth-modal-close" onClick={onClose} aria-label="Kapat">
          <X size={18} />
        </button>
        <h2 className="auth-modal-title">{title}</h2>
        <p className="auth-modal-subtitle">
          {isLogin
            ? 'Sohbetlerini hesabına bağla ve farklı cihazlardan eriş.'
            : 'E-posta ve şifre ile yeni hesap oluştur.'}
        </p>

        <form onSubmit={handleSubmit} className="auth-form">
          <label className="auth-field">
            <span className="auth-field-icon"><Mail size={15} /></span>
            <input
              type="email"
              placeholder="E-posta"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              required
              disabled={loading}
            />
          </label>
          <label className="auth-field">
            <span className="auth-field-icon"><Lock size={15} /></span>
            <input
              type="password"
              placeholder={isLogin ? 'Şifre' : 'Şifre (en az 8 karakter)'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={isLogin ? 'current-password' : 'new-password'}
              required
              disabled={loading}
            />
          </label>

          {error && <div className="auth-error">{error}</div>}

          <button type="submit" className="auth-submit-btn" disabled={loading}>
            <SubmitIcon size={15} />
            {loading ? 'Lütfen bekle…' : submitLabel}
          </button>
        </form>

        <div className="auth-toggle">
          {isLogin ? 'Hesabın yok mu?' : 'Zaten hesabın var mı?'}{' '}
          <button
            type="button"
            className="auth-toggle-btn"
            onClick={() => { setMode(isLogin ? 'register' : 'login'); reset(); }}
            disabled={loading}
          >
            {isLogin ? 'Hesap oluştur' : 'Giriş yap'}
          </button>
        </div>
      </div>
    </div>
  );
}
