import { API_CONFIG } from '../constants/api';

interface ConnectionMethod {
  reachable: boolean;
  url: string;
  method: 'websocket' | 'http' | null;
}

class ConnectionDetector {
  private lastCheck: number = 0;
  private cacheDuration: number = 5000; // 5 seconds
  private cachedResult: ConnectionMethod | null = null;

  async detectConnectionMethod(): Promise<ConnectionMethod> {
    // Return cached result if still valid
    const now = Date.now();
    if (this.cachedResult && now - this.lastCheck < this.cacheDuration) {
      return this.cachedResult;
    }

    // Try HTTP connection first
    const httpUrl = API_CONFIG.BASE_URL;
    
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000);
      
      const response = await fetch(`${httpUrl}/health`, {
        method: 'GET',
        signal: controller.signal,
        cache: 'no-store',
      });
      
      clearTimeout(timeoutId);
      
      if (response.ok) {
        this.cachedResult = {
          reachable: true,
          url: httpUrl,
          method: 'http'
        };
        this.lastCheck = now;
        return this.cachedResult;
      }
    } catch (error) {
      console.log('[ConnectionDetector] HTTP connection failed:', error);
    }

    // Try WebSocket endpoint
    const wsUrl = API_CONFIG.WS_URL;
    if (wsUrl) {
      try {
        const ws = new WebSocket(wsUrl);
        const wsPromise = new Promise<boolean>((resolve) => {
          ws.onopen = () => {
            ws.close();
            resolve(true);
          };
          ws.onerror = () => resolve(false);
          ws.onclose = () => resolve(false);
          
          // Timeout after 3 seconds
          setTimeout(() => {
            if (ws.readyState === WebSocket.CONNECTING) {
              ws.close();
              resolve(false);
            }
          }, 3000);
        });

        const wsReachable = await wsPromise;
        
        if (wsReachable) {
          this.cachedResult = {
            reachable: true,
            url: wsUrl.replace('ws://', 'http://').replace('wss://', 'https://'),
            method: 'websocket'
          };
          this.lastCheck = now;
          return this.cachedResult;
        }
      } catch (error) {
        console.log('[ConnectionDetector] WebSocket connection failed:', error);
      }
    }

    // No connection method available
    this.cachedResult = {
      reachable: false,
      url: '',
      method: null
    };
    this.lastCheck = now;
    return this.cachedResult;
  }

  clearCache(): void {
    this.cachedResult = null;
    this.lastCheck = 0;
  }
}

export const connectionDetector = new ConnectionDetector();
