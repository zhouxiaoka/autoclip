import React, { useEffect, useState, useCallback } from 'react';
import { Card, Row, Col, Statistic, Space, Tag, Button, Typography } from 'antd';
import { 
  WifiOutlined, 
  WifiOutlined as WifiDisconnectedOutlined,
  SyncOutlined,
  ExclamationCircleOutlined,
  ReloadOutlined
} from '@ant-design/icons';
import { TaskProgress } from './TaskProgress';
import { NotificationList } from './NotificationList';
import { useWebSocket, WebSocketEventMessage } from '../hooks/useWebSocket';
import { useNotifications } from '../hooks/useNotifications';

const { Text } = Typography;

interface RealTimeStatusProps {
  userId: string;
}

export const RealTimeStatus: React.FC<RealTimeStatusProps> = ({ userId }) => {
  console.log('🎬 RealTimeStatus组件已加载');
  
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  
  // 直接使用简单的状态管理，不使用复杂的Hook
  const loadProjectTasks = useCallback(async (projectId: string) => {
    console.log('📤 开始加载项目任务:', projectId);
    setLoading(true);
    try {
      const response = await fetch(`http://localhost:8000/api/v1/tasks/project/${projectId}`);
      console.log('📡 API响应状态:', response.status);
      
      if (response.ok) {
        const data = await response.json();
        const projectTasks = data.data.tasks || [];
        console.log('📋 获取到任务数量:', projectTasks.length);
        
        // 转换为TaskProgress组件期望的格式
        const formattedTasks = projectTasks.map((task: any) => ({
          id: task.task_id,
          status: task.status,
          progress: task.progress || 0,
          message: task.name,
          updatedAt: task.updated_at || new Date().toISOString()
        }));
        
        setTasks(formattedTasks);
      } else {
        console.error('❌ API调用失败:', response.status, response.statusText);
      }
    } catch (error) {
      console.error('❌ 加载项目任务失败:', error);
    } finally {
      setLoading(false);
      console.log('✅ 任务加载完成');
    }
  }, []);

  const {
    notifications,
    unreadCount,
    markAsRead,
    removeNotification,
    markAllAsRead,
    clearAll: clearAllNotifications,
    handleSystemNotification,
    handleErrorNotification
  } = useNotifications();

  const handleWebSocketMessage = (message: WebSocketEventMessage) => {
    console.log('收到WebSocket消息:', message);
    
    switch (message.type) {
      case 'task_update':
        // 暂时不处理任务更新，避免复杂的状态管理
        console.log('📈 收到任务更新:', message);
        break;
        
      case 'project_update':
        // 暂时不处理项目更新，避免复杂的状态管理
        console.log('📊 收到项目更新:', message);
        break;
        
      case 'system_notification':
        // 只处理重要的系统通知
        if (message.level === 'success' || message.level === 'error') {
          handleSystemNotification(message);
        }
        break;
        
      case 'error_notification':
        handleErrorNotification(message);
        break;
        
      default:
        console.log('忽略未知类型的WebSocket消息:', (message as any).type);
    }
  };

  // 启用WebSocket功能
  const {
    isConnected,
    connectionStatus,
    connect,
    disconnect,
    subscribeToTopic,
    unsubscribeFromTopic,
    sendMessage
  } = useWebSocket({
    userId,
    onMessage: handleWebSocketMessage
  });

  // 加载项目任务
  useEffect(() => {
    // 这里可以传入具体的项目ID，或者从props获取
    const projectId = '64d5768e-7b6b-40d0-9aed-f216768a6526'; // 示例项目ID
    console.log('🔄 开始加载项目任务:', projectId);
    loadProjectTasks(projectId);
  }, []); // 移除loadProjectTasks依赖，避免无限循环

  const getConnectionStatusColor = () => {
    switch (connectionStatus) {
      case 'connected': return 'success';
      case 'connecting': return 'processing';
      case 'disconnected': return 'default';
      case 'error': return 'error';
      default: return 'default';
    }
  };

  const getConnectionStatusText = () => {
    switch (connectionStatus) {
      case 'connected': return '已连接';
      case 'connecting': return '连接中';
      case 'disconnected': return '未连接';
      case 'error': return '连接错误';
      default: return '未知状态';
    }
  };

  const getConnectionIcon = () => {
    switch (connectionStatus) {
      case 'connected': return <WifiOutlined />;
      case 'connecting': return <SyncOutlined spin />;
      case 'disconnected': return <WifiDisconnectedOutlined />;
      case 'error': return <ExclamationCircleOutlined />;
      default: return <WifiDisconnectedOutlined />;
    }
  };

  return (
    <div style={{ padding: 16 }}>
      <Row gutter={[16, 16]}>
        {/* 连接状态 */}
        <Col span={24}>
          <Card size="small">
            <Space>
              {getConnectionIcon()}
              <Text>WebSocket状态: </Text>
              <Tag color={getConnectionStatusColor()}>
                {getConnectionStatusText()}
              </Tag>
              <Button 
                size="small" 
                icon={<ReloadOutlined />}
                onClick={isConnected ? disconnect : connect}
              >
                {isConnected ? '断开' : '连接'}
              </Button>
            </Space>
          </Card>
        </Col>

        {/* 统计信息 */}
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="任务总数"
              value={tasks.length}
              valueStyle={{ color: '#1890ff' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="加载状态"
              value={loading ? '加载中' : '已完成'}
              valueStyle={{ color: loading ? '#52c41a' : '#999' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="连接状态"
              value={isConnected ? '已连接' : '未连接'}
              valueStyle={{ color: isConnected ? '#722ed1' : '#ff4d4f' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="未读通知"
              value={unreadCount}
              valueStyle={{ color: unreadCount > 0 ? '#ff4d4f' : '#999' }}
            />
          </Card>
        </Col>

        {/* 任务进度 */}
        <Col span={12}>
          <Card 
            title="任务进度" 
            size="small"
            extra={
              <Button size="small" onClick={() => setTasks([])}>
                清空
              </Button>
            }
          >
            <div style={{ maxHeight: 300, overflowY: 'auto' }}>
              {tasks.length === 0 ? (
                <div style={{ textAlign: 'center', padding: 20, color: '#999' }}>
                  暂无任务
                </div>
              ) : (
                tasks.map((task, index) => (
                  <TaskProgress key={task.id || `task-${index}`} task={task} />
                ))
              )}
            </div>
          </Card>
        </Col>

        {/* 通知列表 */}
        <Col span={12}>
          <NotificationList
            notifications={notifications}
            unreadCount={unreadCount}
            onMarkAsRead={markAsRead}
            onRemove={removeNotification}
            onMarkAllAsRead={markAllAsRead}
            onClearAll={clearAllNotifications}
            maxHeight={300}
          />
        </Col>
      </Row>
    </div>
  );
}; 