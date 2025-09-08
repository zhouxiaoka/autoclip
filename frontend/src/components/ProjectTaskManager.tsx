import React, { useState, useEffect } from 'react'
import { Card, Table, Tag, Progress, Space, Typography, Button, Modal, message, Row, Col, Statistic } from 'antd'
import { ReloadOutlined, EyeOutlined, ExclamationCircleOutlined, CheckCircleOutlined, ClockCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import { useTaskStatus } from '../hooks/useTaskStatus'
import { TaskStatus as TaskStatusType } from '../hooks/useTaskStatus'

const { Title, Text } = Typography
const { confirm } = Modal

interface ProjectTaskManagerProps {
  projectId: string
  projectName?: string
}

export const ProjectTaskManager: React.FC<ProjectTaskManagerProps> = ({ 
  projectId, 
  projectName 
}) => {
  const { getAllTasks, loading } = useTaskStatus()
  const [selectedTask, setSelectedTask] = useState<TaskStatusType | null>(null)
  const [taskDetailVisible, setTaskDetailVisible] = useState(false)

  // 获取当前项目的任务
  const projectTasks = getAllTasks().filter(task => task.project_id === projectId)
  const activeTasks = projectTasks.filter(task => 
    task.status === 'running' || task.status === 'pending'
  )
  const completedTasks = projectTasks.filter(task => task.status === 'completed')
  const failedTasks = projectTasks.filter(task => task.status === 'failed')

  // 刷新任务列表
  const handleRefresh = () => {
    message.success('任务列表已刷新')
  }

  // 查看任务详情
  const handleViewTask = (task: TaskStatusType) => {
    setSelectedTask(task)
    setTaskDetailVisible(true)
  }

  // 删除任务
  const handleDeleteTask = (taskId: string) => {
    confirm({
      title: '确认删除',
      icon: <ExclamationCircleOutlined />,
      content: '确定要删除这个任务吗？删除后无法恢复。',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk() {
        message.success('任务已删除')
      }
    })
  }

  // 获取状态图标
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircleOutlined style={{ color: '#52c41a' }} />
      case 'running':
        return <ClockCircleOutlined style={{ color: '#1890ff' }} />
      case 'failed':
        return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
      case 'pending':
        return <ClockCircleOutlined style={{ color: '#faad14' }} />
      default:
        return <ClockCircleOutlined style={{ color: '#d9d9d9' }} />
    }
  }

  // 获取状态颜色
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed':
        return 'success'
      case 'running':
        return 'processing'
      case 'failed':
        return 'error'
      case 'pending':
        return 'warning'
      default:
        return 'default'
    }
  }

  // 表格列定义
  const columns = [
    {
      title: '任务名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: TaskStatusType) => (
        <Space>
          {getStatusIcon(record.status)}
          <Text strong>{text}</Text>
        </Space>
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={getStatusColor(status)}>
          {status === 'completed' ? '已完成' :
           status === 'running' ? '执行中' :
           status === 'failed' ? '失败' :
           status === 'pending' ? '等待中' : status}
        </Tag>
      )
    },
    {
      title: '进度',
      dataIndex: 'progress',
      key: 'progress',
      render: (progress: number, record: TaskStatusType) => (
        <Progress 
          percent={Math.round(progress)} 
          size="small"
          status={record.status === 'failed' ? 'exception' : 'normal'}
        />
      )
    },
    {
      title: '当前步骤',
      dataIndex: 'current_step',
      key: 'current_step',
      render: (step: string) => step || '-'
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (timestamp: string) => (
        <Text type="secondary">
          {new Date(timestamp).toLocaleString('zh-CN')}
        </Text>
      )
    },
    {
      title: '操作',
      key: 'actions',
      width: 120,
      render: (_: any, record: TaskStatusType) => (
        <Space size="small">
          <Button
            type="text"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => handleViewTask(record)}
            title="查看详情"
          />
          <Button
            type="text"
            size="small"
            icon={<ExclamationCircleOutlined />}
            onClick={() => handleDeleteTask(record.id)}
            title="删除任务"
            danger
          />
        </Space>
      )
    }
  ]

  if (projectTasks.length === 0) {
    return (
      <Card title="任务管理" size="small">
        <div style={{ textAlign: 'center', padding: '20px' }}>
          <Text type="secondary">该项目暂无任务记录</Text>
        </div>
      </Card>
    )
  }

  return (
    <Card 
      title={
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>任务管理</span>
          <Button 
            type="primary" 
            size="small"
            icon={<ReloadOutlined />}
            onClick={handleRefresh}
            loading={loading}
          >
            刷新
          </Button>
        </div>
      }
      size="small"
    >
      {/* 任务统计 */}
      <Row gutter={16} style={{ marginBottom: '16px' }}>
        <Col span={6}>
          <Statistic
            title="总任务数"
            value={projectTasks.length}
            prefix={<ClockCircleOutlined />}
          />
        </Col>
        <Col span={6}>
          <Statistic
            title="活跃任务"
            value={activeTasks.length}
            valueStyle={{ color: '#1890ff' }}
            prefix={<ClockCircleOutlined />}
          />
        </Col>
        <Col span={6}>
          <Statistic
            title="已完成"
            value={completedTasks.length}
            valueStyle={{ color: '#52c41a' }}
            prefix={<CheckCircleOutlined />}
          />
        </Col>
        <Col span={6}>
          <Statistic
            title="失败任务"
            value={failedTasks.length}
            valueStyle={{ color: '#ff4d4f' }}
            prefix={<CloseCircleOutlined />}
          />
        </Col>
      </Row>

      {/* 活跃任务 */}
      {activeTasks.length > 0 && (
        <Card 
          size="small" 
          style={{ marginBottom: '16px' }}
          title={`活跃任务 (${activeTasks.length})`}
        >
          <Space wrap>
            {activeTasks.map(task => (
              <div key={task.id} style={{ marginBottom: '8px' }}>
                <Text>{task.message || task.id}</Text>
                <Progress percent={task.progress} size="small" />
              </div>
            ))}
          </Space>
        </Card>
      )}

      {/* 任务列表 */}
      <Table
        columns={columns}
        dataSource={projectTasks}
        rowKey="id"
        pagination={{
          pageSize: 5,
          showSizeChanger: false,
          showTotal: (total, range) => 
            `第 ${range[0]}-${range[1]} 条，共 ${total} 条`
        }}
        size="small"
        loading={loading}
      />

      {/* 任务详情弹窗 */}
      <Modal
        title="任务详情"
        open={taskDetailVisible}
        onCancel={() => setTaskDetailVisible(false)}
        footer={[
          <Button key="close" onClick={() => setTaskDetailVisible(false)}>
            关闭
          </Button>
        ]}
        width={800}
      >
        {selectedTask && (
          <div>
            <Text>任务ID: {selectedTask.id}</Text>
            <br />
            <Text>状态: {selectedTask.status}</Text>
            <br />
            <Text>进度: {selectedTask.progress}%</Text>
            <br />
            <Text>消息: {selectedTask.message}</Text>
          </div>
        )}
      </Modal>
    </Card>
  )
}
