/**
 * API配置检查工具
 * 用于在创建项目前检查API配置是否完整
 */

import { settingsApi } from '../services/api'
import { isDesktopMode } from './desktopMode'
import { message, Modal } from 'antd'
import { useNavigate } from 'react-router-dom'

export interface ApiConfigStatus {
  hasValidConfig: boolean
  missingProviders: string[]
  currentProvider?: string
  currentApiKey?: string
}

/**
 * 检查API配置是否完整
 */
export const checkApiConfig = async (): Promise<ApiConfigStatus> => {
  try {
    console.log('=== 开始API配置检查 ===')
    
    // 检查是否在Desktop模式下运行
    const isDesktop = await isDesktopMode()
    console.log('Desktop模式检查结果:', isDesktop)
    
    // 无论是否在Desktop模式，都尝试获取设置
    let settings
    try {
      settings = await settingsApi.getSettings()
      console.log('获取设置成功:', settings)
    } catch (error) {
      console.warn('获取设置失败，可能不在Desktop模式:', error)
      // 如果获取设置失败，检查是否在Desktop模式
      if (!isDesktop) {
        console.log('非Desktop模式，返回无配置状态')
        return {
          hasValidConfig: false,
          missingProviders: ['LLM API'],
          currentProvider: undefined,
          currentApiKey: undefined
        }
      }
      // Desktop模式下获取设置失败，也返回无配置
      console.log('Desktop模式下获取设置失败，返回无配置状态')
      return {
        hasValidConfig: false,
        missingProviders: ['LLM API'],
        currentProvider: undefined,
        currentApiKey: undefined
      }
    }
    
    if (!settings || !settings.api || !settings.api.api_keys) {
      console.log('设置数据不完整:', { settings, hasApi: !!settings?.api, hasApiKeys: !!settings?.api?.api_keys })
      return {
        hasValidConfig: false,
        missingProviders: ['LLM API'],
        currentProvider: undefined,
        currentApiKey: undefined
      }
    }

    const apiKeys = settings.api.api_keys
    // 修复：api_model 是模型名称，不是提供商名称
    // 需要从 api_provider 或 llm_provider 获取提供商名称
    const currentProvider = settings.api.api_provider || settings.api.llm_provider || 'dashscope'
    
    console.log('API配置详情:', {
      currentProvider,
      apiKeys: {
        dashscope: apiKeys.dashscope ? '***' + apiKeys.dashscope.slice(-4) : '未配置',
        openai: apiKeys.openai ? '***' + apiKeys.openai.slice(-4) : '未配置',
        gemini: apiKeys.gemini ? '***' + apiKeys.gemini.slice(-4) : '未配置',
        siliconflow: apiKeys.siliconflow ? '***' + apiKeys.siliconflow.slice(-4) : '未配置',
        jimeng_access: apiKeys.jimeng_access ? '***' + apiKeys.jimeng_access.slice(-4) : '未配置',
        jimeng_secret: apiKeys.jimeng_secret ? '***' + apiKeys.jimeng_secret.slice(-4) : '未配置'
      }
    })
    
    // 检查当前提供商的API Key
    let currentApiKey = ''
    let hasValidKey = false
    
    switch (currentProvider) {
      case 'dashscope':
        currentApiKey = apiKeys.dashscope || ''
        hasValidKey = !!currentApiKey.trim()
        console.log('DashScope API Key检查:', { hasKey: !!currentApiKey, keyLength: currentApiKey.length, isValid: hasValidKey })
        break
      case 'openai':
        currentApiKey = apiKeys.openai || ''
        hasValidKey = !!currentApiKey.trim()
        console.log('OpenAI API Key检查:', { hasKey: !!currentApiKey, keyLength: currentApiKey.length, isValid: hasValidKey })
        break
      case 'gemini':
        currentApiKey = apiKeys.gemini || ''
        hasValidKey = !!currentApiKey.trim()
        console.log('Gemini API Key检查:', { hasKey: !!currentApiKey, keyLength: currentApiKey.length, isValid: hasValidKey })
        break
      case 'siliconflow':
        currentApiKey = apiKeys.siliconflow || ''
        hasValidKey = !!currentApiKey.trim()
        console.log('SiliconFlow API Key检查:', { hasKey: !!currentApiKey, keyLength: currentApiKey.length, isValid: hasValidKey })
        break
      case 'jimeng':
        currentApiKey = apiKeys.jimeng_access || ''
        hasValidKey = !!(apiKeys.jimeng_access?.trim() && apiKeys.jimeng_secret?.trim())
        console.log('Jimeng API Key检查:', { 
          hasAccess: !!apiKeys.jimeng_access, 
          hasSecret: !!apiKeys.jimeng_secret, 
          isValid: hasValidKey 
        })
        break
      default:
        hasValidKey = false
        console.log('未知提供商:', currentProvider)
    }

    console.log('=== API配置检查最终结果 ===', {
      hasValidConfig: hasValidKey,
      currentProvider,
      currentApiKey: currentApiKey ? '***' + currentApiKey.slice(-4) : undefined,
      isDesktop
    })

    return {
      hasValidConfig: hasValidKey,
      missingProviders: hasValidKey ? [] : ['LLM API'],
      currentProvider,
      currentApiKey: currentApiKey ? '***' + currentApiKey.slice(-4) : undefined
    }
  } catch (error) {
    console.error('检查API配置失败:', error)
    return {
      hasValidConfig: false,
      missingProviders: ['LLM API'],
      currentProvider: undefined,
      currentApiKey: undefined
    }
  }
}

