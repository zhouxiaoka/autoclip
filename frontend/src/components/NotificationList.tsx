import React from 'react';
import { List, Card, Tag, Space, Typography, Button, Badge } from 'antd';
import { 
  InfoCircleOutlined, 
  CheckCircleOutlined, 
  ExclamationCircleOutlined, 
  CloseCircleOutlined,
  DeleteOutlined,
  CheckOutlined
} from '@ant-design/icons';
import { Notification } from '../hooks/useNotifications';

const { Text, Paragraph } = Typography;

interface NotificationListProps {
  notifications: Notification[];
  unreadCount: number;
  onMarkAsRead: (id: string) => void;
  onRemove: (id: string) => void;
  onMarkAllAsRead: () => void;
  onClearAll: () => void;
  maxHeight?: number;
}

const getNotificationIcon = (level: Notification['level']) => {
  switch (level) {
    case 'info':
      return <InfoCircleOutlined style={{ color: '#1890ff' }} />;
    case 'success':
      return <CheckCircleOutlined style={{ color: '#52c41a' }} />;
    case 'warning':
      return <ExclamationCircleOutlined style={{ color: '#faad14' }} />;
    case 'error':
      return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />;
    default:
      return <InfoCircleOutlined />;
  }
};

const getNotificationColor = (level: Notification['level']) => {
  switch (level) {
    case 'info':
      return 'blue';
    case 'success':
      return 'green';
    case 'warning':
      return 'orange';
    case 'error':
      return 'red';
    default:
      return 'default';
  }
};

const formatTime = (timestamp: string) => {
  const date = new Date(timestamp);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  
  if (diff < 60000) { // 1分钟内
    return '刚刚';
  } else if (diff < 3600000) { // 1小时内
    return `${Math.floor(diff / 60000)}分钟前`;
  } else if (diff < 86400000) { // 24小时内
    return `${Math.floor(diff / 3600000)}小时前`;
  } else {
    return date.toLocaleDateString('zh-CN');
  }
};

export const NotificationList: React.FC<NotificationListProps> = ({
  notifications,
  unreadCount,
  onMarkAsRead,
  onRemove,
  onMarkAllAsRead,
  onClearAll,
  maxHeight = 400
}) => {
  const renderNotification = (notification: Notification) => (
    <List.Item
      key={notification.id}
      style={{
        padding: '8px 0',
        opacity: notification.read ? 0.7 : 1,
        backgroundColor: notification.read ? '#f5f5f5' : 'transparent',
        borderRadius: 4,
        marginBottom: 4
      }}
      actions={[
        <Button
          key="read"
          type="text"
          size="small"
          icon={<CheckOutlined />}
          onClick={() => onMarkAsRead(notification.id)}
          disabled={notification.read}
        >
          标记已读
        </Button>,
        <Button
          key="remove"
          type="text"
          size="small"
          danger
          icon={<DeleteOutlined />}
          onClick={() => onRemove(notification.id)}
        >
          删除
        </Button>
      ]}
    >
      <List.Item.Meta
        avatar={getNotificationIcon(notification.level)}
        title={
          <Space>
            <Text strong={!notification.read}>
              {notification.title}
            </Text>
            <Tag color={getNotificationColor(notification.level)}>
              {notification.level}
            </Tag>
            {!notification.read && <Badge status="processing" />}
          </Space>
        }
        description={
          <Space direction="vertical" style={{ width: '100%' }}>
            <Paragraph style={{ margin: 0, fontSize: 12 }}>
              {notification.message}
            </Paragraph>
            <Text type="secondary" style={{ fontSize: 11 }}>
              {formatTime(notification.timestamp)}
            </Text>
          </Space>
        }
      />
    </List.Item>
  );

  return (
    <Card
      title={
        <Space>
          <span>通知</span>
          {unreadCount > 0 && (
            <Badge count={unreadCount} size="small" />
          )}
        </Space>
      }
      extra={
        <Space>
          {unreadCount > 0 && (
            <Button size="small" onClick={onMarkAllAsRead}>
              全部已读
            </Button>
          )}
          <Button size="small" danger onClick={onClearAll}>
            清空
          </Button>
        </Space>
      }
      styles={{
        body: { padding: 12 }
      }}
    >
      <div style={{ maxHeight, overflowY: 'auto' }}>
        {notifications.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 20, color: '#999' }}>
            暂无通知
          </div>
        ) : (
          <List
            dataSource={notifications}
            renderItem={renderNotification}
            pagination={false}
          />
        )}
      </div>
    </Card>
  );
}; 