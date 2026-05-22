const API_BASE_URL = '/api';

export const fetchSessions = async (product = null) => {
  const url = product ? `${API_BASE_URL}/chat/sessions?product=${product}` : `${API_BASE_URL}/chat/sessions`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Oturumlar getirilemedi');
  return await res.json();
};

export const createSession = async (title = 'Yeni Sohbet', product = 'forge') => {
  const res = await fetch(`${API_BASE_URL}/chat/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, product }),
  });
  if (!res.ok) throw new Error('Oturum oluşturulamadı');
  return await res.json();
};

export const fetchSessionMessages = async (sessionId) => {
  const res = await fetch(`${API_BASE_URL}/chat/sessions/${sessionId}/messages`);
  if (!res.ok) throw new Error('Mesajlar getirilemedi');
  return await res.json();
};

export const fetchModels = async () => {
  const res = await fetch(`${API_BASE_URL}/models`);
  if (!res.ok) throw new Error('Modeller getirilemedi');
  return await res.json();
};