/**
 * 显示API配置缺失的提示对话框
 */
export const showApiConfigModal = (missingProviders: string[], onNavigateToSettings?: () => void) => {
  const providerNames = {
    'LLM API': 'AI模型API',
    'Speech API': '语音识别API'
  }

  const missingNames = missingProviders.map(p => providerNames[p as keyof typeof providerNames] || p).join('、')

  Modal.confirm({
    title: <span style={{ color: '#fff' }}>需要配置API</span>,
    content: (
      <div style={{ color: '#fff' }}>
        <p style={{ color: '#fff', marginBottom: '12px', fontSize: '14px' }}>创建项目需要配置以下API:</p>
        <p style={{ fontWeight: 'bold', color: '#40a9ff', marginBottom: '12px', fontSize: '16px' }}>{missingNames}</p>
        <p style={{ color: '#f0f0f0', fontSize: '14px' }}>请前往设置页面进行配置.</p>
      </div>
    ),
    okText: '去配置',
    cancelText: '取消',
    onOk: () => {
      if (onNavigateToSettings) {
        onNavigateToSettings()
      } else {
        // 直接跳转到设置页面
        window.location.href = '#/settings'
        // 强制刷新页面以确保跳转生效
        window.location.reload()
      }
    },
    icon: null,
    centered: true,
    style: { backgroundColor: '#1f1f1f' }
  })
}

/**
 * 在项目创建前检查API配置
 * 如果配置不完整，显示提示并阻止创建
 */
export const validateApiConfigBeforeProjectCreation = async (): Promise<boolean> => {
  console.log('开始验证API配置...')
  const configStatus = await checkApiConfig()
  
  console.log('API配置验证结果:', configStatus)
  
  if (!configStatus.hasValidConfig) {
    console.log('API配置无效，显示配置弹窗')
    showApiConfigModal(configStatus.missingProviders)
    return false
  }
  
  console.log('API配置有效，允许创建项目')
  return true
}

/**
 * 获取API配置状态的友好描述
 */
export const getApiConfigDescription = (status: ApiConfigStatus): string => {
  if (status.hasValidConfig) {
    return `已配置 ${status.currentProvider} API`
  } else {
    return '未配置API,无法创建项目'
  }
}
