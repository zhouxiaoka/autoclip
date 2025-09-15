import { useState } from 'react'
import { message } from 'antd'
import { projectApi } from '../services/api'

export const useCollectionVideoDownload = () => {
  const [isGenerating, setIsGenerating] = useState(false)

  const generateAndDownloadCollectionVideo = async (
    projectId: string, 
    collectionId: string,
    collectionTitle: string
  ) => {
    if (isGenerating) return

    setIsGenerating(true)
    
    try {
      // 直接按用户当前调整的顺序生成合集视频
      message.info('正在按您的顺序生成合集视频...')
      
      // 生成合集视频（按用户调整的顺序）
      await projectApi.generateCollectionVideo(projectId, collectionId)
      
      // 等待1秒让后端完成文件生成，然后下载
      message.success('合集视频生成成功，正在下载...')
      
      setTimeout(async () => {
        try {
          await projectApi.downloadVideo(projectId, undefined, collectionId)
          message.success('合集视频下载完成')
        } catch (downloadError) {
          console.error('下载失败:', downloadError)
          message.error('下载失败，请稍后重试')
        }
      }, 1000)
      
    } catch (error) {
      console.error('生成合集视频失败:', error)
      message.error('生成合集视频失败')
    } finally {
      setIsGenerating(false)
    }
  }

  return {
    isGenerating,
    generateAndDownloadCollectionVideo
  }
} 