import { useState, useEffect } from 'react'

interface FirstRunState {
  isFirstRun: boolean
  isLoading: boolean
  hasCompleted: boolean
}

export const useFirstRun = () => {
  const [state, setState] = useState<FirstRunState>({
    isFirstRun: false,
    isLoading: true,
    hasCompleted: false
  })

  useEffect(() => {
    checkFirstRun()
  }, [])

  const checkFirstRun = async () => {
    try {
      console.log('🔍 开始检查首次运行状态...')
      
      // 创建带超时的fetch请求
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 5000) // 5秒超时
      
      try {
        // 检查是否已有配置
        const response = await fetch('/api/v1/settings/', {
          signal: controller.signal
        })
        clearTimeout(timeoutId)
        
        if (response.ok) {
          const settings = await response.json()
          console.log('📋 获取到设置:', settings)
          
          // 检查是否有API Key配置
          const hasApiKey = settings.api?.api_keys?.dashscope || 
                           settings.api?.api_keys?.openai ||
                           settings.api?.api_keys?.gemini ||
                           settings.api?.api_keys?.siliconflow
          
          console.log('🔑 API Key状态:', hasApiKey)
          
          // 首次运行向导只需要检查API Key配置，不需要强制要求示例项目
          setState({
            isFirstRun: !hasApiKey,
            isLoading: false,
            hasCompleted: hasApiKey
          })
        } else {
          console.log('❌ 设置API响应失败:', response.status)
          // 如果无法获取设置，认为是首次运行
          setState({
            isFirstRun: true,
            isLoading: false,
            hasCompleted: false
          })
        }
      } catch (fetchError) {
        clearTimeout(timeoutId)
        if (fetchError instanceof Error && fetchError.name === 'AbortError') {
          console.log('⏰ API请求超时，假设为首次运行')
        } else {
          console.log('❌ API请求失败:', fetchError)
        }
        setState({
          isFirstRun: true,
          isLoading: false,
          hasCompleted: false
        })
      }
    } catch (error) {
      console.error('❌ 检查首次运行状态失败:', error)
      setState({
        isFirstRun: true,
        isLoading: false,
        hasCompleted: false
      })
    }
  }

  const markCompleted = () => {
    setState(prev => ({
      ...prev,
      isFirstRun: false,
      hasCompleted: true
    }))
  }

  return {
    ...state,
    markCompleted,
    refresh: checkFirstRun
  }
}
