import React, { useState, useEffect } from 'react';
import { Badge, Tooltip, Button, Space, Typography } from 'antd';
import { 
  WifiOutlined, 
  WifiOutlined as WifiDisconnectedOutlined,
  ReloadOutlined
} from '@ant-design/icons';

const { Text } = Typography;

interface NetworkStatus {
  isOnline: boolean;
  lastCheck: string;
  connectionQuality: 'excellent' | 'good' | 'poor' | 'offline';
  latency?: number;
}

interface OfflineModeIndicatorProps {
  onStatusChange?: (status: NetworkStatus) => void;
}

const OfflineModeIndicator: React.FC<OfflineModeIndicatorProps> = ({ onStatusChange }) => {
  const [networkStatus, setNetworkStatus] = useState<NetworkStatus>({
    isOnline: navigator.onLine,
    lastCheck: new Date().toISOString(),
    connectionQuality: navigator.onLine ? 'good' : 'offline'
  });
  const [isChecking, setIsChecking] = useState(false);

  // 检查网络连接质量
  const checkConnectionQuality = async (): Promise<NetworkStatus> => {
    const startTime = Date.now();
    
    try {
      // 尝试访问健康检查端点
      const response = await fetch('/health', {
        method: 'GET',
        timeout: 5000
      } as any);
      
      const latency = Date.now() - startTime;
      
      if (response.ok) {
        let quality: 'excellent' | 'good' | 'poor' = 'good';
        if (latency < 100) quality = 'excellent';
        else if (latency > 500) quality = 'poor';
        
        return {
          isOnline: true,
          lastCheck: new Date().toISOString(),
          connectionQuality: quality,
          latency
        };
      } else {
        return {
          isOnline: false,
          lastCheck: new Date().toISOString(),
          connectionQuality: 'offline'
        };
      }
    } catch (error) {
      return {
        isOnline: false,
        lastCheck: new Date().toISOString(),
        connectionQuality: 'offline'
      };
    }
  };

  // 手动检查网络状态
  const handleCheckNetwork = async () => {
    setIsChecking(true);
    try {
      const status = await checkConnectionQuality();
      setNetworkStatus(status);
      onStatusChange?.(status);
    } catch (error) {
      console.error('网络检查失败:', error);
    } finally {
      setIsChecking(false);
    }
  };

  // 监听网络状态变化
  useEffect(() => {
    const handleOnline = () => {
      setNetworkStatus(prev => ({
        ...prev,
        isOnline: true,
        connectionQuality: 'good',
        lastCheck: new Date().toISOString()
      }));
    };

    const handleOffline = () => {
      setNetworkStatus(prev => ({
        ...prev,
        isOnline: false,
        connectionQuality: 'offline',
        lastCheck: new Date().toISOString()
      }));
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    // 定期检查网络质量
    const interval = setInterval(() => {
      if (navigator.onLine) {
        checkConnectionQuality().then(status => {
          setNetworkStatus(status);
          onStatusChange?.(status);
        });
      }
    }, 30000); // 每30秒检查一次

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
      clearInterval(interval);
    };
  }, [onStatusChange]);

  // 获取状态图标和颜色
  const getStatusIcon = () => {
    if (!networkStatus.isOnline) {
      return <WifiDisconnectedOutlined style={{ color: '#ff4d4f' }} />;
    }
    
    switch (networkStatus.connectionQuality) {
      case 'excellent':
        return <WifiOutlined style={{ color: '#52c41a' }} />;
      case 'good':
        return <WifiOutlined style={{ color: '#1890ff' }} />;
      case 'poor':
        return <WifiOutlined style={{ color: '#faad14' }} />;
      default:
        return <WifiOutlined style={{ color: '#d9d9d9' }} />;
    }
  };

  // 获取状态文本
  const getStatusText = () => {
    if (!networkStatus.isOnline) {
      return '离线模式';
    }
    
    switch (networkStatus.connectionQuality) {
      case 'excellent':
        return '网络优秀';
      case 'good':
        return '网络良好';
      case 'poor':
        return '网络较差';
      default:
        return '网络未知';
    }
  };

  // 获取状态描述
  const getStatusDescription = () => {
    if (!networkStatus.isOnline) {
      return '当前处于离线模式，部分功能可能受限';
    }
    
    const latencyText = networkStatus.latency ? `延迟: ${networkStatus.latency}ms` : '';
    const lastCheck = new Date(networkStatus.lastCheck).toLocaleTimeString();
    
    return `最后检查: ${lastCheck} ${latencyText}`.trim();
  };

  return (
    <Space>
      <Tooltip title={getStatusDescription()}>
        <Badge 
          status={networkStatus.isOnline ? 'success' : 'error'} 
          text={
            <Space>
              {getStatusIcon()}
              <Text type={networkStatus.isOnline ? 'success' : 'danger'}>
                {getStatusText()}
              </Text>
            </Space>
          }
        />
      </Tooltip>
      
      <Button
        type="text"
        size="small"
        icon={<ReloadOutlined spin={isChecking} />}
        onClick={handleCheckNetwork}
        loading={isChecking}
        title="检查网络状态"
        style={{
          color: '#ffffff',
          border: '1px solid transparent',
          borderRadius: '6px',
          height: '32px',
          width: '32px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'all 0.2s ease',
          backgroundColor: 'transparent'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.1)'
          e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.2)'
          e.currentTarget.style.transform = 'scale(1.05)'
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.backgroundColor = 'transparent'
          e.currentTarget.style.borderColor = 'transparent'
          e.currentTarget.style.transform = 'scale(1)'
        }}
        onMouseDown={(e) => {
          e.currentTarget.style.transform = 'scale(0.95)'
        }}
        onMouseUp={(e) => {
          e.currentTarget.style.transform = 'scale(1.05)'
        }}
      />
    </Space>
  );
};

export default OfflineModeIndicator;
