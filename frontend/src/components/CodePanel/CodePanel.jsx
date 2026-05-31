import React, { useState, useMemo, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import { X, Code2, Eye, Copy, Check } from 'lucide-react';

const EXT_TO_LANG = {
  html: 'html', htm: 'html',
  css: 'css',
  js: 'javascript', mjs: 'javascript', jsx: 'javascript',
  ts: 'typescript', tsx: 'typescript',
  py: 'python',
  json: 'json',
  md: 'markdown',
  sh: 'shell', bash: 'shell',
  yml: 'yaml', yaml: 'yaml',
  sql: 'sql',
  go: 'go',
  rs: 'rust',
  java: 'java',
  c: 'c', h: 'c',
  cpp: 'cpp', hpp: 'cpp',
  rb: 'ruby',
  php: 'php',
  xml: 'xml',
  toml: 'toml',
};

function langForPath(path) {
  if (!path) return 'plaintext';
  const ext = path.split('.').pop().toLowerCase();
  return EXT_TO_LANG[ext] || 'plaintext';
}

function basename(path) {
  if (!path) return 'dosya';
  const parts = path.split(/[\\/]/);
  return parts[parts.length - 1] || path;
}

export default function CodePanel({ files, activePath, onSelectTab, onCloseTab, onClose, previewSignal = 0 }) {
  const [view, setView] = useState('code'); // 'code' | 'preview'
  const [copied, setCopied] = useState(false);

  const activeFile = useMemo(
    () => files.find((f) => f.path === activePath) || files[0],
    [files, activePath]
  );

  const isHtml = activeFile && /\.(html?|htm)$/i.test(activeFile.path);

  // Dışarıdan önizleme istendiğinde (örn. oyun üretildi) önizleme sekmesine geç
  useEffect(() => {
    if (previewSignal > 0) setView('preview');
  }, [previewSignal]);
  const effectiveView = isHtml ? view : 'code';

  const handleCopy = async () => {
    if (!activeFile) return;
    try {
      await navigator.clipboard.writeText(activeFile.content || '');
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      /* yoksay */
    }
  };

  if (!files.length) {
    return (
      <div className="code-panel">
        <div className="code-panel-header">
          <span className="code-panel-title">
            <Code2 size={14} /> Kod Paneli
          </span>
          <button className="code-panel-close" onClick={onClose} aria-label="Paneli kapat">
            <X size={16} />
          </button>
        </div>
        <div className="code-panel-empty">
          Henüz dosya yok. Sohbette dosya/site oluşturduğunda burada görünecek.
        </div>
      </div>
    );
  }

  return (
    <div className="code-panel">
      <div className="code-panel-header">
        <div className="code-panel-tabs">
          {files.map((f) => (
            <div
              key={f.path}
              className={`code-tab ${f.path === activePath ? 'active' : ''}`}
              onClick={() => onSelectTab(f.path)}
              title={f.path}
            >
              <span className="code-tab-name">{basename(f.path)}</span>
              <button
                className="code-tab-close"
                onClick={(e) => { e.stopPropagation(); onCloseTab(f.path); }}
                aria-label="Sekmeyi kapat"
              >
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
        <div className="code-panel-actions">
          {isHtml && (
            <div className="code-view-toggle">
              <button
                className={effectiveView === 'code' ? 'active' : ''}
                onClick={() => setView('code')}
              >
                <Code2 size={12} /> Kod
              </button>
              <button
                className={effectiveView === 'preview' ? 'active' : ''}
                onClick={() => setView('preview')}
              >
                <Eye size={12} /> Önizle
              </button>
            </div>
          )}
          <button className="code-panel-icon-btn" onClick={handleCopy} title="Kopyala">
            {copied ? <Check size={14} /> : <Copy size={14} />}
          </button>
          <button className="code-panel-close" onClick={onClose} aria-label="Paneli kapat">
            <X size={16} />
          </button>
        </div>
      </div>

      <div className="code-panel-body">
        {effectiveView === 'code' ? (
          <Editor
            height="100%"
            language={langForPath(activeFile.path)}
            value={activeFile.content || ''}
            theme="vs-dark"
            options={{
              readOnly: true,
              minimap: { enabled: false },
              fontSize: 13,
              wordWrap: 'on',
              scrollBeyondLastLine: false,
              renderLineHighlight: 'none',
              automaticLayout: true,
            }}
          />
        ) : (
          <iframe
            className="code-preview-iframe"
            title="Önizleme"
            srcDoc={activeFile.content || ''}
            sandbox="allow-scripts allow-same-origin allow-forms"
          />
        )}
      </div>

      <div className="code-panel-footer">
        <span className="code-panel-path" title={activeFile.path}>
          📄 {activeFile.path}
        </span>
        <span className="code-panel-meta">
          {(activeFile.content || '').length.toLocaleString('tr-TR')} karakter
        </span>
      </div>
    </div>
  );
}
