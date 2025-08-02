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
      // 第一步：开始生成视频
      message.info('开始生成合集视频...')
      await projectApi.generateCollectionVideo(projectId, collectionId)
      
      // 第二步：等待3秒让后端完成文件生成，然后直接下载
      message.success('合集视频生成成功，正在下载...')
      
      setTimeout(async () => {
        try {
          await projectApi.downloadVideo(projectId, undefined, collectionId)
          message.success('合集视频下载完成')
        } catch (downloadError) {
          console.error('下载失败:', downloadError)
          message.error('下载失败，请稍后重试')
        }
      }, 3000) // 等待3秒让后端完成文件生成
      
    } catch (error) {
      console.error('生成合集视频失败:', error)
      message.error('导出合集视频失败')
    } finally {
      setIsGenerating(false)
    }
  }

  return {
    isGenerating,
    generateAndDownloadCollectionVideo
  }
} 