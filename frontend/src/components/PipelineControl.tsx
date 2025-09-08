import React, { useState, useEffect } from 'react';
import { Card, Button, Space, Typography, Alert, Spin, Progress, Tag, List, Modal, message } from 'antd';
import { 
  PlayCircleOutlined, 
  PauseCircleOutlined, 
  ReloadOutlined, 
  EyeOutlined,
  RocketOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined
} from '@ant-design/icons';

const { Title, Text } = Typography;

interface PipelineControlProps {
  projectId: string;
  onStatusChange?: (status: string) => void;
}

interface TaskInfo {
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

interface PipelineStatus {
  project_id: string;
  project_status: string;
  tasks: TaskInfo[];
  total_tasks: number;
  running_tasks: number;
  completed_tasks: number;
  failed_tasks: number;
}

const PipelineControl: React.FC<PipelineControlProps> = ({ 
  projectId, 
  onStatusChange 
}) => {
  const [pipelineStatus, setPipelineStatus] = useState<PipelineStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusModalVisible, setStatusModalVisible] = useState(false);

  // 获取流水线状态
  const fetchPipelineStatus = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch(`http://localhost:8000/api/v1/pipeline/status/${projectId}`);
      if (!response.ok) {
        throw new Error('获取流水线状态失败');
      }
      
      const data = await response.json();
      setPipelineStatus(data);
      
