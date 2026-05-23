import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { Send, User, Flame, Wrench, Cloud, Cpu, Sparkles } from 'lucide-react';
import { ChatWebSocket } from '../services/websocket';

function resolveModelDisplay(provider, model, models) {
  if (provider === 'auto') {
    return { label: 'Model seçiliyor…', provider: 'auto', model: 'auto', model_type: 'router' };
  }
  const found = models?.find((m) => m.provider === provider && m.model === model);
  if (found) {
    return {
      label: found.label,
      provider: found.provider,
      model: found.model,
      model_type: found.type === 'local' ? 'local' : 'cloud',
    };
  }
  return {
    label: model || provider,
    provider,
    model: model || '',
    model_type: provider === 'ollama' ? 'local' : 'cloud',
  };
}

function ModelActiveIcon({ modelType, provider }) {
  if (provider === 'auto' || modelType === 'router') return <Sparkles size={12} />;
  if (modelType === 'local' || provider === 'ollama' || provider === 'forge') return <Cpu size={12} />;
  return <Cloud size={12} />;
}

export default function ChatWindow({ 
  currentSession, 
  messages, 
  setMessages,
  provider,
  model,
  models = [],
  isConnected 
}) {
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeModel, setActiveModel] = useState(null);
  const messagesEndRef = useRef(null);
  const wsRef = useRef(null);
  const streamIndexRef = useRef(null);
  const wsGenerationRef = useRef(0);

  // Otomatik aşağı kaydır
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isStreaming]);

  // WebSocket kurulumu (Strict Mode çift bağlantıya karşı nesil kilidi)
  useEffect(() => {
    const generation = ++wsGenerationRef.current;
    let opened = false;

    const ws = new ChatWebSocket(
      (token) => {
        if (generation !== wsGenerationRef.current) return;
        setMessages(prev => {
          const newMessages = [...prev];
          let idx = streamIndexRef.current;
          if (
            idx == null ||
            idx >= newMessages.length ||
            newMessages[idx].role !== 'assistant' ||
            !newMessages[idx].isStreaming
          ) {
            newMessages.push({ role: 'assistant', content: '', isStreaming: true });
            idx = newMessages.length - 1;
            streamIndexRef.current = idx;
          }
          newMessages[idx] = {
            ...newMessages[idx],
            content: newMessages[idx].content + token,
          };
          return newMessages;
        });
      },
      () => {
        if (generation !== wsGenerationRef.current) return;
        const idx = streamIndexRef.current;
        streamIndexRef.current = null;
        setIsStreaming(false);
        setActiveModel(null);
        setMessages(prev => {
          const newMessages = [...prev];
          const target =
            idx != null && newMessages[idx]?.role === 'assistant'
              ? idx
              : newMessages.length - 1;
          if (target >= 0 && newMessages[target]?.role === 'assistant') {
            newMessages[target] = { ...newMessages[target], isStreaming: false };
          }
          return newMessages;
        });
      },
      (error) => {
        if (generation !== wsGenerationRef.current || opened) return;
        setIsStreaming(false);
        setActiveModel(null);
        setMessages(prev => [...prev, { role: 'assistant', content: `**HATA:** ${error}` }]);
      },
      (toolMsg) => {
        if (generation !== wsGenerationRef.current) return;
        streamIndexRef.current = null;
        setMessages(prev => [...prev, { role: 'tool', content: toolMsg }]);
      },
      () => {
        opened = true;
      },
      (info) => {
        if (generation !== wsGenerationRef.current) return;
        setActiveModel({
          label: info.label,
          provider: info.provider,
          model: info.model,
          model_type: info.model_type || (info.provider === 'ollama' ? 'local' : 'cloud'),
        });
      }
    );

    ws.connect();
    wsRef.current = ws;

    return () => {
      wsGenerationRef.current += 1;
      ws.disconnect();
      wsRef.current = null;
    };
  }, []);

  const handleSend = (e) => {
    e.preventDefault();
    if (!input.trim() || isStreaming || !wsRef.current?.isConnected) return;

    const userMsg = input.trim();
    setInput('');
    
    // Yalnızca geçerli sohbet rolleri (araç/hata satırları hariç)
    const history = messages
      .filter(m => (m.role === 'user' || m.role === 'assistant') && !m.content?.startsWith('**HATA:**'))
      .map(m => ({ role: m.role, content: m.content }));

    streamIndexRef.current = null;
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setIsStreaming(true);
    setActiveModel(resolveModelDisplay(provider, model, models));

    wsRef.current.sendMessage(
      userMsg, 
      currentSession?.id, 
      provider, 
      model,
      history
    );
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend(e);
    }
  };

  if (!currentSession && messages.length === 0) {
    return (
      <div className="welcome-screen">
        <div className="welcome-icon">
          <Flame size={40} color="white" />
        </div>
        <h1 className="welcome-title">BSC Forge'a Hoş Geldiniz</h1>
        <p className="welcome-subtitle">Kişisel yapay zeka portalınız. Yeni bir ürün yaratmak veya soru sormak için yazmaya başlayın.</p>
        
        <div className="welcome-suggestions">
          <button className="welcome-suggestion" onClick={() => setInput('Bana BSC Forge hakkında bilgi ver.')}>
            Bana BSC Forge hakkında bilgi ver
          </button>
          <button className="welcome-suggestion" onClick={() => setInput('Yeni bir "İngilizce Öğretmeni" ajanı oluştur.')}>
            Yeni bir "İngilizce Öğretmeni" ajanı oluştur
          </button>
          <button className="welcome-suggestion" onClick={() => setInput('Python ile basit bir API nasıl yazarım?')}>
            Python ile basit bir API nasıl yazarım?
          </button>
          <button className="welcome-suggestion" onClick={() => setInput('Bilgisayarımın donanım özelliklerine göre hangi yerel modelleri çalıştırabilirim?')}>
            Hangi yerel modelleri çalıştırabilirim?
          </button>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="chat-messages">
        <div className="chat-messages-inner">
          {messages.map((msg, index) => (
            <div key={index} className={`message ${msg.role === 'tool' ? 'message-tool-row' : ''}`}>
              <div className={`message-avatar ${msg.role}`}>
                {msg.role === 'user' ? <User size={18} /> : msg.role === 'tool' ? <Wrench size={16} /> : <Flame size={20} />}
              </div>
              <div className="message-body">
                <div className="message-role">
                  {msg.role === 'user' ? 'Sen' : msg.role === 'tool' ? 'Araç' : 'Forge Ajan'}
                </div>
                <div className={`message-content ${msg.role === 'tool' ? 'message-tool' : ''}`}>
                  {msg.role === 'tool' ? (
                    msg.content
                  ) : msg.isStreaming ? (
                    <pre className="message-streaming">{msg.content}</pre>
                  ) : (
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  )}
                  {msg.isStreaming && <span className="streaming-cursor"></span>}
                </div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="chat-input-area">
        {isStreaming && activeModel && (
          <div className="active-model-bar" role="status" aria-live="polite">
            <span className="active-model-pulse" aria-hidden="true" />
            <ModelActiveIcon modelType={activeModel.model_type} provider={activeModel.provider} />
            <span className="active-model-label">{activeModel.label}</span>
            <span className="active-model-hint">yanıtlıyor…</span>
          </div>
        )}
        <div className="chat-input-container">
          <form className="chat-input-wrapper" onSubmit={handleSend}>
            <textarea
              className="chat-input"
              placeholder="Forge Ajan'a mesaj gönder..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={1}
              disabled={isStreaming}
            />
            <button 
              type="submit" 
              className="chat-send-btn"
              disabled={!input.trim() || isStreaming || !wsRef.current?.isConnected}
            >
              <Send size={18} />
            </button>
          </form>
          <div className="chat-input-hint">
            {isStreaming 
              ? 'Ajan yanıtlıyor...' 
              : wsRef.current?.isConnected 
                ? 'Göndermek için Enter, yeni satır için Shift+Enter basın.' 
                : 'Sunucuya bağlanılıyor...'}
          </div>
        </div>
      </div>
    </>
  );
}
