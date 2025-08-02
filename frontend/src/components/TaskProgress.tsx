import React from 'react';
import { Progress, Card, Tag, Space, Typography, Tooltip } from 'antd';
import { ClockCircleOutlined, CheckCircleOutlined, CloseCircleOutlined, ExclamationCircleOutlined } from '@ant-design/icons';
import { TaskStatus } from '../hooks/useTaskStatus';

const { Text, Paragraph } = Typography;

interface TaskProgressProps {
  task: TaskStatus;
  showDetails?: boolean;
}

const getStatusColor = (status: TaskStatus['status']) => {
  switch (status) {
    case 'pending':
      return 'default';
    case 'running':
      return 'processing';
    case 'completed':
      return 'success';
    case 'failed':
      return 'error';
    case 'cancelled':
      return 'default';
    default:
      return 'default';
  }
};

const getStatusIcon = (status: TaskStatus['status']) => {
  switch (status) {
    case 'pending':
      return <ClockCircleOutlined />;
    case 'running':
      return <ClockCircleOutlined spin />;
    case 'completed':
      return <CheckCircleOutlined />;
    case 'failed':
      return <CloseCircleOutlined />;
    case 'cancelled':
      return <ExclamationCircleOutlined />;
    default:
      return <ClockCircleOutlined />;
  }
};

const getStatusText = (status: TaskStatus['status']) => {
  switch (status) {
    case 'pending':
      return '等待中';
    case 'running':
      return '运行中';
    case 'completed':
      return '已完成';
    case 'failed':
      return '失败';
    case 'cancelled':
      return '已取消';
    default:
      return '未知';
  }
};

export const TaskProgress: React.FC<TaskProgressProps> = ({ task, showDetails = true }) => {
  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleString('zh-CN');
  };

  return (
    <Card 
      size="small" 
      style={{ marginBottom: 8 }}
      styles={{
        body: { padding: 12 }
      }}
    >
      <Space direction="vertical" style={{ width: '100%' }}>
        <Space style={{ width: '100%', justifyContent: 'space-between' }}>
          <Space>
            {getStatusIcon(task.status)}
            <Text strong>{task.id}</Text>
            <Tag color={getStatusColor(task.status)}>
              {getStatusText(task.status)}
            </Tag>
          </Space>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {formatTime(task.updatedAt)}
          </Text>
        </Space>

        <Progress 
          percent={task.progress} 
          status={task.status === 'failed' ? 'exception' : undefined}
          size="small"
          showInfo={false}
        />

        {showDetails && (
          <Space direction="vertical" style={{ width: '100%' }}>
            {task.message && (
              <Paragraph style={{ margin: 0, fontSize: 12 }}>
                {task.message}
              </Paragraph>
            )}
            
            {task.error && (
              <Tooltip title={task.error}>
                <Paragraph 
                  style={{ 
                    margin: 0, 
                    fontSize: 12, 
                    color: '#ff4d4f',
                    maxWidth: 200,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap'
                  }}
                >
                  错误: {task.error}
                </Paragraph>
              </Tooltip>
            )}
          </Space>
        )}
      </Space>
    </Card>
  );
}; 