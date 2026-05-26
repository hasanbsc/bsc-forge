import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Code2, Menu } from 'lucide-react';
import Sidebar from './components/Sidebar';
import ChatWindow from './components/ChatWindow';
import ModelSelector from './components/ModelSelector';
import CodePanel from './components/CodePanel/CodePanel';
import AuthModal from './components/AuthModal';
import ProductsPage from './pages/ProductsPage';
import { fetchSessions, createSession, fetchSessionMessages, fetchModels, deleteSession, fetchProducts } from './services/api';
import {
  fetchMe,
  setToken,
  clearToken,
  claimAnonymous,
  getBrowserId,
} from './services/auth';

const addIds = (msgs) =>
  msgs.map((m, i) => ({ id: m.created_at ? `${m.created_at}-${i}` : `loaded-${i}`, ...m }));

export default function App() {
  const [sessions, setSessions] = useState([]);
  const [currentSession, setCurrentSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [models, setModels] = useState([]);
  const [provider, setProvider] = useState('auto');
  const [model, setModel] = useState('auto');
  const [sessionError, setSessionError] = useState(null);
  const [modelError, setModelError] = useState(false);
  const [view, setView] = useState('chat'); // 'chat' | 'products'
  const [products, setProducts] = useState([]);
  const [activeProductId, setActiveProductId] = useState('forge');

  // Üyelik
  const [user, setUser] = useState(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [authVersion, setAuthVersion] = useState(0); // WS'i tazelemek için

  // Codex tarzı kod paneli
  const [panelFiles, setPanelFiles] = useState([]);
  const [activeFilePath, setActiveFilePath] = useState(null);
  const [panelOpen, setPanelOpen] = useState(false);
  const [panelWidth, setPanelWidth] = useState(560);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const dragState = useRef(null);

  const handleFileTouched = useCallback((path, content) => {
    if (!path) return;
    setPanelFiles((prev) => {
      const idx = prev.findIndex((f) => f.path === path);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = { ...next[idx], content: content ?? '' };
        return next;
      }
      return [...prev, { path, content: content ?? '' }];
    });
    setActiveFilePath(path);
    setPanelOpen(true);
  }, []);

  const handleSelectTab = useCallback((path) => setActiveFilePath(path), []);

  const handleCloseTab = useCallback((path) => {
    setPanelFiles((prev) => {
      const next = prev.filter((f) => f.path !== path);
      if (path === activeFilePath) {
        setActiveFilePath(next.length ? next[next.length - 1].path : null);
      }
      if (next.length === 0) setPanelOpen(false);
      return next;
    });
  }, [activeFilePath]);

  const startResize = useCallback((e) => {
    dragState.current = { startX: e.clientX, startWidth: panelWidth };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [panelWidth]);

  useEffect(() => {
    const onMove = (e) => {
      if (!dragState.current) return;
      const dx = dragState.current.startX - e.clientX;
      const next = Math.min(Math.max(dragState.current.startWidth + dx, 320), window.innerWidth - 480);
      setPanelWidth(next);
    };
    const onUp = () => {
      if (!dragState.current) return;
      dragState.current = null;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };
  }, []);

  // Başlangıçta modelleri, sohbet geçmişini ve kullanıcıyı yükle
  useEffect(() => {
    const initData = async () => {
      try {
        // browser_id ilk açılışta üretilsin
        getBrowserId();
        const [meData, modelsData, sessionsData, productsData] = await Promise.all([
          fetchMe().catch(() => null),
          fetchModels().catch(() => ({ models: [], default: '' })),
          fetchSessions().catch(() => ({ sessions: [] })),
          fetchProducts().catch(() => ({ products: [] })),
        ]);
        setUser(meData);
        setProducts(productsData.products || []);
        
        if (modelsData.models.length > 0) {
          setModels(modelsData.models);
          setModelError(false);
          const auto = modelsData.models.find(m => m.provider === 'auto');
          if (auto || modelsData.default === 'auto') {
            setProvider('auto');
            setModel('auto');
          } else {
            const active = modelsData.models.filter(m => m.status === 'aktif' && m.provider !== 'auto');
            if (active.length > 0) {
              setProvider(active[0].provider);
              setModel(active[0].model);
            }
          }
        } else {
          setModelError(true);
        }
        
        setSessions(sessionsData.sessions || []);
      } catch (err) {
        console.error("Veriler yüklenirken hata oluştu:", err);
      }
    };
    initData();
  }, []);

  const handleNewSession = async (productId = 'forge') => {
    setSessionError(null);
    setMessages([]);
    setCurrentSession(null);
    setView('chat');

    try {
      const data = await createSession('Yeni Sohbet', productId);
      const newSession = { id: data.session_id, title: data.title, product: productId };
      setSessions([newSession, ...sessions]);
      setCurrentSession(newSession);
      setActiveProductId(productId);
      return newSession;
    } catch (err) {
      console.error("Oturum oluşturulamadı:", err);
      setSessionError('Yeni sohbet oluşturulamadı. Backend çalışıyor mu? (python3 main.py)');
      return null;
    }
  };

  const handleStartProduct = async (product) => {
    await handleNewSession(product.id);
    // Ürünün tercih ettiği model varsa onu seç
    if (product.preferred_provider && product.preferred_provider !== 'auto') {
      setProvider(product.preferred_provider);
      setModel(product.preferred_model || 'auto');
    } else {
      setProvider('auto');
      setModel('auto');
    }
  };

  const handleSelectSession = async (session) => {
    setCurrentSession(session);
    try {
      const data = await fetchSessionMessages(session.id);
      setMessages(addIds(data.messages || []));
    } catch (err) {
      console.error("Mesajlar yüklenemedi:", err);
      setMessages([]);
    }
  };

  const handleDeleteSession = async (session) => {
    const confirmed = window.confirm(`"${session.title}" sohbetini silmek istediğine emin misin?`);
    if (!confirmed) return;

    try {
      await deleteSession(session.id);
      const remaining = sessions.filter(s => s.id !== session.id);
      setSessions(remaining);

      if (currentSession?.id === session.id) {
        setCurrentSession(null);
        setMessages([]);
      }
    } catch (err) {
      console.error("Sohbet silinemedi:", err);
      setSessionError('Sohbet silinemedi. Backend çalışıyor mu?');
    }
  };

  const refreshSessions = async () => {
    try {
      const data = await fetchSessions();
      setSessions(data.sessions || []);
    } catch (err) {
      console.error('Oturumlar yenilenemedi:', err);
    }
  };

  const handleAuthSuccess = async ({ token, user: loggedUser }) => {
    setToken(token);
    setUser(loggedUser);
    setAuthOpen(false);
    setCurrentSession(null);
    setMessages([]);
    try {
      await claimAnonymous(getBrowserId());
    } catch (err) {
      console.warn('Anonim sohbet bağlama hatası:', err);
    }
    await refreshSessions();
    setAuthVersion((v) => v + 1);
  };

  const handleLogout = async () => {
    clearToken();
    setUser(null);
    setCurrentSession(null);
    setMessages([]);
    await refreshSessions();
    setAuthVersion((v) => v + 1);
  };

  const closeSidebar = () => setSidebarOpen(false);

  return (
    <div className="app-layout">
      {sidebarOpen && (
        <div className="sidebar-overlay" onClick={closeSidebar} />
      )}
      <Sidebar
        sessions={sessions}
        currentSession={currentSession}
        isOpen={sidebarOpen}
        onClose={closeSidebar}
        onSelectSession={(session) => { handleSelectSession(session); closeSidebar(); setView('chat'); }}
        onNewSession={() => { handleNewSession('forge'); closeSidebar(); }}
        onDeleteSession={handleDeleteSession}
        view={view}
        onViewChange={(v) => { setView(v); closeSidebar(); }}
        user={user}
        onLoginClick={() => setAuthOpen(true)}
        onLogout={handleLogout}
      />

      <AuthModal
        open={authOpen}
        onClose={() => setAuthOpen(false)}
        onSuccess={handleAuthSuccess}
      />
      
      <main className="main-content">
        {view === 'products' && (
          <ProductsPage
            products={products}
            setProducts={setProducts}
            onStartProduct={handleStartProduct}
          />
        )}
        {view === 'chat' && (
          <>
            {sessionError && (
              <div className="session-error-banner" role="alert">
                {sessionError}
                <button type="button" onClick={() => setSessionError(null)} aria-label="Kapat">×</button>
              </div>
            )}
            <header className="chat-header">
              <button
                type="button"
                className="mobile-menu-btn"
                onClick={() => setSidebarOpen(v => !v)}
                aria-label="Menüyü aç"
              >
                <Menu size={20} />
              </button>
              <div className="chat-header-title">
                {currentSession ? currentSession.title : 'Yeni Sohbet'}
              </div>
              <div className="chat-header-actions">
                <button
                  type="button"
                  className={`code-panel-toggle ${panelOpen ? 'active' : ''}`}
                  onClick={() => setPanelOpen((v) => !v)}
                  title="Kod panelini aç/kapat"
                >
                  <Code2 size={14} /> Kod Paneli
                  {panelFiles.length > 0 && (
                    <span className="badge">{panelFiles.length}</span>
                  )}
                </button>
                {modelError ? (
                  <span className="model-error-hint">⚠ Model listesi yüklenemedi — backend çalışıyor mu?</span>
                ) : models.length > 0 ? (
                  <ModelSelector
                    models={models}
                    provider={provider}
                    model={model}
                    onSelect={(p, m) => { setProvider(p); setModel(m); }}
                  />
                ) : null}
              </div>
            </header>
            <ChatWindow
              currentSession={currentSession}
              messages={messages}
              setMessages={setMessages}
              provider={provider}
              model={model}
              models={models}
              activeProductId={activeProductId}
              onNewSession={() => handleNewSession('forge')}
              onFileTouched={handleFileTouched}
              authVersion={authVersion}
            />
          </>
        )}
      </main>

      {panelOpen && view === 'chat' && (
        <aside className="code-panel-host" style={{ width: panelWidth }}>
          <div
            className="code-panel-resizer"
            onMouseDown={startResize}
            title="Boyutu sürükleyerek değiştir"
          />
          <CodePanel
            files={panelFiles}
            activePath={activeFilePath}
            onSelectTab={handleSelectTab}
            onCloseTab={handleCloseTab}
            onClose={() => setPanelOpen(false)}
          />
        </aside>
      )}
    </div>
  );
}
