import React, { useState, useEffect } from 'react';
import { useWebSocket, WebSocketEventMessage } from '../hooks/useWebSocket';

interface InlineProgressBarProps {
  projectId: string;
  currentStep?: number;
  totalSteps?: number;
  status?: string;
  onProgressUpdate?: (progress: number, step: string) => void;
}

interface ProgressData {
  progress: number;
  currentStep: number;
  totalSteps: number;
  stepName: string;
  stepDetails?: string;
}

// 流水线步骤配置
const PIPELINE_STEPS = [
  { id: 1, name: '大纲提取', description: '从视频转写文本中提取结构性大纲' },
  { id: 2, name: '时间定位', description: '基于SRT字幕定位话题时间区间' },
  { id: 3, name: '内容评分', description: '多维度评估片段质量与传播潜力' },
  { id: 4, name: '标题生成', description: '为高分片段生成吸引人的标题' },
  { id: 5, name: '主题聚类', description: '将相关片段聚合为合集推荐' },
  { id: 6, name: '视频切割', description: '使用FFmpeg生成切片与合集视频' }
];

export const InlineProgressBar: React.FC<InlineProgressBarProps> = ({
  projectId,
  currentStep = 0,
  totalSteps = 6,
  status = 'processing',
  onProgressUpdate
}) => {
  const [progressData, setProgressData] = useState<ProgressData>({
    progress: currentStep > 0 ? Math.round((currentStep / totalSteps) * 100) : 0,
    currentStep: currentStep,
    totalSteps: totalSteps,
    stepName: currentStep > 0 ? getStepName(currentStep) : '初始化中...',
    stepDetails: ''
  });

  // WebSocket连接用于实时进度更新
  const { isConnected, syncSubscriptions } = useWebSocket({
    userId: `homepage-user`, // 使用统一的用户ID，避免重复连接
    onMessage: (message: WebSocketEventMessage) => {
      console.log('InlineProgressBar收到WebSocket消息:', message);
      if (message.type === 'task_progress_update' && 
          message.project_id === projectId) {
        handleProgressUpdate(message);
      }
    }
  });

  // 处理进度更新
  const handleProgressUpdate = (message: any) => {
    console.log('InlineProgressBar处理进度更新:', message);
    
    const newProgress = message.progress || 0;
    const stepName = message.step_name || '处理中...';
    const stepDetails = message.message || '';
    
    // 快照消息检查 - 避免回退
    if (message.snapshot && progressData.progress > newProgress) {
      console.log('忽略旧快照消息:', { current: progressData.progress, snapshot: newProgress });
      return;
    }
    
    console.log('更新进度数据:', { newProgress, stepName, stepDetails });
    
    setProgressData(prev => ({
      ...prev,
      progress: newProgress,
      stepName: stepName,
      stepDetails: stepDetails
    }));

    // 通知父组件
    onProgressUpdate?.(newProgress, stepName);
  };

  // 根据步骤ID获取步骤名称
  const getStepName = (stepId: number): string => {
    const step = PIPELINE_STEPS.find(s => s.id === stepId);
    return step ? step.name : '处理中...';
  };

  // 监听props变化，更新进度数据
  useEffect(() => {
    const newProgress = currentStep > 0 ? Math.round((currentStep / totalSteps) * 100) : 0;
    const newStepName = currentStep > 0 ? getStepName(currentStep) : '初始化中...';
    
    setProgressData(prev => ({
      ...prev,
      progress: newProgress,
      currentStep: currentStep,
      totalSteps: totalSteps,
      stepName: newStepName
    }));
  }, [currentStep, totalSteps]);

  // 订阅项目进度更新
  useEffect(() => {
    console.log('InlineProgressBar WebSocket状态:', { isConnected, projectId });
    if (isConnected && projectId) {
      console.log('订阅项目进度:', projectId);
      syncSubscriptions([projectId]);
    }
  }, [isConnected, projectId, syncSubscriptions]);

  // 计算进度条宽度百分比
  const progressPercentage = Math.min(Math.max(progressData.progress, 0), 100);
  
  // 计算当前步骤在总步骤中的位置
  const stepProgress = progressData.currentStep > 0 ? 
    ((progressData.currentStep - 1) / progressData.totalSteps) * 100 : 0;

  // 生成进度条背景渐变
  const getProgressGradient = () => {
    const baseColor = '#1890ff';
    const lightColor = '#40a9ff';
    const darkColor = '#096dd9';
    
    return `linear-gradient(90deg, 
      ${baseColor} 0%, 
      ${lightColor} ${progressPercentage}%, 
      rgba(24, 144, 255, 0.1) ${progressPercentage}%, 
      rgba(24, 144, 255, 0.1) 100%)`;
  };

  // 生成动画效果
  const getAnimationStyle = () => {
    return {
      background: getProgressGradient()
    };
  };

  return (
    <div style={{
      background: 'rgba(24, 144, 255, 0.15)',
      border: '1px solid rgba(24, 144, 255, 0.3)',
      borderRadius: '4px',
      padding: '6px 12px',
      position: 'relative',
      overflow: 'hidden',
      height: '32px', // 固定高度
      display: 'flex',
      alignItems: 'center'
    }}>
      {/* 进度条背景 */}
      <div style={{
        position: 'absolute',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        ...getAnimationStyle()
      }} />
      
      {/* 内容层 - 单行布局 */}
      <div style={{ 
        position: 'relative', 
        zIndex: 1,
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '8px'
      }}>
        {/* 左侧：步骤名称 */}
        <div style={{ 
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          minWidth: '0',
          flex: '1'
        }}>
          <span style={{ 
            color: '#1890ff',
            fontSize: '12px', 
            fontWeight: 600,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis'
          }}>
            {progressData.stepName}
          </span>
        </div>
        
        {/* 中间：进度条 */}
        <div style={{
          width: '80px',
          height: '4px',
          background: 'rgba(24, 144, 255, 0.2)',
          borderRadius: '2px',
          overflow: 'hidden',
          flexShrink: 0
        }}>
          <div style={{
            width: `${progressPercentage}%`,
            height: '100%',
            background: status === 'processing' && progressData.progress < 100 ? 
              'linear-gradient(90deg, #1890ff, #40a9ff, #1890ff)' :
              'linear-gradient(90deg, #1890ff, #40a9ff)',
            borderRadius: '2px',
            transition: 'width 0.3s ease-in-out',
            animation: status === 'processing' && progressData.progress < 100 ? 
              'progressBarPulse 2s infinite ease-in-out' : 'none'
          }} />
        </div>
        
        {/* 右侧：进度信息 */}
        <div style={{ 
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          flexShrink: 0
        }}>
          <span style={{ 
            color: '#1890ff',
            fontSize: '10px',
            opacity: 0.8
          }}>
            {progressData.currentStep}/{progressData.totalSteps}
          </span>
          <span style={{ 
            color: '#1890ff',
            fontSize: '10px',
            fontWeight: 600,
            minWidth: '28px'
          }}>
            {Math.round(progressPercentage)}%
          </span>
        </div>
      </div>
      
      {/* 添加CSS动画 */}
      <style jsx>{`
        @keyframes progressBarPulse {
          0%, 100% {
            opacity: 1;
            transform: scaleY(1);
          }
          50% {
            opacity: 0.8;
            transform: scaleY(1.1);
          }
        }
      `}</style>
    </div>
  );
};

export default InlineProgressBar;
