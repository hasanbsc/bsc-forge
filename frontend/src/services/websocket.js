export class ChatWebSocket {
  constructor(onToken, onDone, onError) {
    this.ws = null;
    this.onToken = onToken;
    this.onDone = onDone;
    this.onError = onError;
    this.isConnected = false;
  }

  connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Vite proxy handles /api, but for WebSocket we connect directly or through proxy
    const wsUrl = `${protocol}//${window.location.host}/api/chat/ws`;
    
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.isConnected = true;
      console.log('WebSocket bağlandı');
    };

    this.ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'token') {
        this.onToken(data.content);
      } else if (data.type === 'done') {
        this.onDone();
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
      this.onError('Bağlantı hatası oluştu.');
    };
  }

  sendMessage(message, sessionId, provider, model, history) {
    if (!this.isConnected) {
      this.onError('Sunucuya bağlı değilsiniz.');
      return;
    }

    const payload = {
      message,
      session_id: sessionId,
      provider,
      model,
      history
    };

    this.ws.send(JSON.stringify(payload));
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}
