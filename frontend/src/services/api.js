import { authHeaders } from './auth';

const API_BASE_URL = '/api';

const headersJson = () => ({
  'Content-Type': 'application/json',
  ...authHeaders(),
});

export const fetchSessions = async (product = null) => {
  const url = product ? `${API_BASE_URL}/chat/sessions?product=${product}` : `${API_BASE_URL}/chat/sessions`;
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) throw new Error('Oturumlar getirilemedi');
  return await res.json();
};

export const createSession = async (title = 'Yeni Sohbet', product = 'forge') => {
  const res = await fetch(`${API_BASE_URL}/chat/sessions`, {
    method: 'POST',
    headers: headersJson(),
    body: JSON.stringify({ title, product }),
  });
  if (!res.ok) throw new Error('Oturum oluşturulamadı');
  return await res.json();
};

export const fetchSessionMessages = async (sessionId) => {
  const res = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}/messages`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error('Mesajlar getirilemedi');
  return await res.json();
};

export const deleteSession = async (sessionId) => {
  const res = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error('Sohbet silinemedi');
  return await res.json();
};

export const fetchModels = async () => {
  const res = await fetch(`${API_BASE_URL}/models`);
  if (!res.ok) throw new Error('Modeller getirilemedi');
  return await res.json();
};

export const fetchProducts = async () => {
  const res = await fetch(`${API_BASE_URL}/products`);
  if (!res.ok) throw new Error('Ürünler getirilemedi');
  return await res.json();
};

export const createProduct = async (data) => {
  const res = await fetch(`${API_BASE_URL}/products`, {
    method: 'POST',
    headers: headersJson(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Ürün oluşturulamadı');
  return await res.json();
};

export const deleteProduct = async (productId) => {
  const res = await fetch(`${API_BASE_URL}/products/${productId}`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error('Ürün silinemedi');
  return await res.json();
};
