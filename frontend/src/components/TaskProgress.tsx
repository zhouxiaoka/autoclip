import React, { useState, useEffect } from 'react';
import { Progress, Card, Tag, Space, Typography, Spin } from 'antd';
import { PlayCircleOutlined, CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined } from '@ant-design/icons';

const { Text, Title } = Typography;

interface TaskProgressProps {
  projectId: string;
  taskId?: string;
  status: string;
  onProgressUpdate?: (progress: number, step: string) => void;
}

interface TaskProgressData {
  id: string;
  name: string;
  status: string;
  progress: number;
  current_step: string;
  realtime_progress?: number;
  realtime_step?: string;
  step_details?: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
}

const TaskProgress: React.FC<TaskProgressProps> = ({ 
  projectId, 
  taskId, 
  status, 
  onProgressUpdate 
}) => {
  const [progressData, setProgressData] = useState<TaskProgressData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 获取任务进度
  const fetchTaskProgress = async () => {
    if (!projectId) return;
    
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch(`/api/v1/progress/project/${projectId}`);
      if (!response.ok) {
        throw new Error('获取进度失败');
      }
      
      const data = await response.json();
      if (data.tasks && data.tasks.length > 0) {
        // 找到当前任务或第一个运行中的任务
        const currentTask = taskId 
          ? data.tasks.find((t: TaskProgressData) => t.id === taskId)
          : data.tasks.find((t: TaskProgressData) => t.status === 'running') || data.tasks[0];
        
        setProgressData(currentTask);
        
        // 通知父组件进度更新
        if (onProgressUpdate) {
          const progress = currentTask.realtime_progress || currentTask.progress;
          const step = currentTask.realtime_step || currentTask.current_step;
          onProgressUpdate(progress, step);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '未知错误');
    } finally {
      setLoading(false);
    }
  };

  // 定期更新进度
  useEffect(() => {
    if (status === 'processing') {
      // 立即获取一次
      fetchTaskProgress();
      
      // 每5秒更新一次
      const interval = setInterval(fetchTaskProgress, 5000);
      return () => clearInterval(interval);
    }
  }, [projectId, taskId, status]);

  // 获取状态图标和颜色
  const getStatusConfig = (status: string) => {
    switch (status) {
      case 'running':
        return { icon: <PlayCircleOutlined />, color: 'processing', text: '处理中' };
      case 'completed':
        return { icon: <CheckCircleOutlined />, color: 'success', text: '已完成' };
      case 'failed':
        return { icon: <CloseCircleOutlined />, color: 'error', text: '失败' };
      case 'pending':
        return { icon: <ClockCircleOutlined />, color: 'default', text: '等待中' };
      default:
        return { icon: <ClockCircleOutlined />, color: 'default', text: status };
    }
  };

  // 获取进度条状态
  const getProgressStatus = (status: string) => {
    switch (status) {
      case 'running':
        return 'active';
      case 'completed':
        return 'success';
      case 'failed':
        return 'exception';
      default:
        return 'normal';
    }
  };

  if (loading) {
    return (
      <Card size="small" style={{ marginBottom: 16 }}>
        <div style={{ textAlign: 'center', padding: '20px' }}>
          <Spin size="large" />
          <div style={{ marginTop: 16 }}>
            <Text>正在获取任务进度...</Text>
          </div>
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card size="small" style={{ marginBottom: 16 }}>
        <div style={{ textAlign: 'center', padding: '20px' }}>
          <CloseCircleOutlined style={{ fontSize: 24, color: '#ff4d4f' }} />
          <div style={{ marginTop: 16 }}>
            <Text type="danger">{error}</Text>
          </div>
        </div>
      </Card>
    );
  }

  if (!progressData) {
    return null;
  }

  const statusConfig = getStatusConfig(progressData.status);
  const progressStatus = getProgressStatus(progressData.status);
  const currentProgress = progressData.realtime_progress || progressData.progress;
  const currentStep = progressData.realtime_step || progressData.current_step;

  return (
    <Card size="small" style={{ marginBottom: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
        <Space>
          {statusConfig.icon}
          <Title level={5} style={{ margin: 0 }}>
            {progressData.name || '视频处理任务'}
          </Title>
          <Tag color={statusConfig.color}>
            {statusConfig.text}
          </Tag>
        </Space>
      </div>

      <div style={{ marginBottom: 16 }}>
        <Progress
          percent={currentProgress}
          status={progressStatus}
          strokeColor={{
            '0%': '#108ee9',
            '100%': '#87d068',
          }}
        />
      </div>

      <div style={{ marginBottom: 8 }}>
        <Text strong>当前步骤: </Text>
        <Text>{currentStep || '未知'}</Text>
      </div>

      {progressData.step_details && (
        <div style={{ marginBottom: 8 }}>
          <Text strong>详细信息: </Text>
          <Text type="secondary">{progressData.step_details}</Text>
        </div>
      )}

      <div style={{ fontSize: '12px', color: '#999' }}>
        <Space split={<Text type="secondary">|</Text>}>
          {progressData.created_at && (
            <Text type="secondary">
              创建: {new Date(progressData.created_at).toLocaleString()}
            </Text>
          )}
          {progressData.started_at && (
            <Text type="secondary">
              开始: {new Date(progressData.started_at).toLocaleString()}
            </Text>
          )}
          {progressData.completed_at && (
            <Text type="secondary">
              完成: {new Date(progressData.completed_at).toLocaleString()}
            </Text>
          )}
        </Space>
      </div>

      {status === 'processing' && (
        <div style={{ marginTop: 16, textAlign: 'center' }}>
          <Text type="secondary">进度每5秒自动更新</Text>
        </div>
      )}
    </Card>
  );
};

export default TaskProgress; 