import React, { useState, useEffect, useRef } from 'react'
import { Modal, Steps, Progress, Typography, Button, Alert, Space, Spin, message } from 'antd'
import { 
  CheckCircleOutlined, 
  LoadingOutlined, 
  ExclamationCircleOutlined, 
  ReloadOutlined
} from '@ant-design/icons'
import { projectApi } from '../services/api'
import { useProjectStore } from '../store/useProjectStore'
import {
  classifyStatusPollError,
  shouldStopProcessingPoll,
  toProcessingView,
  type ProcessingStatusView,
} from '../utils/processingStatusPoll'

const { Text } = Typography
const { Step } = Steps

interface TaskProgressModalProps {
  visible: boolean
  projectId: string | null
  onClose: () => void
  onComplete?: (projectId: string) => void
}

const TaskProgressModal: React.FC<TaskProgressModalProps> = ({
  visible,
  projectId,
  onClose,
  onComplete
}) => {
  const [status, setStatus] = useState<ProcessingStatusView | null>(null)
  const [loading, setLoading] = useState(false)
  const [pollEpoch, setPollEpoch] = useState(0)
  const { updateProject } = useProjectStore()
  const updateProjectRef = useRef(updateProject)
  const onCompleteRef = useRef(onComplete)
  const reportedStepRef = useRef<number | undefined>(undefined)
  updateProjectRef.current = updateProject
  onCompleteRef.current = onComplete

  const steps = [
    { title: '大纲提取', description: '从视频转写文本中提取结构性大纲' },
    { title: '时间定位', description: '基于SRT字幕定位话题时间区间' },
    { title: '内容评分', description: '多维度评估片段质量与传播潜力' },
    { title: '标题生成', description: '为高分片段生成吸引人的标题' },
    { title: '主题聚类', description: '将相关片段聚合为合集推荐' },
    { title: '视频切割', description: '使用FFmpeg生成切片与合集视频' }
  ]

  useEffect(() => {
    if (!visible || !projectId) {
      setStatus(null)
      return
    }

    let stopped = false
    let notifiedRetry = false
    let notifiedTerminal = false
    let timer = 0
    reportedStepRef.current = undefined

    const stop = () => {
      stopped = true
      if (timer) window.clearInterval(timer)
    }

    const checkStatus = async () => {
      if (stopped) return

      try {
        const statusData = await projectApi.getProcessingStatus(projectId)
        if (stopped) return
        const view = toProcessingView(statusData)
        reportedStepRef.current = typeof statusData.current_step === 'number' ? statusData.current_step : undefined
        setStatus(view)

        updateProjectRef.current(projectId, {
          status: view.status,
          current_step: view.current_step,
          total_steps: view.total_steps,
          error_message: view.error_message
        })

        if (shouldStopProcessingPoll({ phase: view.status })) {
          stop()
          if (view.status === 'completed') onCompleteRef.current?.(projectId)
          if (view.status === 'error' && !notifiedTerminal) {
            notifiedTerminal = true
            message.error(`处理失败: ${view.error_message || '处理过程中发生未知错误'}`)
          }
        }
      } catch (error) {
        if (stopped) return
        console.error('Check status error:', error)
        const kind = classifyStatusPollError(error)

        if (shouldStopProcessingPoll({ error })) {
          stop()
          if (!notifiedTerminal) {
            notifiedTerminal = true
            message.error(kind === 'not_found' ? '项目不存在或已被删除' : '获取处理状态失败，请刷新页面重试')
          }
          return
        }

        if (notifiedRetry) return
        notifiedRetry = true
        if (kind === 'timeout') {
          message.warning('网络连接超时，正在重试...')
        }
      }
    }

    void checkStatus()
    timer = window.setInterval(() => { void checkStatus() }, 2000)

    return () => stop()
  }, [visible, projectId, pollEpoch])

  const handleRetry = async () => {
    if (!projectId) return
    
    setLoading(true)
    try {
      if (reportedStepRef.current !== undefined) {
        await projectApi.restartStep(projectId, reportedStepRef.current)
      } else {
        // 完全重试
        await projectApi.retryProcessing(projectId)
      }
      setStatus(null)
      setPollEpoch((epoch) => epoch + 1)
    } catch (error) {
      console.error('Retry error:', error)
    } finally {
      setLoading(false)
    }
  }

  const getStepStatus = (stepIndex: number) => {
    if (!status) return 'wait'
    
    if (status.status === 'error' && stepIndex === status.current_step) {
      return 'error'
    }
    
    if (stepIndex < status.current_step) {
      return 'finish'
    }
    
    if (stepIndex === status.current_step) {
      return status.status === 'completed' ? 'finish' : 'process'
    }
    
    return 'wait'
  }

  const getStepIcon = (stepIndex: number) => {
    const stepStatus = getStepStatus(stepIndex)
    
    if (stepStatus === 'error') {
      return <ExclamationCircleOutlined style={{ color: '#ff4d4f' }} />
    }
    
    if (stepStatus === 'finish') {
      return <CheckCircleOutlined style={{ color: '#52c41a' }} />
    }
    
    if (stepStatus === 'process') {
      return <LoadingOutlined style={{ color: '#1890ff' }} />
    }
    
    return null
  }

  return (
    <Modal
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <LoadingOutlined style={{ color: '#1890ff' }} />
          <span>任务处理进度</span>
        </div>
      }
      open={visible}
      onCancel={onClose}
      footer={[
        <Button key="close" onClick={onClose}>
          关闭
        </Button>,
        ...(status?.status === 'error' ? [
          <Button 
            key="retry" 
            type="primary" 
            icon={<ReloadOutlined />}
            loading={loading}
            onClick={handleRetry}
          >
            从当前步骤重试
          </Button>
        ] : [])
      ]}
      width={600}
      centered
      maskClosable={false}
      destroyOnClose
    >
      <div style={{ padding: '16px 0' }}>
        {!status ? (
          <div style={{ textAlign: 'center', padding: '40px 0' }}>
            <Spin size="large" />
            <div style={{ marginTop: '16px', color: '#666' }}>
              正在获取任务状态...
            </div>
          </div>
        ) : (
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            {/* 整体进度 */}
            <div>
              <div style={{ 
                display: 'flex', 
                justifyContent: 'space-between', 
                alignItems: 'center',
                marginBottom: '8px'
              }}>
                <Text strong>整体进度</Text>
                <Text type="secondary">
                  {status.current_step}/{status.total_steps} 步骤
                </Text>
              </div>
              <Progress 
                percent={Math.round((status.current_step / status.total_steps) * 100)}
                status={status.status === 'error' ? 'exception' : 'active'}
                strokeColor={{
                  '0%': '#4facfe',
                  '100%': '#00f2fe'
                }}
              />
            </div>

            {/* 当前步骤信息 */}
            <div style={{
              background: '#f8f9fa',
              padding: '16px',
              borderRadius: '8px',
              border: '1px solid #e9ecef'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                {getStepIcon(status.current_step)}
                <Text strong>当前步骤: {status.step_name}</Text>
              </div>
              <Progress 
                percent={status.progress}
                size="small"
                status={status.status === 'error' ? 'exception' : 'active'}
              />
            </div>

            {/* 错误信息 */}
            {status.status === 'error' && status.error_message && (
              <Alert
                message="处理失败"
                description={status.error_message}
                type="error"
                showIcon
              />
            )}

            {/* 步骤列表 */}
            <div>
              <Text strong style={{ marginBottom: '16px', display: 'block' }}>处理步骤</Text>
              <Steps
                direction="vertical"
                size="small"
                current={status.current_step}
                status={status.status === 'error' ? 'error' : 'process'}
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
            </div>

            {/* 完成提示 */}
            {status.status === 'completed' && (
              <Alert
                message="处理完成"
                description="视频已成功处理，您可以查看生成的片段和合集。"
                type="success"
                showIcon
              />
            )}
          </Space>
        )}
      </div>
    </Modal>
  )
}

export default TaskProgressModal