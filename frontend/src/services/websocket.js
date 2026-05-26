import { getBrowserId, getToken } from './auth';

const MAX_RETRIES = 5;
const HEARTBEAT_INTERVAL = 30_000;

export class ChatWebSocket {
  constructor(onToken, onDone, onError, onTool, onOpen, onModelActive, onDisconnect, onApprovalRequest) {
    this.onToken = onToken;
    this.onDone = onDone;
    this.onError = onError;
    this.onTool = onTool;
    this.onOpen = onOpen;
    this.onModelActive = onModelActive;
    this.onDisconnect = onDisconnect;
    this.onApprovalRequest = onApprovalRequest;

    this.ws = null;
    this.isConnected = false;
    this._intentionalClose = false;
    this._retryCount = 0;
    this._retryTimer = null;
    this._heartbeatTimer = null;
    this._wsUrl = null;
  }

  connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const qs = new URLSearchParams();
    const token = getToken();
    if (token) qs.set('token', token);
    qs.set('browser_id', getBrowserId());
    this._wsUrl = `${protocol}//${window.location.host}/api/chat/ws?${qs.toString()}`;
    this._connect();
  }

  // Auth değişince bağlantıyı yeni kimlikle tazele
  reconnectWithAuth() {
    this._intentionalClose = true;
    if (this.ws) {
      try { this.ws.close(); } catch { /* yok say */ }
      this.ws = null;
    }
    this._stopHeartbeat();
    if (this._retryTimer) {
      clearTimeout(this._retryTimer);
      this._retryTimer = null;
    }
    this.isConnected = false;
    this._intentionalClose = false;
    this._retryCount = 0;
    this.connect();
  }

  _connect() {
    if (this._intentionalClose) return;

    this.ws = new WebSocket(this._wsUrl);

    this.ws.onopen = () => {
      this.isConnected = true;
      this._retryCount = 0;
      this.onOpen?.();
      this._startHeartbeat();
    };

    this.ws.onmessage = (event) => {
      let data;
      try {
        data = JSON.parse(event.data);
      } catch {
        this.onError('Sunucudan geçersiz veri alındı.');
        return;
      }

      if (data.type === 'pong') return;

      if (data.type === 'token') {
        this.onToken(data.content);
      } else if (data.type === 'done') {
        this.onDone(data.usage || null);
      } else if (data.type === 'model_active') {
        this.onModelActive?.(data);
      } else if (data.type === 'tool' || data.type === 'fallback' || data.type === 'routing') {
        this.onTool?.(data.content);
      } else if (data.type === 'error') {
        this.onError(data.content);
      } else if (data.type === 'approval_request') {
        this.onApprovalRequest?.(data);
      }
    };

    this.ws.onclose = () => {
      this.isConnected = false;
      this._stopHeartbeat();
      this.onDisconnect?.();
      if (!this._intentionalClose) {
        this._scheduleReconnect();
      }
    };

    this.ws.onerror = () => {
      // onclose her zaman onerror'dan sonra tetiklenir; reconnect oradan yönetilir
    };
  }

  _startHeartbeat() {
    this._stopHeartbeat();
    this._heartbeatTimer = setInterval(() => {
      if (this.isConnected && this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }));
      }
    }, HEARTBEAT_INTERVAL);
  }

  _stopHeartbeat() {
    if (this._heartbeatTimer) {
      clearInterval(this._heartbeatTimer);
      this._heartbeatTimer = null;
    }
  }

  _scheduleReconnect() {
    if (this._retryCount >= MAX_RETRIES) {
      this.onError('Sunucuya bağlanılamadı. Sayfayı yenileyin.');
      return;
    }
    const delay = Math.min(1000 * Math.pow(2, this._retryCount), 30_000);
    this._retryCount++;
    this._retryTimer = setTimeout(() => this._connect(), delay);
  }

  sendApproval(path, approved, sessionId, productId = 'forge', folder = '') {
    if (!this.isConnected) return;
    this.ws.send(JSON.stringify({
      type: 'approval_response',
      approved,
      path,
      folder,
      session_id: sessionId,
      product_id: productId,
    }));
  }

  sendMessage(message, sessionId, provider, model, history, routing = 'manual', productId = 'forge', orchestrate = false) {
    if (!sessionId) {
      this.onError('Aktif oturum yok. Soldaki "Yeni Sohbet" butonuna tıklayın.');
      return;
    }
    if (!this.isConnected) {
      this.onError('Sunucuya bağlı değilsiniz, yeniden bağlanılıyor…');
      return;
    }

    this.ws.send(JSON.stringify({
      message,
      session_id: sessionId,
      provider,
      model,
      routing: provider === 'auto' || model === 'auto' ? 'auto' : routing,
      history,
      product_id: productId,
      orchestrate,
    }));
  }

  disconnect() {
    this._intentionalClose = true;
    this._stopHeartbeat();
    if (this._retryTimer) {
      clearTimeout(this._retryTimer);
      this._retryTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.isConnected = false;
  }
}
