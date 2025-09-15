import React, { useState, useEffect } from 'react'
import {
  Card,
  Table,
  Button,
  Space,
  Tag,
  Progress,
  Modal,
  Form,
  Select,
  DatePicker,
  Input,
  message,
  Tooltip,
  Popconfirm,
  Typography,
  Row,
  Col,
  Statistic,
  Divider
} from 'antd'
import {
  ReloadOutlined,
  EyeOutlined,
  StopOutlined,
  ExclamationCircleOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined
} from '@ant-design/icons'
import { uploadApi, BILIBILI_PARTITIONS } from '../services/uploadApi'
import dayjs from 'dayjs'

const { RangePicker } = DatePicker
const { Option } = Select
const { Text } = Typography

interface UploadTask {
  id: string
  project_id: string
  account_id: string
  clip_id: string
  title: string
  description: string
  tags: string
  partition_id: number
  bvid?: string
  status: string
  error_message?: string
  created_at: string
  updated_at: string
  progress?: number
  current_step?: string
}

interface UploadTaskManagerProps {
  projectId?: string
}

const UploadTaskManager: React.FC<UploadTaskManagerProps> = ({ projectId }) => {
  const [tasks, setTasks] = useState<UploadTask[]>([])
  const [loading, setLoading] = useState(false)
  const [filteredTasks, setFilteredTasks] = useState<UploadTask[]>([])
  const [selectedTask, setSelectedTask] = useState<UploadTask | null>(null)
  const [detailModalVisible, setDetailModalVisible] = useState(false)
  const [filters, setFilters] = useState({
    status: '',
    accountId: '',
    dateRange: null as any,
    keyword: ''
  })

  // 获取投稿任务列表
  const fetchTasks = async () => {
    try {
      setLoading(true)
      const records = await uploadApi.getUploadRecords(projectId)
      setTasks(records)
      setFilteredTasks(records)
    } catch (error: any) {
      message.error('获取投稿任务失败: ' + (error.message || '未知错误'))
    } finally {
      setLoading(false)
    }
  }

  // 重试失败的任务
  const retryTask = async (taskId: string) => {
    message.info('B站上传功能正在开发中，敬请期待！', 3);
    return;
    
    // 原有代码已禁用
    try {
      // 这里需要调用重试API
      message.success('任务重试已启动')
      fetchTasks() // 刷新列表
    } catch (error: any) {
      message.error('重试任务失败: ' + (error.message || '未知错误'))
    }
  }

  // 取消进行中的任务
  const cancelTask = async (taskId: string) => {
    message.info('B站上传功能正在开发中，敬请期待！', 3);
    return;
    
    // 原有代码已禁用
    try {
      // 这里需要调用取消API
      message.success('任务已取消')
      fetchTasks() // 刷新列表
    } catch (error: any) {
      message.error('取消任务失败: ' + (error.message || '未知错误'))
    }
  }

  // 查看任务详情
  const showTaskDetail = (task: UploadTask) => {
    setSelectedTask(task)
    setDetailModalVisible(true)
  }

  // 应用筛选条件
  const applyFilters = () => {
    let filtered = tasks

    if (filters.status) {
      filtered = filtered.filter(task => task.status === filters.status)
    }

    if (filters.accountId) {
      filtered = filtered.filter(task => task.account_id === filters.accountId)
    }

    if (filters.keyword) {
      filtered = filtered.filter(task => 
        task.title.toLowerCase().includes(filters.keyword.toLowerCase()) ||
        task.description.toLowerCase().includes(filters.keyword.toLowerCase())
      )
    }

    if (filters.dateRange && filters.dateRange.length === 2) {
      const startDate = filters.dateRange[0].startOf('day')
      const endDate = filters.dateRange[1].endOf('day')
      filtered = filtered.filter(task => {
        const taskDate = dayjs(task.created_at)
        return taskDate.isAfter(startDate) && taskDate.isBefore(endDate)
      })
    }

    setFilteredTasks(filtered)
  }

  // 重置筛选条件
  const resetFilters = () => {
    setFilters({
      status: '',
      accountId: '',
      dateRange: null,
      keyword: ''
    })
    setFilteredTasks(tasks)
  }

  // 获取状态标签颜色
  const getStatusColor = (status: string) => {
    switch (status) {
      case 'pending':
        return 'orange'
      case 'processing':
        return 'blue'
      case 'success':
        return 'green'
      case 'failed':
        return 'red'
      default:
        return 'default'
    }
  }

  // 获取状态图标
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending':
        return <ClockCircleOutlined />
      case 'processing':
        return <ExclamationCircleOutlined />
      case 'success':
        return <CheckCircleOutlined />
      case 'failed':
        return <CloseCircleOutlined />
      default:
        return null
    }
  }

  // 获取状态文本
  const getStatusText = (status: string) => {
    switch (status) {
      case 'pending':
        return '待处理'
      case 'processing':
        return '处理中'
      case 'success':
        return '成功'
      case 'failed':
        return '失败'
      default:
        return status
    }
  }

  // 计算统计数据
  const getStatistics = () => {
    const total = tasks.length
    const pending = tasks.filter(t => t.status === 'pending').length
    const processing = tasks.filter(t => t.status === 'processing').length
    const success = tasks.filter(t => t.status === 'success').length
    const failed = tasks.filter(t => t.status === 'failed').length

    return { total, pending, processing, success, failed }
  }

  useEffect(() => {
    fetchTasks()
  }, [projectId])

  useEffect(() => {
    applyFilters()
  }, [filters, tasks])

  const columns = [
    {
      title: '任务信息',
      key: 'task_info',
      render: (record: UploadTask) => (
        <div>
          <div style={{ fontWeight: 'bold' }}>{record.title}</div>
          <div style={{ fontSize: '12px', color: '#666' }}>
            项目ID: {record.project_id.slice(0, 8)}...
          </div>
        </div>
      )
    },
    {
      title: '切片数量',
      key: 'clip_count',
      render: (record: UploadTask) => {
        const clipCount = record.clip_id.split(',').filter(id => id.trim()).length
        return <Tag>{clipCount} 个切片</Tag>
      }
    },
    {
      title: '分区',
      key: 'partition',
      render: (record: UploadTask) => {
        const partition = BILIBILI_PARTITIONS.find(p => p.id === record.partition_id)
        return partition ? partition.name : `分区${record.partition_id}`
      }
    },
    {
      title: '状态',
      key: 'status',
      render: (record: UploadTask) => (
        <Tag color={getStatusColor(record.status)} icon={getStatusIcon(record.status)}>
          {getStatusText(record.status)}
        </Tag>
      )
    },
    {
      title: '进度',
      key: 'progress',
      render: (record: UploadTask) => {
        if (record.status === 'processing' && record.progress !== undefined) {
          return <Progress percent={record.progress} size="small" />
        } else if (record.status === 'success') {
          return <Progress percent={100} size="small" status="success" />
        } else if (record.status === 'failed') {
          return <Progress percent={0} size="small" status="exception" />
        }
        return <Progress percent={0} size="small" />
      }
    },
    {
      title: '创建时间',
      key: 'created_at',
      render: (record: UploadTask) => dayjs(record.created_at).format('YYYY-MM-DD HH:mm')
    },
    {
      title: '操作',
      key: 'actions',
      render: (record: UploadTask) => (
        <Space>
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => showTaskDetail(record)}
          >
            详情
          </Button>
          
          {record.status === 'failed' && (
            <Button
              type="link"
              size="small"
              icon={<ReloadOutlined />}
              onClick={() => retryTask(record.id)}
            >
              重试
            </Button>
          )}
          
          {record.status === 'processing' && (
            <Popconfirm
              title="确定要取消这个任务吗？"
              onConfirm={() => cancelTask(record.id)}
              okText="确定"
              cancelText="取消"
            >
              <Button
                type="link"
                size="small"
                danger
                icon={<StopOutlined />}
              >
                取消
              </Button>
            </Popconfirm>
          )}
        </Space>
      )
    }
  ]

  const stats = getStatistics()

  return (
    <div style={{ padding: '24px' }}>
      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: '24px' }}>
        <Col span={4}>
          <Card>
            <Statistic title="总任务数" value={stats.total} />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic title="待处理" value={stats.pending} valueStyle={{ color: '#faad14' }} />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic title="处理中" value={stats.processing} valueStyle={{ color: '#1890ff' }} />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic title="成功" value={stats.success} valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic title="失败" value={stats.failed} valueStyle={{ color: '#ff4d4f' }} />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic 
              title="成功率" 
              value={stats.total > 0 ? Math.round((stats.success / stats.total) * 100) : 0}
              suffix="%" 
              valueStyle={{ color: '#52c41a' }}
            />
          </Card>
        </Col>
      </Row>

      {/* 筛选栏 */}
      <Card style={{ marginBottom: '16px' }}>
        <Row gutter={16} align="middle">
          <Col span={6}>
            <Form.Item label="状态" style={{ marginBottom: 0 }}>
              <Select
                placeholder="选择状态"
                value={filters.status}
                onChange={(value) => setFilters({ ...filters, status: value })}
                allowClear
              >
                <Option value="pending">待处理</Option>
                <Option value="processing">处理中</Option>
                <Option value="success">成功</Option>
                <Option value="failed">失败</Option>
              </Select>
            </Form.Item>
          </Col>
          <Col span={6}>
            <Form.Item label="时间范围" style={{ marginBottom: 0 }}>
              <RangePicker
                value={filters.dateRange}
                onChange={(dates) => setFilters({ ...filters, dateRange: dates })}
                placeholder={['开始日期', '结束日期']}
              />
            </Form.Item>
          </Col>
          <Col span={6}>
            <Form.Item label="关键词" style={{ marginBottom: 0 }}>
              <Input
                placeholder="搜索标题或描述"
                value={filters.keyword}
                onChange={(e) => setFilters({ ...filters, keyword: e.target.value })}
              />
            </Form.Item>
          </Col>
          <Col span={6}>
            <Space>
              <Button type="primary" onClick={applyFilters}>
                筛选
              </Button>
              <Button onClick={resetFilters}>
                重置
              </Button>
              <Button icon={<ReloadOutlined />} onClick={fetchTasks}>
                刷新
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      {/* 任务列表 */}
      <Card title={`投稿任务列表 (${filteredTasks.length})`}>
        <Table
          columns={columns}
          dataSource={filteredTasks}
          rowKey="id"
          loading={loading}
          pagination={{
            pageSize: 10,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条`
          }}
        />
      </Card>

      {/* 任务详情弹窗 */}
      <Modal
        title="任务详情"
        open={detailModalVisible}
        onCancel={() => setDetailModalVisible(false)}
        footer={[
          <Button key="close" onClick={() => setDetailModalVisible(false)}>
            关闭
          </Button>
        ]}
        width={800}
      >
        {selectedTask && (
          <div>
            <Row gutter={16}>
              <Col span={12}>
                <div><strong>任务ID:</strong> {selectedTask.id}</div>
                <div><strong>项目ID:</strong> {selectedTask.project_id}</div>
                <div><strong>标题:</strong> {selectedTask.title}</div>
                <div><strong>描述:</strong> {selectedTask.description}</div>
              </Col>
              <Col span={12}>
                <div><strong>状态:</strong> 
                  <Tag color={getStatusColor(selectedTask.status)} style={{ marginLeft: 8 }}>
                    {getStatusText(selectedTask.status)}
                  </Tag>
                </div>
                <div><strong>分区:</strong> 
                  {(() => {
                    const partition = BILIBILI_PARTITIONS.find(p => p.id === selectedTask.partition_id)
                    return partition ? partition.name : `分区${selectedTask.partition_id}`
                  })()}
                </div>
                <div><strong>创建时间:</strong> {dayjs(selectedTask.created_at).format('YYYY-MM-DD HH:mm:ss')}</div>
                <div><strong>更新时间:</strong> {dayjs(selectedTask.updated_at).format('YYYY-MM-DD HH:mm:ss')}</div>
              </Col>
            </Row>
            
            <Divider />
            
            <div>
              <strong>切片信息:</strong>
              <div style={{ marginTop: 8 }}>
                {selectedTask.clip_id.split(',').filter(id => id.trim()).map((clipId, index) => (
                  <Tag key={index} style={{ marginBottom: 4 }}>{clipId.trim()}</Tag>
                ))}
              </div>
            </div>
            
            {selectedTask.tags && (
              <>
                <Divider />
                <div>
                  <strong>标签:</strong>
                  <div style={{ marginTop: 8 }}>
                    {JSON.parse(selectedTask.tags).map((tag: string, index: number) => (
                      <Tag key={index} color="blue">{tag}</Tag>
                    ))}
                  </div>
                </div>
              </>
            )}
            
            {selectedTask.bvid && (
              <>
                <Divider />
                <div>
                  <strong>BV号:</strong> {selectedTask.bvid}
                </div>
              </>
            )}
            
            {selectedTask.error_message && (
              <>
                <Divider />
                <div>
                  <strong>错误信息:</strong>
                  <div style={{ marginTop: 8, color: '#ff4d4f', backgroundColor: '#fff2f0', padding: 8, borderRadius: 4 }}>
                    {selectedTask.error_message}
                  </div>
                </div>
              </>
            )}
          </div>
        )}
      </Modal>
    </div>
  )
}

export default UploadTaskManager



