import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import ChatWindow from './components/ChatWindow';
import ModelSelector from './components/ModelSelector';
import { fetchSessions, createSession, fetchSessionMessages, fetchModels } from './services/api';

export default function App() {
  const [sessions, setSessions] = useState([]);
  const [currentSession, setCurrentSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [models, setModels] = useState([]);
  const [provider, setProvider] = useState('gemini');
  const [model, setModel] = useState('gemini-2.5-flash');

  // Başlangıçta modelleri ve sohbet geçmişini yükle
  useEffect(() => {
    const initData = async () => {
      try {
        const [modelsData, sessionsData] = await Promise.all([
          fetchModels().catch(() => ({ models: [], default: '' })),
          fetchSessions().catch(() => ({ sessions: [] }))
        ]);
        
        if (modelsData.models.length > 0) {
          setModels(modelsData.models);
          // Varsayılan sağlayıcıyı bul
          const activeProviders = modelsData.models.filter(m => m.status === 'aktif');
          if (activeProviders.length > 0) {
            setProvider(activeProviders[0].provider);
            setModel(activeProviders[0].model);
          }
        }
        
        setSessions(sessionsData.sessions || []);
      } catch (err) {
        console.error("Veriler yüklenirken hata oluştu:", err);
      }
    };
    initData();
  }, []);

  const handleNewSession = async () => {
    try {
      const data = await createSession();
      const newSession = { id: data.session_id, title: data.title, product: 'forge' };
      setSessions([newSession, ...sessions]);
      setCurrentSession(newSession);
      setMessages([]);
    } catch (err) {
      console.error("Oturum oluşturulamadı:", err);
    }
  };

  const handleSelectSession = async (session) => {
    setCurrentSession(session);
    try {
      const data = await fetchSessionMessages(session.id);
      setMessages(data.messages || []);
    } catch (err) {
      console.error("Mesajlar yüklenemedi:", err);
      setMessages([]);
    }
  };

  return (
    <div className="app-layout">
      <Sidebar 
        sessions={sessions} 
        currentSession={currentSession}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
      />
      
      <main className="main-content">
        <header className="chat-header">
          <div className="chat-header-title">
            {currentSession ? currentSession.title : 'Yeni Sohbet'}
          </div>
          <div className="chat-header-actions">
            {models.length > 0 && (
              <ModelSelector 
                models={models}
                provider={provider}
                model={model}
                onSelect={(p, m) => {
                  setProvider(p);
                  setModel(m);
                }}
              />
            )}
          </div>
        </header>
        
        <ChatWindow 
          currentSession={currentSession}
          messages={messages}
          setMessages={setMessages}
          provider={provider}
          model={model}
        />
      </main>
    </div>
  );
}
