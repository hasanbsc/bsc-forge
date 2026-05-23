import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatWindow from './components/ChatWindow';
import ModelSelector from './components/ModelSelector';
import ProductsPage from './pages/ProductsPage';
import { fetchSessions, createSession, fetchSessionMessages, fetchModels, deleteSession, fetchProducts } from './services/api';

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

  // Başlangıçta modelleri ve sohbet geçmişini yükle
  useEffect(() => {
    const initData = async () => {
      try {
        const [modelsData, sessionsData, productsData] = await Promise.all([
          fetchModels().catch(() => ({ models: [], default: '' })),
          fetchSessions().catch(() => ({ sessions: [] })),
          fetchProducts().catch(() => ({ products: [] })),
        ]);
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
    } catch (err) {
      console.error("Oturum oluşturulamadı:", err);
      setSessionError('Yeni sohbet oluşturulamadı. Backend çalışıyor mu? (python3 main.py)');
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

  return (
    <div className="app-layout">
      <Sidebar
        sessions={sessions}
        currentSession={currentSession}
        onSelectSession={handleSelectSession}
        onNewSession={() => handleNewSession('forge')}
        onDeleteSession={handleDeleteSession}
        view={view}
        onViewChange={setView}
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
              <div className="chat-header-title">
                {currentSession ? currentSession.title : 'Yeni Sohbet'}
              </div>
              <div className="chat-header-actions">
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
            />
          </>
        )}
      </main>
    </div>
  );
}
