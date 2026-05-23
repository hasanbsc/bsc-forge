export class ChatWebSocket {
  constructor(onToken, onDone, onError, onTool, onOpen, onModelActive) {
    this.ws = null;
    this.onToken = onToken;
    this.onDone = onDone;
    this.onError = onError;
    this.onTool = onTool;
    this.onOpen = onOpen;
    this.onModelActive = onModelActive;
    this.isConnected = false;
    this._intentionalClose = false;
  }

  connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Vite proxy handles /api, but for WebSocket we connect directly or through proxy
    const wsUrl = `${protocol}//${window.location.host}/api/chat/ws`;
    
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.isConnected = true;
      this.onOpen?.();
      console.log('WebSocket bağlandı');
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'token') {
        this.onToken(data.content);
      } else if (data.type === 'done') {
        this.onDone();
      } else if (data.type === 'model_active') {
        this.onModelActive?.(data);
      } else if (data.type === 'tool' || data.type === 'fallback' || data.type === 'routing') {
        this.onTool?.(data.content);
      } else if (data.type === 'error') {
        this.onError(data.content);
      }
    };

    this.ws.onclose = () => {
      this.isConnected = false;
      console.log('WebSocket bağlantısı koptu');
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket hatası:', error);
      if (!this._intentionalClose && !this.isConnected) {
        this.onError('Bağlantı hatası oluştu.');
      }
    };
  }

  sendMessage(message, sessionId, provider, model, history, routing = 'manual') {
    if (!this.isConnected) {
      this.onError('Sunucuya bağlı değilsiniz.');
      return;
    }

    const payload = {
      message,
      session_id: sessionId,
      provider,
      model,
      routing: provider === 'auto' || model === 'auto' ? 'auto' : routing,
      history
    };

    this.ws.send(JSON.stringify(payload));
  }

  disconnect() {
    if (this.ws) {
      this._intentionalClose = true;
      this.ws.close();
      this.ws = null;
    }
    this.isConnected = false;
  }
}
