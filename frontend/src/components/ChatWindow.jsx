import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { Send, User, Flame, Wrench, Cloud, Cpu, Sparkles, FolderOpen, FileX, ArrowUp, ArrowDown } from 'lucide-react';
import { ChatWebSocket } from '../services/websocket';

const genId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
const fmtTok = (n) => n >= 1000 ? `${(n / 1000).toFixed(1)}k` : `${n}`;

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
  activeProductId = 'forge',
}) {
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeModel, setActiveModel] = useState(null);
  const [sessionTokens, setSessionTokens] = useState({ input: 0, output: 0 });
  const [pendingApproval, setPendingApproval] = useState(null);
  const [approvalPath, setApprovalPath] = useState('');
  const [approvalError, setApprovalError] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const messagesEndRef = useRef(null);
  const wsRef = useRef(null);
  const streamIndexRef = useRef(null);
  const wsGenerationRef = useRef(0);
  const activeModelRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isStreaming]);

  // WebSocket kurulumu (Strict Mode çift bağlantıya karşı nesil kilidi)
  useEffect(() => {
    const generation = ++wsGenerationRef.current;

    const ws = new ChatWebSocket(
      // onToken
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
            newMessages.push({ id: genId(), role: 'assistant', content: '', isStreaming: true });
            idx = newMessages.length - 1;
            streamIndexRef.current = idx;
          }
          newMessages[idx] = { ...newMessages[idx], content: newMessages[idx].content + token };
          return newMessages;
        });
      },
      // onDone
      (usage) => {
        if (generation !== wsGenerationRef.current) return;
        const idx = streamIndexRef.current;
        const capturedModel = activeModelRef.current;
        streamIndexRef.current = null;
        activeModelRef.current = null;
        setIsStreaming(false);
        setActiveModel(null);
        if (usage) {
          setSessionTokens(prev => ({
            input: prev.input + usage.input,
            output: prev.output + usage.output,
          }));
        }
        setMessages(prev => {
          const newMessages = [...prev];
          const target =
            idx != null && newMessages[idx]?.role === 'assistant'
              ? idx
              : newMessages.length - 1;
          if (target >= 0 && newMessages[target]?.role === 'assistant') {
            newMessages[target] = {
              ...newMessages[target],
              isStreaming: false,
              usage: usage || null,
              modelLabel: capturedModel?.label || null,
            };
          }
          return newMessages;
        });
      },
      // onError
      (error) => {
        if (generation !== wsGenerationRef.current) return;
        setIsStreaming(false);
        setActiveModel(null);
        streamIndexRef.current = null;
        setMessages(prev => [
          ...prev,
          { id: genId(), role: 'assistant', content: `**HATA:** ${error}` },
        ]);
      },
      // onTool
      (toolMsg) => {
        if (generation !== wsGenerationRef.current) return;
        streamIndexRef.current = null;
        setMessages(prev => [...prev, { id: genId(), role: 'tool', content: toolMsg }]);
      },
      // onOpen
      () => {},
      // onModelActive
      (info) => {
        if (generation !== wsGenerationRef.current) return;
        const m = {
          label: info.label,
          provider: info.provider,
          model: info.model,
          model_type: info.model_type || (info.provider === 'ollama' ? 'local' : 'cloud'),
        };
        setActiveModel(m);
        activeModelRef.current = m;
      },
      // onDisconnect — WS kopunca streaming'i zorla sıfırla
      () => {
        if (generation !== wsGenerationRef.current) return;
        setIsStreaming(false);
        setActiveModel(null);
        streamIndexRef.current = null;
      },
      // onApprovalRequest — dosya yazma onayı bekliyor
      (data) => {
        if (generation !== wsGenerationRef.current) return;
        setIsStreaming(false);
        setActiveModel(null);
        streamIndexRef.current = null;
        setPendingApproval(data);
        setApprovalPath(data.path || '');
      },
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

    const history = messages
      .filter(m => (m.role === 'user' || m.role === 'assistant') && !m.isError)
      .map(m => ({ role: m.role, content: m.content }));

    streamIndexRef.current = null;
    setMessages(prev => [...prev, { id: genId(), role: 'user', content: userMsg }]);
    setIsStreaming(true);
    setActiveModel(resolveModelDisplay(provider, model, models));

    wsRef.current.sendMessage(
      userMsg,
      currentSession?.id,
      provider,
      model,
      history,
      'manual',
      activeProductId,
    );
  };

  const handleReject = () => {
    if (!pendingApproval || !wsRef.current?.isConnected) return;
    wsRef.current.sendApproval(
      pendingApproval.path,
      false,
      currentSession?.id,
      activeProductId,
      '',
    );
    setIsStreaming(true);
    setPendingApproval(null);
    setApprovalPath('');
    setApprovalError('');
  };

  const handlePickAndSave = async () => {
    if (!pendingApproval || !wsRef.current?.isConnected) return;
    if (!window.showDirectoryPicker) {
      setApprovalError('Bu tarayıcı klasör seçmeyi desteklemiyor. Chrome veya Edge kullanın.');
      return;
    }
    if (!approvalPath.trim()) {
      setApprovalError('Dosya adı boş olamaz.');
      return;
    }

    setApprovalError('');
    setIsSaving(true);
    try {
      const dirHandle = await window.showDirectoryPicker({ mode: 'readwrite' });
      const parts = approvalPath.split('/').filter(Boolean);
      const filename = parts.pop();
      let target = dirHandle;
      for (const sub of parts) {
        target = await target.getDirectoryHandle(sub, { create: true });
      }
      const fileHandle = await target.getFileHandle(filename, { create: true });
      const writable = await fileHandle.createWritable();
      await writable.write(pendingApproval.content);
      await writable.close();

      wsRef.current.sendApproval(
        approvalPath,
        true,
        currentSession?.id,
        activeProductId,
        dirHandle.name,
      );
      setIsStreaming(true);
      setPendingApproval(null);
      setApprovalPath('');
    } catch (err) {
      if (err.name !== 'AbortError') {
        setApprovalError(`Kaydedilemedi: ${err.message}`);
      }
    } finally {
      setIsSaving(false);
    }
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
          {messages.map((msg) => (
            <div key={msg.id} className={`message ${msg.role === 'tool' ? 'message-tool-row' : ''}`}>
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
                {!msg.isStreaming && msg.usage && (
                  <div className="message-token-meta">
                    {msg.modelLabel && (
                      <span className="token-chip token-chip-model">
                        <Sparkles size={10} /> {msg.modelLabel}
                      </span>
                    )}
                    <span className="token-chip" title="Girdi tokenları">
                      <ArrowUp size={10} /> {fmtTok(msg.usage.input)}
                    </span>
                    <span className="token-chip" title="Çıktı tokenları">
                      <ArrowDown size={10} /> {fmtTok(msg.usage.output)}
                    </span>
                  </div>
                )}
              </div>
            </div>
          ))}
          {pendingApproval && (
            <div className="approval-card">
              <div className="approval-header">
                <span className="approval-icon">📥</span>
                <div className="approval-header-text">
                  <div className="approval-title">Dosya Kaydetme Onayı</div>
                  <div className="approval-path-hint">Klasör seçeceksiniz; dosya bilgisayarınıza kaydedilir.</div>
                </div>
              </div>
              <div className="approval-path-row">
                <label className="approval-path-label">Dosya adı</label>
                <input
                  className="approval-path-input"
                  value={approvalPath}
                  onChange={(e) => setApprovalPath(e.target.value)}
                  placeholder="örn. index.html"
                  spellCheck={false}
                />
              </div>
              <pre className="approval-preview">{pendingApproval.preview}</pre>
              {approvalError && <div className="approval-error">{approvalError}</div>}
              <div className="approval-actions">
                <button
                  className="approval-btn-accept"
                  onClick={handlePickAndSave}
                  disabled={!approvalPath.trim() || isSaving}
                >
                  <FolderOpen size={15} /> {isSaving ? 'Kaydediliyor…' : 'Klasör Seç ve Kaydet'}
                </button>
                <button className="approval-btn-reject" onClick={handleReject} disabled={isSaving}>
                  <FileX size={15} /> Reddet
                </button>
              </div>
            </div>
          )}

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
            <span className="hint-text">
              {isStreaming
                ? 'Ajan yanıtlıyor...'
                : wsRef.current?.isConnected
                  ? 'Enter gönderir · Shift+Enter yeni satır'
                  : 'Sunucuya bağlanılıyor...'}
            </span>
            {sessionTokens.output > 0 && (
              <span className="hint-tokens">
                <span className="hint-token-item" title="Bu oturumdaki toplam girdi tokenı">
                  <ArrowUp size={10} /> {fmtTok(sessionTokens.input)}
                </span>
                <span className="hint-token-item" title="Bu oturumdaki toplam çıktı tokenı">
                  <ArrowDown size={10} /> {fmtTok(sessionTokens.output)}
                </span>
              </span>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
