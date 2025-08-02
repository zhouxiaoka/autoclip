import { useEffect, useRef, useState, useCallback } from 'react';

export interface WebSocketMessage {
  type: string;
  timestamp: string;
  [key: string]: any;
}

export interface TaskUpdateMessage extends WebSocketMessage {
  type: 'task_update';
  task_id: string;
  status: string;
  progress?: number;
  message?: string;
  error?: string;
}

export interface ProjectUpdateMessage extends WebSocketMessage {
  type: 'project_update';
  project_id: string;
  status: string;
  progress?: number;
  message?: string;
}

export interface SystemNotificationMessage extends WebSocketMessage {
  type: 'system_notification';
  notification_type: string;
  title: string;
  message: string;
  level: 'info' | 'success' | 'warning' | 'error';
}

export interface ErrorNotificationMessage extends WebSocketMessage {
  type: 'error_notification';
  error_type: string;
  error_message: string;
  details?: any;
}

export type WebSocketEventMessage = 
  | TaskUpdateMessage 
  | ProjectUpdateMessage 
  | SystemNotificationMessage 
  | ErrorNotificationMessage;

interface UseWebSocketOptions {
  userId: string;
  onMessage?: (message: WebSocketEventMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

export const useWebSocket = (options: UseWebSocketOptions) => {
  const { userId, onMessage, onConnect, onDisconnect, onError } = options;
  const [isConnected, setIsConnected] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 3; // 减少重连次数
  const isConnectingRef = useRef(false); // 防止重复连接

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING || isConnectingRef.current) {
      return;
    }

    isConnectingRef.current = true;
    setConnectionStatus('connecting');
    const wsUrl = `ws://localhost:8000/api/v1/ws/${userId}`;
    
    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket连接已建立');
        setIsConnected(true);
        setConnectionStatus('connected');
        reconnectAttempts.current = 0;
        isConnectingRef.current = false;
        onConnect?.();
      };

      ws.onmessage = (event) => {
        try {
          const data: WebSocketEventMessage = JSON.parse(event.data);
          console.log('收到WebSocket消息:', data);
          onMessage?.(data);
        } catch (error) {
          console.error('解析WebSocket消息失败:', error);
        }
      };

      ws.onclose = (event) => {
        console.log('WebSocket连接已关闭:', event.code, event.reason);
        setIsConnected(false);
        setConnectionStatus('disconnected');
        isConnectingRef.current = false;
        onDisconnect?.();

        // 暂时禁用自动重连，避免疯狂重连
        // if (event.code !== 1000 && reconnectAttempts.current < maxReconnectAttempts) {
        //   reconnectAttempts.current++;
        //   const delay = Math.min(2000 * Math.pow(2, reconnectAttempts.current), 15000);
        //   console.log(`将在 ${delay}ms 后尝试重连 (${reconnectAttempts.current}/${maxReconnectAttempts})`);
        //   
        //   reconnectTimeoutRef.current = setTimeout(() => {
        //     connect();
        //   }, delay);
        // }
      };

      ws.onerror = (error) => {
        console.error('WebSocket错误:', error);
        setConnectionStatus('error');
        isConnectingRef.current = false;
        onError?.(error);
      };

    } catch (error) {
      console.error('创建WebSocket连接失败:', error);
      setConnectionStatus('error');
      isConnectingRef.current = false;
    }
  }, [userId]); // 移除回调函数依赖，避免无限重渲染

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    isConnectingRef.current = false;
    
    if (wsRef.current) {
      wsRef.current.close(1000, '用户主动断开连接');
      wsRef.current = null;
    }
    
    setIsConnected(false);
    setConnectionStatus('disconnected');
  }, []);

  const sendMessage = useCallback((message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
      return true;
    }
    console.warn('WebSocket未连接，无法发送消息');
    return false;
  }, []);

  const subscribeToTopic = useCallback((topic: string) => {
    return sendMessage({
      type: 'subscribe',
      topic
    });
  }, [sendMessage]);

  const unsubscribeFromTopic = useCallback((topic: string) => {
    return sendMessage({
      type: 'unsubscribe',
      topic
    });
  }, [sendMessage]);

  const ping = useCallback(() => {
    return sendMessage({
      type: 'ping'
    });
  }, [sendMessage]);

  const getStatus = useCallback(() => {
    return sendMessage({
      type: 'get_status'
    });
  }, [sendMessage]);

  // 自动连接 - 移除依赖，避免无限重渲染
  useEffect(() => {
    // 延迟连接，避免组件初始化时的重渲染
    const timer = setTimeout(() => {
      connect();
    }, 1000);

    return () => {
      clearTimeout(timer);
      disconnect();
    };
  }, []); // 移除依赖

  // 清理重连定时器
  useEffect(() => {
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
    };
  }, []);

  return {
    isConnected,
    connectionStatus,
    connect,
    disconnect,
    sendMessage,
    subscribeToTopic,
    unsubscribeFromTopic,
    ping,
    getStatus
  };
}; 