      // 通知父组件状态变化
      if (onStatusChange) {
        onStatusChange(data.project_status);
      }
      
    } catch (err) {
      setError(err instanceof Error ? err.message : '未知错误');
    } finally {
      setLoading(false);
    }
  };

  // 启动流水线
  const startPipeline = async () => {
    try {
      setActionLoading(true);
      
      const response = await fetch(`http://localhost:8000/api/v1/pipeline/start/${projectId}`, {
        method: 'POST'
      });
      
      if (!response.ok) {
        throw new Error('启动流水线失败');
      }
      
      const result = await response.json();
      message.success(result.message);
      
      // 刷新状态
      await fetchPipelineStatus();
      
    } catch (err) {
      message.error(err instanceof Error ? err.message : '启动失败');
    } finally {
      setActionLoading(false);
    }
  };

  // 停止流水线
  const stopPipeline = async () => {
    try {
      setActionLoading(true);
      
      const response = await fetch(`http://localhost:8000/api/v1/pipeline/stop/${projectId}`, {
        method: 'POST'
      });
      
      if (!response.ok) {
        throw new Error('停止流水线失败');
      }
      
      const result = await response.json();
      message.success(result.message);
      
      // 刷新状态
      await fetchPipelineStatus();
      
    } catch (err) {
      message.error(err instanceof Error ? err.message : '停止失败');
    } finally {
      setActionLoading(false);
    }
  };

  // 重启流水线
  const restartPipeline = async () => {
    try {
      setActionLoading(true);
      
      const response = await fetch(`http://localhost:8000/api/v1/pipeline/restart/${projectId}`, {
        method: 'POST'
      });
      
      if (!response.ok) {
        throw new Error('重启流水线失败');
      }
      
      const result = await response.json();
      message.success(result.message);
      
      // 刷新状态
      await fetchPipelineStatus();
      
    } catch (err) {
      message.error(err instanceof Error ? err.message : '重启失败');
    } finally {
      setActionLoading(false);
    }
  };

  // 定期刷新状态
  useEffect(() => {
    if (projectId) {
      fetchPipelineStatus();
      
      // 每10秒刷新一次
      const interval = setInterval(fetchPipelineStatus, 10000);
      return () => clearInterval(interval);
    }
  }, [projectId]);

  // 获取状态配置
  const getStatusConfig = (status: string) => {
    switch (status) {
      case 'processing':
        return { color: 'processing', text: '处理中', icon: <PlayCircleOutlined /> };
      case 'completed':
        return { color: 'success', text: '已完成', icon: <CheckCircleOutlined /> };
      case 'failed':
        return { color: 'error', text: '失败', icon: <CloseCircleOutlined /> };
      case 'pending':
        return { color: 'default', text: '等待中', icon: <ClockCircleOutlined /> };
      case 'paused':
        return { color: 'warning', text: '已暂停', icon: <PauseCircleOutlined /> };
      default:
        return { color: 'default', text: status, icon: <ClockCircleOutlined /> };
    }
  };

  // 获取任务状态配置
  const getTaskStatusConfig = (status: string) => {
    switch (status) {
      case 'running':
        return { color: 'processing', text: '运行中' };
      case 'completed':
        return { color: 'success', text: '已完成' };
      case 'failed':
        return { color: 'error', text: '失败' };
      case 'pending':
        return { color: 'default', text: '等待中' };
      case 'cancelled':
        return { color: 'warning', text: '已取消' };
      default:
        return { color: 'default', text: status };
    }
  };

  if (loading) {
    return (
      <Card size="small" style={{ marginBottom: 16 }}>
        <div style={{ textAlign: 'center', padding: '20px' }}>
          <Spin size="large" />
          <div style={{ marginTop: 16 }}>
            <Text>正在获取流水线状态...</Text>
          </div>
        </div>
      </Card>
    );
  }

  if (error) {
    return (
      <Card size="small" style={{ marginBottom: 16 }}>
        <Alert
          message="获取流水线状态失败"
          description={error}
          type="error"
          showIcon
          action={
            <Button size="small" onClick={fetchPipelineStatus}>
              重试
            </Button>
          }
        />
      </Card>
    );
  }

  if (!pipelineStatus) {
    return null;
  }

  const statusConfig = getStatusConfig(pipelineStatus.project_status);
  const canStart = pipelineStatus.project_status === 'pending' || pipelineStatus.project_status === 'failed';
  const canStop = pipelineStatus.project_status === 'processing';
  const canRestart = pipelineStatus.project_status === 'processing' || pipelineStatus.project_status === 'failed';

  return (
    <>
      <Card size="small" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
          <Space>
            {statusConfig.icon}
            <Title level={5} style={{ margin: 0 }}>
              流水线控制
            </Title>
            <Tag color={statusConfig.color}>
              {statusConfig.text}
            </Tag>
          </Space>
        </div>

        {/* 控制按钮 */}
        <Space style={{ marginBottom: 16 }}>
          {canStart && (
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={startPipeline}
              loading={actionLoading}
            >
              启动流水线
            </Button>
          )}
          
          {canStop && (
            <Button
              danger
              icon={<PauseCircleOutlined />}
              onClick={stopPipeline}
              loading={actionLoading}
            >
              停止流水线
            </Button>
          )}
          
          {canRestart && (
            <Button
              icon={<ReloadOutlined />}
              onClick={restartPipeline}
              loading={actionLoading}
            >
              重启流水线
            </Button>
          )}
          
          <Button
            icon={<EyeOutlined />}
            onClick={() => setStatusModalVisible(true)}
          >
            查看详情
          </Button>
        </Space>

        {/* 任务统计 */}
        <div style={{ display: 'flex', justifyContent: 'space-around', marginBottom: 16 }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#1890ff' }}>
              {pipelineStatus.total_tasks}
            </div>
            <div style={{ fontSize: '12px', color: '#666' }}>总任务</div>
          </div>
          
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#52c41a' }}>
              {pipelineStatus.running_tasks}
            </div>
            <div style={{ fontSize: '12px', color: '#666' }}>运行中</div>
          </div>
          
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#faad14' }}>
              {pipelineStatus.completed_tasks}
            </div>
            <div style={{ fontSize: '12px', color: '#666' }}>已完成</div>
          </div>
          
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#ff4d4f' }}>
              {pipelineStatus.failed_tasks}
            </div>
            <div style={{ fontSize: '12px', color: '#666' }}>失败</div>
          </div>
        </div>

        {/* 当前任务进度 */}
        {pipelineStatus.tasks.length > 0 && (
          <div>
            <Text strong>当前任务:</Text>
            {pipelineStatus.tasks.map((task, index) => (
              <div key={task.id} style={{ marginTop: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                  <Text>{task.name}</Text>
                  <Tag color={getTaskStatusConfig(task.status).color}>
                    {getTaskStatusConfig(task.status).text}
                  </Tag>
                </div>
                
                <Progress
                  percent={task.realtime_progress || task.progress}
                  size="small"
                  status={task.status === 'failed' ? 'exception' : 'normal'}
                />
                
                <div style={{ fontSize: '12px', color: '#666', marginTop: 4 }}>
                  步骤: {task.realtime_step || task.current_step}
                </div>
              </div>
            ))}
          </div>
        )}

        <div style={{ marginTop: 16, textAlign: 'center' }}>
          <Text type="secondary">状态每10秒自动更新</Text>
        </div>
      </Card>

      {/* 状态详情模态框 */}
      <Modal
        title="流水线状态详情"
        open={statusModalVisible}
        onCancel={() => setStatusModalVisible(false)}
        footer={null}
        width={800}
      >
        {pipelineStatus && (
          <div>
            <div style={{ marginBottom: 16 }}>
              <Text strong>项目状态: </Text>
              <Tag color={statusConfig.color}>{statusConfig.text}</Tag>
            </div>
            
            <List
              header={<Text strong>任务列表</Text>}
              dataSource={pipelineStatus.tasks}
              renderItem={(task) => (
                <List.Item>
                  <List.Item.Meta
                    title={
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Text>{task.name}</Text>
                        <Tag color={getTaskStatusConfig(task.status).color}>
                          {getTaskStatusConfig(task.status).text}
                        </Tag>
                      </div>
                    }
                    description={
                      <div>
                        <div>步骤: {task.realtime_step || task.current_step}</div>
                        {task.step_details && <div>详情: {task.step_details}</div>}
                        <div>创建时间: {new Date(task.created_at).toLocaleString()}</div>
                        {task.started_at && (
                          <div>开始时间: {new Date(task.started_at).toLocaleString()}</div>
                        )}
                        {task.completed_at && (
                          <div>完成时间: {new Date(task.completed_at).toLocaleString()}</div>
                        )}
                      </div>
                    }
                  />
                  
                  <div style={{ width: 200 }}>
                    <Progress
                      percent={task.realtime_progress || task.progress}
                      status={task.status === 'failed' ? 'exception' : 'normal'}
                    />
                  </div>
                </List.Item>
              )}
            />
          </div>
        )}
      </Modal>
    </>
  );
};

export default PipelineControl;
