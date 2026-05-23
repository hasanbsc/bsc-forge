import React, { useState } from 'react';
import { Plus, Trash2, Zap } from 'lucide-react';
import { createProduct, deleteProduct } from '../services/api';

const TOOL_LABELS = {
  list_directory: '📂 Klasör listele',
  read_file: '📄 Dosya oku',
};

function ProductCard({ product, onStart, onDelete }) {
  return (
    <div className="product-card">
      <div className="product-card-header">
        <span className="product-icon">{product.icon}</span>
        {product.is_builtin && <span className="product-badge">Yerleşik</span>}
      </div>
      <h3 className="product-name">{product.name}</h3>
      <p className="product-desc">{product.description}</p>
      {product.tools_enabled.length > 0 && (
        <div className="product-tools">
          {product.tools_enabled.map(t => (
            <span key={t} className="product-tool-tag">
              {TOOL_LABELS[t] || t}
            </span>
          ))}
        </div>
      )}
      <div className="product-card-actions">
        <button className="product-start-btn" onClick={() => onStart(product)}>
          <Zap size={14} /> Başlat
        </button>
        {!product.is_builtin && (
          <button
            className="product-delete-btn"
            title="Sil"
            onClick={() => onDelete(product)}
          >
            <Trash2 size={14} />
          </button>
        )}
      </div>
    </div>
  );
}

export default function ProductsPage({ products, setProducts, onStartProduct }) {
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: '',
    description: '',
    icon: '🤖',
    system_prompt: '',
    tools_enabled: [],
    preferred_provider: 'auto',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const toggleTool = (tool) => {
    setForm(prev => ({
      ...prev,
      tools_enabled: prev.tools_enabled.includes(tool)
        ? prev.tools_enabled.filter(t => t !== tool)
        : [...prev.tools_enabled, tool],
    }));
  };

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      const newProduct = await createProduct({
        ...form,
        system_prompt: form.system_prompt.trim() || null,
      });
      setProducts(prev => [...prev, newProduct]);
      setShowForm(false);
      setForm({ name: '', description: '', icon: '🤖', system_prompt: '', tools_enabled: [], preferred_provider: 'auto' });
    } catch (err) {
      setError('Ürün oluşturulamadı: ' + err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (product) => {
    if (!window.confirm(`"${product.name}" ürününü silmek istediğine emin misin?`)) return;
    try {
      await deleteProduct(product.id);
      setProducts(prev => prev.filter(p => p.id !== product.id));
    } catch (err) {
      setError('Silinemedi: ' + err.message);
    }
  };

  return (
    <div className="products-page">
      <div className="products-header">
        <div>
          <h2 className="products-title">Ürünler</h2>
          <p className="products-subtitle">Özelleştirilmiş yapay zeka asistanları</p>
        </div>
        <button className="product-new-btn" onClick={() => setShowForm(true)}>
          <Plus size={15} /> Yeni Ürün
        </button>
      </div>

      {error && (
        <div className="products-error">
          {error}
          <button onClick={() => setError(null)}>×</button>
        </div>
      )}

      {showForm && (
        <form className="product-form" onSubmit={handleCreate}>
          <div className="product-form-header">
            <h3>Yeni Ürün Oluştur</h3>
            <button type="button" className="product-form-close" onClick={() => setShowForm(false)}>×</button>
          </div>
          <div className="product-form-row">
            <input
              className="product-form-icon-input"
              value={form.icon}
              onChange={e => setForm(prev => ({ ...prev, icon: e.target.value }))}
              placeholder="🤖"
              maxLength={2}
            />
            <input
              className="product-form-input"
              placeholder="Ürün adı *"
              value={form.name}
              onChange={e => setForm(prev => ({ ...prev, name: e.target.value }))}
              required
            />
          </div>
          <input
            className="product-form-input"
            placeholder="Açıklama"
            value={form.description}
            onChange={e => setForm(prev => ({ ...prev, description: e.target.value }))}
          />
          <textarea
            className="product-form-textarea"
            placeholder="Sistem promptu (boş bırakırsan Forge varsayılanı kullanılır)"
            value={form.system_prompt}
            onChange={e => setForm(prev => ({ ...prev, system_prompt: e.target.value }))}
            rows={4}
          />
          <div className="product-form-tools">
            <span className="product-form-label">Araçlar:</span>
            {Object.entries(TOOL_LABELS).map(([tool, label]) => (
              <label key={tool} className="product-tool-checkbox">
                <input
                  type="checkbox"
                  checked={form.tools_enabled.includes(tool)}
                  onChange={() => toggleTool(tool)}
                />
                {label}
              </label>
            ))}
          </div>
          <div className="product-form-actions">
            <button type="submit" className="product-start-btn" disabled={saving}>
              {saving ? 'Kaydediliyor…' : 'Oluştur'}
            </button>
            <button type="button" className="product-cancel-btn" onClick={() => setShowForm(false)}>
              İptal
            </button>
          </div>
        </form>
      )}

      <div className="products-grid">
        {products.map(product => (
          <ProductCard
            key={product.id}
            product={product}
            onStart={onStartProduct}
            onDelete={handleDelete}
          />
        ))}
      </div>
    </div>
  );
}
