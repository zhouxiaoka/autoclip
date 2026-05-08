import { message } from 'antd'

export async function validateApiConfigBeforeProjectCreation(): Promise<boolean> {
  try {
    return true
  } catch (error) {
    console.error('API配置检查失败:', error)
    message.error('API配置检查失败')
    return false
  }
}
