import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { Send, Bot, User, Flame } from 'lucide-react';
import { ChatWebSocket } from '../services/websocket';

export default function ChatWindow({ 
  currentSession, 
  messages, 
  setMessages,
  provider,
  model,
  isConnected 
}) {
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef(null);
  const wsRef = useRef(null);

  // Otomatik aşağı kaydır
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isStreaming]);

  // WebSocket kurulumu
  useEffect(() => {
    const ws = new ChatWebSocket(
      (token) => {
        setMessages(prev => {
          const newMessages = [...prev];
          const lastIndex = newMessages.length - 1;
          
          if (lastIndex >= 0 && newMessages[lastIndex].role === 'assistant' && newMessages[lastIndex].isStreaming) {
            newMessages[lastIndex].content += token;
          } else {
            newMessages.push({ role: 'assistant', content: token, isStreaming: true });
          }
          return newMessages;
        });
      },
      () => {
        setIsStreaming(false);
        setMessages(prev => {
          const newMessages = [...prev];
          if (newMessages.length > 0) {
            newMessages[newMessages.length - 1].isStreaming = false;
          }
          return newMessages;
        });
      },
      (error) => {
        setIsStreaming(false);
        setMessages(prev => [...prev, { role: 'assistant', content: `**HATA:** ${error}` }]);
      }
    );

    ws.connect();
    wsRef.current = ws;

    return () => {
      ws.disconnect();
    };
  }, [setMessages]);

  const handleSend = (e) => {
    e.preventDefault();
    if (!input.trim() || isStreaming || !wsRef.current?.isConnected) return;

    const userMsg = input.trim();
    setInput('');
    
    // Geçmiş mesajları hazırla (streaming flaglerini temizleyerek)
    const history = messages.map(m => ({
      role: m.role,
      content: m.content
    }));

    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setIsStreaming(true);

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
            <div key={index} className="message">
              <div className={`message-avatar ${msg.role}`}>
                {msg.role === 'user' ? <User size={18} /> : <Flame size={20} />}
              </div>
              <div className="message-body">
                <div className="message-role">
                  {msg.role === 'user' ? 'Sen' : 'Forge Ajan'}
                </div>
                <div className="message-content">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                  {msg.isStreaming && <span className="streaming-cursor"></span>}
                </div>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      <div className="chat-input-area">
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
