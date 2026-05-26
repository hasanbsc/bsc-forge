// BSC Forge — Üyelik (Auth) servisi
//
// Token ve browser_id localStorage'da saklanır.
// browser_id, anonim sohbetlerin kullanıcıya bağlanabilmesi için ilk açılışta
// üretilir ve kalıcı tutulur.

const TOKEN_KEY = 'bsc.auth_token';
const BROWSER_ID_KEY = 'bsc.browser_id';

export const getToken = () => {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
};

export const setToken = (token) => {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage erişim hatası — sessiz geç */
  }
};

export const clearToken = () => setToken(null);

const generateBrowserId = () => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
  // Fallback (eski tarayıcılar)
  return 'brw-' + Math.random().toString(36).slice(2) + Date.now().toString(36);
};

export const getBrowserId = () => {
  try {
    let id = localStorage.getItem(BROWSER_ID_KEY);
    if (!id) {
      id = generateBrowserId();
      localStorage.setItem(BROWSER_ID_KEY, id);
    }
    return id;
  } catch {
    // localStorage yoksa session bazlı geçici ID
    return generateBrowserId();
  }
};

// ── REST çağrıları ──

const parseError = async (res) => {
  try {
    const body = await res.json();
    if (typeof body.detail === 'string') return body.detail;
    if (Array.isArray(body.detail) && body.detail[0]?.msg) return body.detail[0].msg;
  } catch {
    /* JSON parse edilemiyorsa düş */
  }
  return `İstek başarısız (HTTP ${res.status})`;
};

export const register = async (email, password) => {
  const res = await fetch('/api/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return await res.json();
};

export const login = async (email, password) => {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return await res.json();
};

export const fetchMe = async () => {
  const token = getToken();
  if (!token) return null;
  const res = await fetch('/api/auth/me', {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (res.status === 401) {
    clearToken();
    return null;
  }
  if (!res.ok) throw new Error(await parseError(res));
  const data = await res.json();
  return data.user;
};

export const claimAnonymous = async (browserId) => {
  const token = getToken();
  if (!token) return { claimed: 0 };
  const res = await fetch('/api/auth/claim-anonymous', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ browser_id: browserId }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return await res.json();
};

// Tüm REST/WS çağrıları için ortak header üretici
export const authHeaders = () => {
  const headers = { 'X-Browser-Id': getBrowserId() };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
};
