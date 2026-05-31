import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { Send, User, Flame, Wrench, Cloud, Cpu, Sparkles, FolderOpen, FileX, ArrowUp, ArrowDown, Music, Search, X as XIcon, Copy, Check } from 'lucide-react';
import { ChatWebSocket } from '../services/websocket';

const genId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
const fmtTok = (n) => n >= 1000 ? `${(n / 1000).toFixed(1)}k` : `${n}`;

// 2D Oyun Stüdyosu: yerel model oyunu ```html kod bloğu olarak üretir
// (Ollama tool-calling yapmaz). Bloğu çıkar, Kaplay CDN'ini garantili doğru
// URL'e sabitle (küçük model URL'i bozabiliyor) ve kod paneline gönder.
const KAPLAY_CDN = 'https://unpkg.com/kaplay@3001.0.19/dist/kaplay.js';

function extractHtmlBlock(text) {
  if (!text) return null;
  const fence = text.match(/```(?:html)?\s*\n([\s\S]*?)```/i);
  if (fence && /<(!doctype|html|script|canvas)/i.test(fence[1])) return fence[1].trim();
  const doc = text.match(/<!DOCTYPE html>[\s\S]*<\/html>/i);
  return doc ? doc[0].trim() : null;
}

function normalizeGameHtml(html) {
  // Kaplay/Kaboom script src'sini kanonik URL'e zorla (model yanlış yazsa da çalışsın)
  let out = html.replace(
    /<script\b[^>]*\bsrc=["'][^"']*(?:kaplay|kaboom)[^"']*["'][^>]*><\/script>/i,
    `<script src="${KAPLAY_CDN}"></script>`,
  );
  // Hiç kaplay script'i yoksa <body> başına ekle
  if (!/unpkg\.com\/kaplay/i.test(out) && /<body[^>]*>/i.test(out)) {
    out = out.replace(/<body[^>]*>/i, (m) => `${m}\n<script src="${KAPLAY_CDN}"></script>`);
  }
  return out;
}

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

const escapeRegex = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

function HighlightedText({ text, query }) {
  if (!query) return text;
  const re = new RegExp(`(${escapeRegex(query)})`, 'ig');
  const parts = String(text).split(re);
  return parts.map((part, i) =>
    re.test(part) && part.toLowerCase() === query.toLowerCase()
      ? <mark key={i} className="chat-search-mark">{part}</mark>
      : part
  );
}

export default function ChatWindow({
  currentSession,
  messages,
  setMessages,
  provider,
  model,
  models = [],
  activeProductId = 'forge',
  onNewSession,
  onFileTouched,
  authVersion = 0,
}) {
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [activeModel, setActiveModel] = useState(null);
  const [sessionTokens, setSessionTokens] = useState({ input: 0, output: 0 });
  const [approvalQueue, setApprovalQueue] = useState([]); // dosya onay kuyruğu (çoklu dosya için)
  const [approvalPath, setApprovalPath] = useState('');
  const [approvalError, setApprovalError] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [batchSaveAll, setBatchSaveAll] = useState(false); // "Tümünü kabul et" modu
  const [orchestrate, setOrchestrate] = useState(false); // Orkestra şefi (yerel LLM ön-analiz)
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [copiedMsgId, setCopiedMsgId] = useState(null);
  const searchInputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const wsRef = useRef(null);
  const streamIndexRef = useRef(null);
  const wsGenerationRef = useRef(0);
  const activeModelRef = useRef(null);
  const savedDirHandleRef = useRef(null); // İlk seçimden sonra aynı klasör kullanılır

  const pendingApproval = approvalQueue[0] || null;

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isStreaming]);

  // Ctrl+F / Cmd+F → arama aç; Esc → kapat
  useEffect(() => {
    const onKey = (e) => {
      const ctrlF = (e.ctrlKey || e.metaKey) && (e.key === 'f' || e.key === 'F');
      if (ctrlF) {
        e.preventDefault();
        setSearchOpen(true);
        setTimeout(() => searchInputRef.current?.focus(), 0);
      } else if (e.key === 'Escape' && searchOpen) {
        setSearchOpen(false);
        setSearchQuery('');
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [searchOpen]);

  const closeSearch = () => {
    setSearchOpen(false);
    setSearchQuery('');
  };

  // Oyun Stüdyosu: tamamlanan yanıttaki ```html oyununu kod paneline gönder
  useEffect(() => {
    if (activeProductId !== 'game_studio') return;
    const last = messages[messages.length - 1];
    if (!last || last.role !== 'assistant' || last.isStreaming) return;
    const html = extractHtmlBlock(last.content);
    if (html) onFileTouched?.('oyun.html', normalizeGameHtml(html));
  }, [messages, activeProductId, onFileTouched]);

  const handleCopy = async (msg) => {
    try {
      await navigator.clipboard.writeText(msg.content);
      setCopiedMsgId(msg.id);
      setTimeout(() => setCopiedMsgId((id) => (id === msg.id ? null : id)), 1500);
    } catch (err) {
      console.warn('Kopyalama başarısız:', err);
    }
  };

  // Mesajlarda arama: query varsa içerikte (case-insensitive) eşleşenleri tut.
  const normalizedQuery = searchQuery.trim().toLowerCase();
  const filteredMessages = normalizedQuery
    ? messages.filter((m) => (m.content || '').toLowerCase().includes(normalizedQuery))
    : messages;

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
      // onApprovalRequest — dosya yazma onayı bekliyor (çoklu dosya kuyruğu)
      (data) => {
        if (generation !== wsGenerationRef.current) return;
        setIsStreaming(false);
        setActiveModel(null);
        streamIndexRef.current = null;
        setApprovalQueue((prev) => {
          const next = [...prev, data];
          if (prev.length === 0) {
            setApprovalPath(data.path || '');
          }
          return next;
        });
        if (data?.path) onFileTouched?.(data.path, data.content || '');
      },
    );

    ws.connect();
    wsRef.current = ws;

    return () => {
      wsGenerationRef.current += 1;
      ws.disconnect();
      wsRef.current = null;
    };
  }, [authVersion]);

  const sendText = async (text, overrideSessionId) => {
    const userMsg = (text || '').trim();
    if (!userMsg || isStreaming || !wsRef.current?.isConnected) return;

    // Oturum yoksa anında oluştur — kullanıcı karşılama ekranında doğrudan
    // yazıp gönderebilsin diye (ekstra "yeni sohbet" tıklaması gerekmez).
    let sessionId = overrideSessionId ?? currentSession?.id;
    if (!sessionId) {
      if (!onNewSession) return;
      const newSession = await onNewSession();
      sessionId = newSession?.id;
      if (!sessionId) return;
    }

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
      sessionId,
      provider,
      model,
      history,
      'manual',
      activeProductId,
      orchestrate,
    );
  };

  const handleSend = (e) => {
    e.preventDefault();
    sendText(input);
  };

  const handleSuggestionClick = (text) => sendText(text);

  const popApprovalQueue = () => {
    setApprovalQueue((prev) => {
      const next = prev.slice(1);
      if (next.length > 0) {
        setApprovalPath(next[0]?.path || '');
      } else {
        setApprovalPath('');
        setBatchSaveAll(false);
        savedDirHandleRef.current = null;
      }
      return next;
    });
    setApprovalError('');
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
    popApprovalQueue();
  };

  const writeToDir = async (dirHandle, filePath, content) => {
    const parts = filePath.split('/').filter(Boolean);
    const filename = parts.pop();
    let target = dirHandle;
    for (const sub of parts) {
      target = await target.getDirectoryHandle(sub, { create: true });
    }
    const fileHandle = await target.getFileHandle(filename, { create: true });
    const writable = await fileHandle.createWritable();
    // UTF-8 zorla: ham string yazımı Türkçe karakterleri bozar (Kahve DÃ¼kkanÄ±).
    // Blob veya Uint8Array tarayıcıya kesin UTF-8 byte'larını verir.
    const utf8Bytes = new TextEncoder().encode(content);
    await writable.write(utf8Bytes);
    await writable.close();
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
      let dirHandle = savedDirHandleRef.current;
      if (!dirHandle) {
        dirHandle = await window.showDirectoryPicker({ mode: 'readwrite' });
        savedDirHandleRef.current = dirHandle;
      }
      await writeToDir(dirHandle, approvalPath, pendingApproval.content);
      wsRef.current.sendApproval(
        approvalPath,
        true,
        currentSession?.id,
        activeProductId,
        dirHandle.name,
      );
      popApprovalQueue();
    } catch (err) {
      if (err.name !== 'AbortError') {
        setApprovalError(`Kaydedilemedi: ${err.message}`);
      }
    } finally {
      setIsSaving(false);
    }
  };

  const handleSaveAll = async () => {
    if (!pendingApproval || !wsRef.current?.isConnected) return;
    if (!window.showDirectoryPicker) {
      setApprovalError('Bu tarayıcı klasör seçmeyi desteklemiyor. Chrome veya Edge kullanın.');
      return;
    }

    setApprovalError('');
    setIsSaving(true);
    setBatchSaveAll(true);
    try {
      let dirHandle = savedDirHandleRef.current;
      if (!dirHandle) {
        dirHandle = await window.showDirectoryPicker({ mode: 'readwrite' });
        savedDirHandleRef.current = dirHandle;
      }
      // Mevcut + kuyruktaki tüm dosyaları aynı klasöre sıralı kaydet
      const queueSnapshot = [...approvalQueue];
      for (const item of queueSnapshot) {
        const filePath = (item.path || '').trim() || 'dosya.txt';
        try {
          await writeToDir(dirHandle, filePath, item.content || '');
          wsRef.current.sendApproval(
            filePath,
            true,
            currentSession?.id,
            activeProductId,
            dirHandle.name,
          );
        } catch (err) {
          wsRef.current.sendApproval(
            filePath,
            false,
            currentSession?.id,
            activeProductId,
            '',
          );
          throw err;
        }
      }
      // Queue'yu temizle
      setApprovalQueue([]);
      setApprovalPath('');
      setBatchSaveAll(false);
      savedDirHandleRef.current = null;
    } catch (err) {
      if (err.name !== 'AbortError') {
        setApprovalError(`Kaydedilemedi: ${err.message}`);
      }
      setBatchSaveAll(false);
    } finally {
      setIsSaving(false);
    }
  };

  const handleRejectAll = () => {
    if (!wsRef.current?.isConnected) return;
    const queueSnapshot = [...approvalQueue];
    for (const item of queueSnapshot) {
      wsRef.current.sendApproval(
        item.path || '',
        false,
        currentSession?.id,
        activeProductId,
        '',
      );
    }
    setApprovalQueue([]);
    setApprovalPath('');
    setApprovalError('');
    setBatchSaveAll(false);
    savedDirHandleRef.current = null;
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend(e);
    }
  };

  // Henüz mesaj yoksa karşılama içeriğini mesaj alanının içinde göster —
  // input alanı her zaman altta görünür kalsın ki kullanıcı doğrudan yazabilsin.
  const showWelcome = messages.length === 0 && !normalizedQuery;

  return (
    <>
      {searchOpen && (
        <div className="chat-search-bar">
          <Search size={14} />
          <input
            ref={searchInputRef}
            type="search"
            placeholder="Mesajlarda ara…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="chat-search-input"
          />
          <span className="chat-search-count">
            {normalizedQuery ? `${filteredMessages.length} / ${messages.length}` : `${messages.length} mesaj`}
          </span>
          <button type="button" className="chat-search-close" onClick={closeSearch} aria-label="Aramayı kapat">
            <XIcon size={14} />
          </button>
        </div>
      )}
      <div className="chat-messages">
        <div className="chat-messages-inner">
          {showWelcome && (
            <div className="welcome-screen">
              <div className="welcome-icon">
                <Flame size={40} color="white" />
              </div>
              <h1 className="welcome-title">BSC Forge'a Hoş Geldiniz</h1>
              <p className="welcome-subtitle">Kişisel yapay zeka portalınız. Aşağıdan doğrudan yazmaya başlayın veya bir öneri seçin.</p>

              <div className="welcome-suggestions">
                <button className="welcome-suggestion" onClick={() => handleSuggestionClick('Bana BSC Forge hakkında bilgi ver.')}>
                  Bana BSC Forge hakkında bilgi ver
                </button>
                <button className="welcome-suggestion" onClick={() => handleSuggestionClick('Yeni bir "İngilizce Öğretmeni" ajanı oluştur.')}>
                  Yeni bir "İngilizce Öğretmeni" ajanı oluştur
                </button>
                <button className="welcome-suggestion" onClick={() => handleSuggestionClick('Python ile basit bir API nasıl yazarım?')}>
                  Python ile basit bir API nasıl yazarım?
                </button>
                <button className="welcome-suggestion" onClick={() => handleSuggestionClick('Bilgisayarımın donanım özelliklerine göre hangi yerel modelleri çalıştırabilirim?')}>
                  Hangi yerel modelleri çalıştırabilirim?
                </button>
              </div>
            </div>
          )}
          {filteredMessages.map((msg) => (
            <div key={msg.id} className={`message ${msg.role === 'tool' ? 'message-tool-row' : ''}`}>
              <div className={`message-avatar ${msg.role}`}>
                {msg.role === 'user' ? <User size={18} /> : msg.role === 'tool' ? <Wrench size={16} /> : <Flame size={20} />}
              </div>
              <div className="message-body">
                <div className="message-role">
                  {msg.role === 'user' ? 'Sen' : msg.role === 'tool' ? 'Araç' : 'Forge Ajan'}
                  {msg.role === 'assistant' && !msg.isStreaming && msg.content?.trim() && (
                    <button
                      type="button"
                      className="message-copy-btn"
                      title="Kopyala"
                      onClick={() => handleCopy(msg)}
                    >
                      {copiedMsgId === msg.id ? <Check size={12} /> : <Copy size={12} />}
                      {copiedMsgId === msg.id ? 'Kopyalandı' : 'Kopyala'}
                    </button>
                  )}
                </div>
                <div className={`message-content ${msg.role === 'tool' ? 'message-tool' : ''}`}>
                  {msg.role === 'tool' ? (
                    <HighlightedText text={msg.content} query={normalizedQuery} />
                  ) : msg.isStreaming ? (
                    <pre className="message-streaming">{msg.content}</pre>
                  ) : normalizedQuery ? (
                    <pre className="message-streaming"><HighlightedText text={msg.content} query={normalizedQuery} /></pre>
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
                  <div className="approval-title">
                    Dosya Kaydetme Onayı
                    {approvalQueue.length > 1 && (
                      <span className="approval-batch-badge">
                        1 / {approvalQueue.length}
                      </span>
                    )}
                  </div>
                  <div className="approval-path-hint">
                    {approvalQueue.length > 1
                      ? `${approvalQueue.length} dosya sırada. "Tümünü Kabul Et" ile hepsini aynı klasöre kaydedebilirsin.`
                      : (savedDirHandleRef.current
                          ? `"${savedDirHandleRef.current.name}" klasörüne kaydedilecek.`
                          : 'Klasör seçeceksiniz; dosya bilgisayarınıza kaydedilir.')}
                  </div>
                </div>
              </div>
              {approvalQueue.length > 1 && (
                <div className="approval-batch-list">
                  {approvalQueue.map((item, idx) => (
                    <span
                      key={`${item.path}-${idx}`}
                      className={`approval-batch-chip ${idx === 0 ? 'current' : ''}`}
                      title={item.path}
                    >
                      {idx === 0 ? '▶ ' : ''}{(item.path || '').split('/').pop()}
                    </span>
                  ))}
                </div>
              )}
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
                  <FolderOpen size={15} />
                  {isSaving && !batchSaveAll
                    ? 'Kaydediliyor…'
                    : (savedDirHandleRef.current ? 'Bu Dosyayı Kaydet' : 'Klasör Seç ve Kaydet')}
                </button>
                {approvalQueue.length > 1 && (
                  <button
                    className="approval-btn-accept-all"
                    onClick={handleSaveAll}
                    disabled={isSaving}
                    title="Kalan tüm dosyaları aynı klasöre kaydet"
                  >
                    {batchSaveAll ? 'Tümü kaydediliyor…' : `Tümünü Kabul Et (${approvalQueue.length})`}
                  </button>
                )}
                <button className="approval-btn-reject" onClick={handleReject} disabled={isSaving}>
                  <FileX size={15} /> Reddet
                </button>
                {approvalQueue.length > 1 && (
                  <button
                    className="approval-btn-reject"
                    onClick={handleRejectAll}
                    disabled={isSaving}
                    title="Tüm kuyruğu reddet"
                  >
                    Tümünü Reddet
                  </button>
                )}
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
              type="button"
              className={`chat-orchestrate-btn ${orchestrate ? 'active' : ''}`}
              onClick={() => setOrchestrate((v) => !v)}
              title={
                orchestrate
                  ? 'Orkestra şefi açık — yerel model ile ön analiz (1-8s gecikme)'
                  : 'Orkestra şefi kapalı — sadece hızlı heuristik (sıfır gecikme)'
              }
              disabled={isStreaming}
            >
              <Music size={16} />
            </button>
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
