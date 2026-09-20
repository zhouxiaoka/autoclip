/**
 * React 错误边界组件
 * 捕获子组件中的 JavaScript 错误，记录错误信息，并显示降级 UI（样式遵循 DESIGN.md：单色、无渐变）
 */

import { Component, ErrorInfo, ReactNode } from 'react'
import { errorHandler } from '../utils/errorHandler'
import { isDomDisplacementError, isPageTranslated } from '../utils/domTranslationGuard'
import { Btn } from '../ui'

interface Props {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, errorInfo: ErrorInfo) => void
  showDetails?: boolean
}

interface State {
  hasError: boolean
  error: Error | null
  errorInfo: ErrorInfo | null
  errorId: string
}

const ISSUE_URL = 'https://github.com/zhouxiaoka/autoclip/issues/new/choose'

const preStyle: React.CSSProperties = {
  margin: 0,
  padding: 12,
  fontFamily: 'var(--ac-font-mono)',
  fontSize: 11.5,
  lineHeight: 1.5,
  color: 'var(--ac-sub)',
  background: 'var(--ac-line-2)',
  border: '1px solid var(--ac-line)',
  borderRadius: 10,
  overflow: 'auto',
  maxHeight: 220,
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
}

class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: ''
    }
  }

  static getDerivedStateFromError(error: Error): Partial<State> {
    // 更新 state 使下一次渲染能够显示降级后的 UI
    return {
      hasError: true,
      error,
      errorId: `error_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    this.setState({ errorInfo })
    errorHandler.handleError(error, 'ReactErrorBoundary')
    if (this.props.onError) {
      this.props.onError(error, errorInfo)
    }
    console.group('React Error Boundary')
    console.error('Error:', error)
    console.error('Error Info:', errorInfo)
    console.error('Error ID:', this.state.errorId)
    console.groupEnd()
  }

  handleReload = () => {
    this.setState({ hasError: false, error: null, errorInfo: null, errorId: '' })
    window.location.reload()
  }

  handleGoHome = () => {
    this.setState({ hasError: false, error: null, errorInfo: null, errorId: '' })
    // HashRouter：首页是 #/，直接改 href 会保留当前 hash 导致原地刷新
    window.location.hash = '#/'
    window.location.reload()
  }

  handleReportError = () => {
    const { error, errorInfo, errorId } = this.state
    if (!error) return
    const errorReport = {
      id: errorId,
      message: error.message,
      stack: error.stack,
      componentStack: errorInfo?.componentStack,
      timestamp: new Date().toISOString(),
      userAgent: navigator.userAgent,
      url: window.location.href,
      translated: isPageTranslated(),
    }
    console.log('Error Report:', errorReport)
    window.open(ISSUE_URL, '_blank', 'noopener')
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children
    }
    if (this.props.fallback) {
      return this.props.fallback
    }

    const { error, errorInfo, errorId } = this.state
    // 浏览器「翻译此页」移动了 DOM 节点导致 React 更新失败（#100），给出能自救的提示
    const translationSuspected = isDomDisplacementError(error) || isPageTranslated()

    return (
      <div
        translate="no"
        style={{
          minHeight: '100vh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 24,
          background: 'var(--ac-bg)',
          color: 'var(--ac-ink)',
          fontFamily: 'var(--ac-font-sans)',
        }}
      >
        <div
          style={{
            width: 'min(560px, 100%)',
            background: 'var(--ac-card)',
            border: '1px solid var(--ac-line)',
            borderRadius: 16,
            padding: '32px 32px 28px',
          }}
        >
          <div className="ac-eyebrow">页面出错</div>
          <h1 style={{ margin: '10px 0 0', fontSize: 20, fontWeight: 600, lineHeight: 1.3, letterSpacing: '-0.01em' }}>
            {translationSuspected ? '浏览器翻译打断了页面渲染' : '这个页面遇到了意外错误'}
          </h1>
          <p style={{ margin: '8px 0 0', fontSize: 13.5, color: 'var(--ac-sub)', lineHeight: 1.6, maxWidth: '60ch' }}>
            {translationSuspected ? (
              <>
                检测到网页正在被浏览器翻译（Chrome / Edge「翻译此页」）。翻译会改写页面结构，导致界面在切换选项时崩溃。
                请在地址栏右侧关闭翻译、恢复原文后再刷新。
                <span style={{ display: 'block', marginTop: 6 }}>
                  Page translation (Chrome / Edge “Translate this page”) rewrites the DOM and breaks the UI.
                  Please turn translation off, show the original page, then reload.
                </span>
              </>
            ) : (
              '问题已记录到本地日志。先试试刷新；仍然出现的话把下面的错误信息带上，到 GitHub 提一个 issue。'
            )}
          </p>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 24, flexWrap: 'wrap' }}>
            <Btn variant="cta" onClick={this.handleReload}>刷新页面</Btn>
            <Btn onClick={this.handleGoHome}>返回首页</Btn>
            <Btn variant="text" onClick={this.handleReportError}>报告问题</Btn>
          </div>

          {error && (
            <details style={{ marginTop: 24 }} open={!!this.props.showDetails}>
              <summary style={{ cursor: 'pointer', fontSize: 12.5, color: 'var(--ac-muted)', userSelect: 'none' }}>
                错误详情 <span className="ac-mono" style={{ fontFamily: 'var(--ac-font-mono)' }}>{errorId}</span>
              </summary>
              <div style={{ display: 'grid', gap: 10, marginTop: 12 }}>
                <pre style={preStyle}>{error.message}</pre>
                {this.props.showDetails && error.stack && <pre style={preStyle}>{error.stack}</pre>}
                {this.props.showDetails && errorInfo?.componentStack && <pre style={preStyle}>{errorInfo.componentStack}</pre>}
              </div>
            </details>
          )}
        </div>
      </div>
    )
  }
}

export default ErrorBoundary
