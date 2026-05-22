import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Cloud, Cpu, Server } from 'lucide-react';

export default function ModelSelector({ 
  models, 
  provider, 
  model, 
  onSelect 
}) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Tıklama dışı kapatma
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const currentModel = models.find(m => m.provider === provider && m.model === model) || 
                       models.find(m => m.provider === provider) ||
                       models[0];

  if (!currentModel) return null;

  const isLocal = currentModel.type === 'local';

  return (
    <div className="model-selector" ref={dropdownRef}>
      <button 
        className="model-selector-btn" 
        onClick={() => setIsOpen(!isOpen)}
      >
        {isLocal ? <Cpu size={14} /> : <Cloud size={14} />}
        <span>{currentModel.label}</span>
        <ChevronDown size={14} />
      </button>

      {isOpen && (
        <div className="model-dropdown">
          {models.map((m, idx) => (
            <div 
              key={idx} 
              className={`model-dropdown-item ${m.provider === provider && m.model === model ? 'selected' : ''}`}
              onClick={() => {
                onSelect(m.provider, m.model);
                setIsOpen(false);
              }}
            >
              {m.type === 'local' ? <Cpu size={16} /> : <Cloud size={16} />}
              <div className="model-dropdown-label">{m.label}</div>
              <div className={`model-dropdown-tag ${m.type}`}>
                {m.type === 'local' ? 'Lokal' : 'Bulut'}
              </div>
            </div>
          ))}
          
          {models.find(m => m.provider === 'ollama') === undefined && (
            <div className="model-dropdown-item" style={{ opacity: 0.5 }}>
              <Server size={16} />
              <div className="model-dropdown-label">Ollama (Kapalı)</div>
              <div className="model-dropdown-tag local">Lokal</div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
