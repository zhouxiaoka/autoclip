import React, { useState, useEffect } from 'react';
import { Progress, Card, Tag, Space, Typography, Tooltip } from 'antd';
import { ClockCircleOutlined, CheckCircleOutlined, CloseCircleOutlined, ExclamationCircleOutlined, PlayCircleOutlined, LoadingOutlined } from '@ant-design/icons';
import { TaskStatus } from '../hooks/useTaskStatus';
import dayjs from 'dayjs';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';

// 配置dayjs插件
dayjs.extend(utc);
dayjs.extend(timezone);

const { Text, Paragraph } = Typography;

interface TaskProgressProps {
  task: TaskStatus;
  showDetails?: boolean;
  projectId?: string; // 添加项目ID参数
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

export const TaskProgress: React.FC<TaskProgressProps> = ({ task, showDetails = true, projectId }) => {
  const [videoThumbnail, setVideoThumbnail] = useState<string | null>(null);
  const [thumbnailLoading, setThumbnailLoading] = useState(false);

  const formatTime = (timestamp: string) => {
    // 正确处理时区转换，确保显示本地时间
    const now = dayjs().tz('Asia/Shanghai');
    const taskTime = dayjs(timestamp).tz('Asia/Shanghai');
    return taskTime.from(now);
  };

  // 生成视频缩略图
  useEffect(() => {
    if (!projectId) return;

    const generateThumbnail = async () => {
      // 检查缓存
      const thumbnailCacheKey = `task_thumbnail_${task.id}`;
      const cachedThumbnail = localStorage.getItem(thumbnailCacheKey);
      if (cachedThumbnail) {
        setVideoThumbnail(cachedThumbnail);
        return;
      }

      setThumbnailLoading(true);

      try {
        const video = document.createElement('video');
        video.crossOrigin = 'anonymous';
        video.muted = true;
        video.preload = 'metadata';

        // 尝试多个可能的视频文件路径
        const possiblePaths = [
          'input/input.mp4',
          'input.mp4',
          'raw/input.mp4'
        ];

        let videoLoaded = false;

        for (const path of possiblePaths) {
          if (videoLoaded) break;

          try {
            const videoUrl = `http://localhost:8000/api/v1/projects/${projectId}/files/${path}`;
            console.log('尝试加载任务视频:', videoUrl);

            await new Promise((resolve, reject) => {
              const timeoutId = setTimeout(() => {
                reject(new Error('视频加载超时'));
              }, 5000); // 5秒超时

              video.onloadedmetadata = () => {
                clearTimeout(timeoutId);
                console.log('任务视频元数据加载成功:', videoUrl);
                video.currentTime = Math.min(3, video.duration / 4); // 取视频1/4处或3秒处的帧
              };

              video.onseeked = () => {
                clearTimeout(timeoutId);
                try {
                  const canvas = document.createElement('canvas');
                  const ctx = canvas.getContext('2d');
                  if (!ctx) {
                    reject(new Error('无法获取canvas上下文'));
                    return;
                  }

                  // 设置合适的缩略图尺寸
                  const maxWidth = 200;
                  const maxHeight = 120;
                  const aspectRatio = video.videoWidth / video.videoHeight;

                  let width = maxWidth;
                  let height = maxHeight;

                  if (aspectRatio > maxWidth / maxHeight) {
                    height = maxWidth / aspectRatio;
                  } else {
                    width = maxHeight * aspectRatio;
                  }

                  canvas.width = width;
                  canvas.height = height;
                  ctx.drawImage(video, 0, 0, width, height);

                  const thumbnail = canvas.toDataURL('image/jpeg', 0.7);
                  setVideoThumbnail(thumbnail);

                  // 缓存缩略图
                  try {
                    localStorage.setItem(thumbnailCacheKey, thumbnail);
                  } catch (e) {
                    // 如果localStorage空间不足，清理旧缓存
                    const keys = Object.keys(localStorage).filter(key => key.startsWith('task_thumbnail_'));
                    if (keys.length > 20) { // 保留最多20个任务缩略图缓存
                      keys.slice(0, 5).forEach(key => localStorage.removeItem(key));
                      localStorage.setItem(thumbnailCacheKey, thumbnail);
                    }
                  }

                  videoLoaded = true;
                  resolve(thumbnail);
                } catch (error) {
                  reject(error);
                }
              };

              video.onerror = () => {
                clearTimeout(timeoutId);
                reject(new Error(`视频加载失败: ${videoUrl}`));
              };

              video.src = videoUrl;
            });
          } catch (error) {
            console.log('尝试下一个视频路径:', error);
            continue;
          }
        }
      } catch (error) {
        console.error('生成任务缩略图失败:', error);
      } finally {
        setThumbnailLoading(false);
      }
    };

    generateThumbnail();
  }, [projectId, task.id]);

  return (
    <Card 
      size="small" 
      style={{ marginBottom: 8 }}
      styles={{
        body: { padding: 12 }
      }}
      cover={
        projectId ? (
          <div 
            style={{ 
              height: 80, 
              position: 'relative',
              background: videoThumbnail 
                ? `url(${videoThumbnail}) center/cover` 
                : 'linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              overflow: 'hidden'
            }}
          >
            {/* 缩略图加载状态 */}
            {thumbnailLoading && (
              <div style={{ 
                textAlign: 'center',
                color: 'rgba(255, 255, 255, 0.8)'
              }}>
                <LoadingOutlined 
                  style={{ 
                    fontSize: '16px', 
                    marginBottom: '2px'
                  }} 
                />
                <div style={{ 
                  fontSize: '10px',
                  fontWeight: 500
                }}>
                  生成封面中...
                </div>
              </div>
            )}
            
            {/* 无缩略图时的默认显示 */}
            {!videoThumbnail && !thumbnailLoading && (
              <div style={{ textAlign: 'center' }}>
                <PlayCircleOutlined 
                  style={{ 
                    fontSize: '24px', 
                    color: 'rgba(255, 255, 255, 0.9)',
                    marginBottom: '2px',
                    filter: 'drop-shadow(0 2px 8px rgba(0,0,0,0.3))'
                  }} 
                />
                <div style={{ 
                  color: 'rgba(255, 255, 255, 0.8)', 
                  fontSize: '10px',
                  fontWeight: 500
                }}>
                  视频封面
                </div>
              </div>
            )}
          </div>
        ) : undefined
      }
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