import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Layout, Card, Progress, Steps, Typography, Button, Alert, Space, Spin, message } from 'antd'
import { CheckCircleOutlined, LoadingOutlined, ExclamationCircleOutlined, ArrowLeftOutlined } from '@ant-design/icons'
import { projectApi } from '../services/api'
import { useProjectStore } from '../store/useProjectStore'
import {
  classifyStatusPollError,
  shouldStopProcessingPoll,
  toProcessingView,
  type ProcessingStatusView,
} from '../utils/processingStatusPoll'

const { Content } = Layout
const { Title, Text } = Typography
const { Step } = Steps

const ProcessingPage: React.FC = () => {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { currentProject, setCurrentProject } = useProjectStore()
  const [status, setStatus] = useState<ProcessingStatusView | null>(null)
  const [loading, setLoading] = useState(true)

  const steps = [
    { title: '大纲提取', description: '从视频转写文本中提取结构性大纲' },
    { title: '时间定位', description: '基于SRT字幕定位话题时间区间' },
    { title: '内容评分', description: '多维度评估片段质量与传播潜力' },
    { title: '标题生成', description: '为高分片段生成吸引人的标题' },
    { title: '主题聚类', description: '将相关片段聚合为合集推荐' },
    { title: '视频切割', description: '使用FFmpeg生成切片与合集视频' }
  ]

  useEffect(() => {
    if (!id) return

    let stopped = false
    let notifiedRetry = false
    let timer = 0

    const stop = () => {
      stopped = true
      if (timer) window.clearInterval(timer)
    }

    const checkStatus = async () => {
      if (stopped) return

      try {
        const statusData = await projectApi.getProcessingStatus(id)
        if (stopped) return
        const view = toProcessingView(statusData)
        setStatus(view)

        if (shouldStopProcessingPoll({ phase: view.status })) {
          stop()
        }

        if (view.status === 'completed') {
          message.success('🎉 视频处理完成！正在跳转到结果页面...')
          window.setTimeout(() => navigate(`/project/${id}`), 2000)
          return
        }

        if (view.status === 'error') {
          const errorMsg = view.error_message || '处理过程中发生未知错误'
          message.error(`处理失败: ${errorMsg}`)
          message.info('您可以返回首页重新上传文件或联系技术支持', 5)
        }
      } catch (error: any) {
        if (stopped) return
        console.error('Check status error:', error)
        const kind = classifyStatusPollError(error)

        if (shouldStopProcessingPoll({ error })) {
          stop()
          if (kind === 'not_found') {
            message.error('项目不存在或已被删除')
            window.setTimeout(() => navigate('/'), 2000)
          } else {
            message.error('获取处理状态失败，请刷新页面重试')
          }
          return
        }

        if (notifiedRetry) return
        notifiedRetry = true
        if (kind === 'timeout') {
          message.warning('网络连接超时，正在重试...')
        } else {
          message.error('获取处理状态失败，请刷新页面重试')
        }
      }
    }

    loadProject()
    timer = window.setInterval(() => { void checkStatus() }, 2000)

    return () => stop()
  }, [id, navigate])

  const loadProject = async () => {
    if (!id) return
    
    try {
      const project = await projectApi.getProject(id)
      setCurrentProject(project)
      
      // 如果项目已完成，直接跳转到详情页
      if (project.status === 'completed') {
        navigate(`/project/${id}`)
        return
      }
      
      // 如果项目状态是等待处理，开始处理
      if (project.status === 'pending') {
        await startProcessing()
      }
    } catch (error) {
      message.error('加载项目失败')
      console.error('Load project error:', error)
    } finally {
      setLoading(false)
    }
  }

  const startProcessing = async () => {
    if (!id) return
    
    try {
      await projectApi.startProcessing(id)
      message.success('开始处理项目')
    } catch (error) {
      message.error('启动处理失败')
      console.error('Start processing error:', error)
    }
  }

  const getStepStatus = (stepIndex: number) => {
    if (!status) return 'wait'
    
    if (status.status === 'error') {
      return stepIndex < status.current_step ? 'finish' : 'error'
    }
    
    if (stepIndex < status.current_step) return 'finish'
    if (stepIndex === status.current_step) return 'process'
    return 'wait'
  }

  const getStepIcon = (stepIndex: number) => {
    const stepStatus = getStepStatus(stepIndex)
    
    if (stepStatus === 'finish') return <CheckCircleOutlined />
    if (stepStatus === 'process') return <LoadingOutlined />
    if (stepStatus === 'error') return <ExclamationCircleOutlined />
    return null
  }

  if (loading) {
    return (
      <Content style={{ padding: '24px', display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '400px' }}>
        <Spin size="large" tip="加载中..." />
      </Content>
    )
  }

  return (
    <Content style={{ padding: '24px', maxWidth: '1000px', margin: '0 auto' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <Title level={2}>视频处理进度</Title>
          <Button 
            icon={<ArrowLeftOutlined />} 
            onClick={() => navigate('/')}
          >
            返回首页
          </Button>
        </div>

        {currentProject && (
          <Card>
            <Title level={4}>{currentProject.name}</Title>
            <Text type="secondary">项目ID: {currentProject.id}</Text>
          </Card>
        )}

        {status?.status === 'error' && (
          <Alert
            message="处理失败"
            description={
              <div>
                <p>{status.error_message || '处理过程中发生未知错误'}</p>
                <p style={{ marginTop: '8px', fontSize: '12px', color: '#666' }}>
                  可能的原因：文件格式不支持、文件损坏、网络问题或服务器错误
                </p>
              </div>
            }
            type="error"
            showIcon
            action={
              <Space>
                <Button size="small" onClick={() => window.location.reload()}>
                  刷新页面
                </Button>
                <Button size="small" onClick={() => navigate('/')}>
                  返回首页
                </Button>
              </Space>
            }
          />
        )}

        {status && status.status === 'processing' && (
          <Card title="处理进度">
            <Space direction="vertical" size="large" style={{ width: '100%' }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <Text strong>总体进度</Text>
                  <Text>{Math.round(status.progress)}%</Text>
                </div>
                <Progress 
                  percent={status.progress} 
                  status="active"
                  strokeColor={{
                    '0%': '#108ee9',
                    '100%': '#87d068',
                  }}
                />
              </div>

              <div>
                <Text strong>当前步骤: </Text>
                <Text>{status.step_name}</Text>
              </div>

              <Steps 
                direction="vertical" 
                current={status.current_step}
                status="process"
              >
                {steps.map((step, index) => (
                  <Step
                    key={index}
                    title={step.title}
                    description={step.description}
                    status={getStepStatus(index)}
                    icon={getStepIcon(index)}
                  />
                ))}
              </Steps>
            </Space>
          </Card>
        )}

        {status?.status === 'completed' && (
          <Alert
            message="处理完成"
            description="视频已成功处理完成，正在跳转到项目详情页..."
            type="success"
            showIcon
          />
        )}
      </Space>
    </Content>
  )
}

export default ProcessingPage