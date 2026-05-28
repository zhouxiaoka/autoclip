import React from 'react'
import { Alert } from 'antd'

interface SpeechRecognitionConfigProps {
  config?: Record<string, unknown>
  onConfigChange?: (config: Record<string, unknown>) => void
}

const SpeechRecognitionConfig: React.FC<SpeechRecognitionConfigProps> = () => {
  return (
    <Alert
      type="info"
      showIcon
      message="语音识别配置暂不可用"
      description="当前版本会在未上传字幕时尝试使用后端默认 ASR 配置。"
    />
  )
}

export default SpeechRecognitionConfig
