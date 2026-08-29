import { useState } from 'react'
import { message } from 'antd'
import { projectApi } from '../services/api'

export const useCollectionVideoDownload = () => {
  const [isGenerating, setIsGenerating] = useState(false)

  const generateAndDownloadCollectionVideo = async (
    projectId: string, 
    collectionId: string,
    _collectionTitle: string
  ) => {
    if (isGenerating) return

    setIsGenerating(true)
    
    try {
      // 直接按用户当前调整的顺序生成合集视频
      message.info('Generating collection video in your current order…')
      
      await projectApi.generateCollectionVideo(projectId, collectionId)
      
      message.success('Collection video ready — starting download…')
      
      setTimeout(async () => {
        try {
          await projectApi.downloadVideo(projectId, undefined, collectionId)
          message.success('Collection video downloaded')
        } catch (downloadError) {
          console.error('Download failed:', downloadError)
          message.error('Download failed — please try again')
        }
      }, 1000)
      
    } catch (error) {
      console.error('Failed to generate collection video:', error)
      message.error('Failed to generate collection video')
    } finally {
      setIsGenerating(false)
    }
  }

  return {
    isGenerating,
    generateAndDownloadCollectionVideo
  }
} 