import React, { createContext, useContext, useState, useEffect, ReactNode, useRef, useCallback } from 'react';
import { AppState, AppStateStatus } from 'react-native';
import { API_CONFIG } from '../constants/api';
import { connectionDetector } from '../services/connectionDetector';
import { useHealthWebSocket } from '../hooks/useHealthWebSocket';

export type ConnectionStatus = 'connected' | 'disconnected' | 'maintenance' | 'checking';
export type ConnectionErrorType = 'network' | 'server' | 'unknown';

interface ConnectionContextType {
  connectionStatus: ConnectionStatus;
  isOnline: boolean;
  lastChecked: Date | null;
  checkConnection: () => Promise<void>;
  errorType: ConnectionErrorType;
  connectionRestoredAt: Date | null;
}

const ConnectionContext = createContext<ConnectionContextType | undefined>(undefined);

export const useConnection = () => {
  const context = useContext(ConnectionContext);
  if (!context) {
    throw new Error('useConnection must be used within ConnectionProvider');
  }
  return context;
};

interface ConnectionProviderProps {
  children: ReactNode;
}

export const ConnectionProvider: React.FC<ConnectionProviderProps> = ({ children }) => {
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('checking');
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const [errorType, setErrorType] = useState<ConnectionErrorType>('unknown');
  const [hasInternet, setHasInternet] = useState(false);
  const { isConnected: wsConnected, isHealthy } = useHealthWebSocket();
  const lastHealthCheckRef = useRef<number>(0);
  const HEALTH_CHECK_INTERVAL = 30000; // 30 segundos (reduzido de 5 segundos)
  const [connectionRestoredAt, setConnectionRestoredAt] = useState<Date | null>(null);
  const [isAppInBackground, setIsAppInBackground] = useState(false);
  const prevConnectionStatusRef = useRef<ConnectionStatus>('checking');

  const checkConnection = useCallback(async () => {
    try {
      setConnectionStatus('checking');

      // Verificar internet com controller separado para cada tentativa
      let currentHasInternet = false;
      
      // Tentativa 1: Google
      try {
        console.log('[ConnectionContext] Verificando internet (Google)...');
        const controller1 = new AbortController();
        const timeoutId1 = setTimeout(() => controller1.abort(), 3000);
        const internetCheck = await fetch('https://www.google.com/generate_204', {
          signal: controller1.signal,
          cache: 'no-store',
        });
        clearTimeout(timeoutId1);
        currentHasInternet = internetCheck.ok;
        setHasInternet(currentHasInternet);
        console.log('[ConnectionContext] Internet check (Google):', currentHasInternet);
      } catch (internetError) {
        console.log('[ConnectionContext] Google falhou, tentando Cloudflare...');
        
        // Tentativa 2: Cloudflare (com NOVO controller)
        try {
          const controller2 = new AbortController();
          const timeoutId2 = setTimeout(() => controller2.abort(), 3000);
          const cloudflareCheck = await fetch('https://cloudflare.com/cdn-cgi/trace', {
            signal: controller2.signal,
            cache: 'no-store',
          });
          clearTimeout(timeoutId2);
          currentHasInternet = cloudflareCheck.ok;
          setHasInternet(currentHasInternet);
          console.log('[ConnectionContext] Internet check (Cloudflare):', currentHasInternet);
        } catch (cloudflareError) {
          currentHasInternet = false;
          setHasInternet(false);
          console.log('[ConnectionContext] Sem internet (ambos falharam)');
        }
      }

      console.log('[ConnectionContext] hasInternet:', currentHasInternet);

      // Controller para verificação do backend
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);

      // Se não houver internet, não tentar verificar o backend
      if (!currentHasInternet) {
        console.log('[ConnectionContext] Sem internet, não verificando backend');
        setConnectionStatus('disconnected');
        setErrorType('network');
        clearTimeout(timeoutId);
        return;
      }

      // Agora verificar o backend
      console.log('[ConnectionContext] Verificando backend...');
      const connectionMethod = await connectionDetector.detectConnectionMethod();

      if (!connectionMethod.reachable) {
        console.log('[ConnectionContext] Nenhum método de conexão disponível');
        setConnectionStatus('disconnected');
        setErrorType('server');
        clearTimeout(timeoutId);
        return;
      }

      const response = await fetch(`${connectionMethod.url}${API_CONFIG.API_PREFIX}/maintenance/status`, {
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (response.ok) {
        const data = await response.json();
        setLastChecked(new Date());

        if (data.is_under_maintenance) {
          setConnectionStatus('maintenance');
        } else {
          setConnectionStatus('connected');
          setRetryCount(0);
          setErrorType('unknown');
        }
      } else {
        // Se o servidor respondeu com erro mas há internet, é erro de servidor
        if (currentHasInternet) {
          console.log('[ConnectionContext] Backend indisponível (tem internet)');
          setConnectionStatus('disconnected');
          setErrorType('server');
        } else {
          // Sem internet
          console.log('[ConnectionContext] Sem internet');
          setConnectionStatus('disconnected');
          setErrorType('network');
        }
      }
    } catch (error) {
      console.log('[ConnectionContext] Erro na verificação:', error);

      // Não logar erro se foi abortado (timeout esperado)
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('[ConnectionContext] Timeout - verificando internet novamente...');
        // Timeout - verificar internet novamente para garantir que o valor está atualizado
        let currentHasInternet = false;
        try {
          const internetCheck = await fetch('https://www.google.com/generate_204', {
            cache: 'no-store',
          });
          currentHasInternet = internetCheck.ok;
          console.log('[ConnectionContext] Internet check (Google):', currentHasInternet);
        } catch (internetError) {
          try {
            const cloudflareCheck = await fetch('https://cloudflare.com/cdn-cgi/trace', {
              cache: 'no-store',
            });
            currentHasInternet = cloudflareCheck.ok;
            console.log('[ConnectionContext] Internet check (Cloudflare):', currentHasInternet);
          } catch (cloudflareError) {
            currentHasInternet = false;
            console.log('[ConnectionContext] Sem internet (ambos falharam)');
          }
        }

        if (currentHasInternet) {
          // Há internet mas o backend não respondeu - erro de servidor
          console.log('[ConnectionContext] Timeout mas tem internet - servidor indisponível');
          setConnectionStatus('disconnected');
          setErrorType('server');
        } else {
          // Sem internet
          console.log('[ConnectionContext] Timeout sem internet');
          setConnectionStatus('disconnected');
          setErrorType('network');
        }
      } else if (error instanceof TypeError && error.message.includes('Network request failed')) {
        console.log('[ConnectionContext] Network request failed - verificando internet novamente...');
        // Erro de rede - verificar internet novamente para garantir que o valor está atualizado
        let currentHasInternet = false;
        try {
          const internetCheck = await fetch('https://www.google.com/generate_204', {
            cache: 'no-store',
          });
          currentHasInternet = internetCheck.ok;
          console.log('[ConnectionContext] Internet check (Google):', currentHasInternet);
        } catch (internetError) {
          try {
            const cloudflareCheck = await fetch('https://cloudflare.com/cdn-cgi/trace', {
              cache: 'no-store',
            });
            currentHasInternet = cloudflareCheck.ok;
            console.log('[ConnectionContext] Internet check (Cloudflare):', currentHasInternet);
          } catch (cloudflareError) {
            currentHasInternet = false;
            console.log('[ConnectionContext] Sem internet (ambos falharam)');
          }
        }

        if (currentHasInternet) {
          // Há internet mas o backend não respondeu - erro de servidor
          console.log('[ConnectionContext] Network request failed mas tem internet - servidor indisponível');
          setConnectionStatus('disconnected');
          setErrorType('server');
        } else {
          // Sem internet
          console.log('[ConnectionContext] Network request failed sem internet');
          setConnectionStatus('disconnected');
          setErrorType('network');
        }
      } else {
        console.error('[ConnectionContext] Erro ao verificar conexão:', error);
        setConnectionStatus('disconnected');
        setErrorType('network');
      }
    }
  }, []);

  // Monitorar quando a conexão é restaurada (de disconnected para connected)
  useEffect(() => {
    const prevStatus = prevConnectionStatusRef.current;
    const currentStatus = connectionStatus;
    
    // Se estava desconectado e agora está conectado
    if (prevStatus === 'disconnected' && currentStatus === 'connected') {
      console.log('[ConnectionContext] Conexão restaurada! Notificando telas...');
      setConnectionRestoredAt(new Date());
    }
    
    // Atualizar ref para próxima comparação
    prevConnectionStatusRef.current = currentStatus;
  }, [connectionStatus]);

  // Monitorar status de health via WebSocket
  useEffect(() => {
    if (wsConnected && isHealthy !== null) {
      // WebSocket conectado e recebendo status - atualizar conexão
      if (isHealthy) {
        setConnectionStatus('connected');
        setRetryCount(0);
        setErrorType('unknown');
      } else {
        setConnectionStatus('disconnected');
        setErrorType('server');
      }
      setLastChecked(new Date());
    }
  }, [wsConnected, isHealthy]);

  useEffect(() => {
    let intervalId: NodeJS.Timeout;

    const startChecking = () => {
      // Não fazer polling se o app estiver em background
      if (isAppInBackground) {
        console.log('[ConnectionContext] App em background, pausando verificação de conexão');
        return;
      }
      
      // Só fazer polling se WebSocket não estiver conectado
      if (!wsConnected) {
        checkConnection();
        
        // Verificar a cada 30 segundos (reduzido de 5 segundos)
        intervalId = setInterval(() => {
          // Não verificar se app estiver em background
          if (isAppInBackground) {
            console.log('[ConnectionContext] App em background, pulando verificação');
            return;
          }
          
          // Evitar verificações muito frequentes
          const now = Date.now();
          if (now - lastHealthCheckRef.current >= HEALTH_CHECK_INTERVAL) {
            checkConnection();
            lastHealthCheckRef.current = now;
          }
        }, HEALTH_CHECK_INTERVAL);
      } else {
        // WebSocket conectado - verificar apenas a cada 5 minutos como fallback
        intervalId = setInterval(() => {
          // Não verificar se app estiver em background
          if (isAppInBackground) {
            console.log('[ConnectionContext] App em background, pulando verificação fallback');
            return;
          }
          checkConnection();
        }, 300000); // 5 minutos
      }
    };

    startChecking();

    return () => {
      clearInterval(intervalId);
    };
  }, [wsConnected, isAppInBackground]);

  // Implementar retry com backoff exponencial quando desconectado
  useEffect(() => {
    if (connectionStatus === 'disconnected' && !isAppInBackground) {
      const backoffDelay = Math.min(1000 * Math.pow(2, retryCount), 30000); // Max 30s
      
      const retryTimeout = setTimeout(() => {
        setRetryCount(prev => prev + 1);
        checkConnection();
      }, backoffDelay);

      return () => clearTimeout(retryTimeout);
    }
  }, [connectionStatus, retryCount, isAppInBackground]);

  // Monitorar estado do app (foreground/background)
  useEffect(() => {
    const handleAppStateChange = (nextAppState: AppStateStatus) => {
      if (nextAppState === 'background' || nextAppState === 'inactive') {
        console.log('[ConnectionContext] App foi para background');
        setIsAppInBackground(true);
      } else if (nextAppState === 'active') {
        console.log('[ConnectionContext] App voltou para foreground');
        setIsAppInBackground(false);
        // Forçar verificação imediata ao voltar
        checkConnection();
      }
    };

    const subscription = AppState.addEventListener('change', handleAppStateChange);

    return () => {
      subscription.remove();
    };
  }, [checkConnection]);

  const isOnline = connectionStatus === 'connected';

  return (
    <ConnectionContext.Provider value={{ connectionStatus, isOnline, lastChecked, checkConnection, errorType, connectionRestoredAt }}>
      {children}
    </ConnectionContext.Provider>
  );
};
