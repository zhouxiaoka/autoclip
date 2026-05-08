import React from 'react'

/**
 * 外部链接处理工具
 * 在Tauri环境中安全地打开外部链接
 */

// 检测是否在Tauri环境中
const isTauri = () => {
  return typeof window !== 'undefined' && Boolean((window as any).__TAURI__ || (window as any).__TAURI_INTERNALS__)
}

/**
 * 打开外部链接
 * @param url 要打开的URL
 */
export const openExternalLink = async (url: string) => {
  try {
    if (isTauri()) {
      // 在Tauri环境中使用shell API
      const { open } = await import('@tauri-apps/plugin-shell')
      await open(url)
    } else {
      // 在Web环境中使用普通方式
      window.open(url, '_blank', 'noopener,noreferrer')
    }
  } catch (error) {
    console.error('打开外部链接失败:', error)
    // 降级处理:尝试使用window.open
    try {
      window.open(url, '_blank', 'noopener,noreferrer')
    } catch (fallbackError) {
      console.error('降级打开链接也失败:', fallbackError)
      // 最后的降级:复制链接到剪贴板
      try {
        await navigator.clipboard.writeText(url)
        alert(`链接已复制到剪贴板:${url}`)
      } catch (clipboardError) {
        console.error('复制到剪贴板失败:', clipboardError)
        alert(`请手动访问:${url}`)
      }
    }
  }
}

/**
 * 创建一个可点击的外部链接组件
 * @param url 链接地址
 * @param text 显示文本
 * @param className CSS类名
 */
export const ExternalLink: React.FC<{
  url: string
  text: string
  className?: string
}> = ({ url, text, className }) => {
  const handleClick = (e: React.MouseEvent) => {
    e.preventDefault()
    openExternalLink(url)
  }

  return (
    <a
      href={url}
      onClick={handleClick}
      className={className}
      style={{ 
        color: '#1890ff',
        cursor: 'pointer',
        textDecoration: 'underline'
      }}
    >
      {text}
    </a>
  )
}
