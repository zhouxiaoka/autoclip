/**
 * React 错误边界组件
 * 捕获子组件中的 JavaScript 错误，记录错误信息，并显示降级 UI
 */

import { Component, ErrorInfo, ReactNode } from 'react'
import { Result, Button, Card, Typography, Space, Collapse } from 'antd'
import { ReloadOutlined, BugOutlined, HomeOutlined } from '@ant-design/icons'
import { errorHandler } from '../utils/errorHandler'

const { Title, Text, Paragraph } = Typography
const { Panel } = Collapse

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
    // 记录错误信息
    this.setState({ errorInfo })
    
    // 使用错误处理器处理错误
    errorHandler.handleError(error, 'ReactErrorBoundary')
    
    // 调用自定义错误处理函数
    if (this.props.onError) {
      this.props.onError(error, errorInfo)
    }
    
    // 记录详细的错误信息
    console.group('🚨 React Error Boundary')
    console.error('Error:', error)
    console.error('Error Info:', errorInfo)
    console.error('Error ID:', this.state.errorId)
    console.groupEnd()
  }

  handleReload = () => {
    // 清除错误状态
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: ''
    })
    
    // 刷新页面
    window.location.reload()
  }

  handleGoHome = () => {
    // 清除错误状态
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
      errorId: ''
    })
    
    // 跳转到首页
    window.location.href = '/'
  }

  handleReportError = () => {
    const { error, errorInfo, errorId } = this.state
    
    if (!error) return
    
    // 创建错误报告
    const errorReport = {
      id: errorId,
      message: error.message,
      stack: error.stack,
      componentStack: errorInfo?.componentStack,
      timestamp: new Date().toISOString(),
      userAgent: navigator.userAgent,
      url: window.location.href,
      userId: localStorage.getItem('userId') || 'anonymous'
    }
    
    // 这里可以发送错误报告到服务器
    console.log('Error Report:', errorReport)
    
    // 显示成功消息
    // message.success('错误报告已提交，感谢您的反馈！')
  }

  render() {
    if (this.state.hasError) {
      // 如果有自定义的降级 UI，使用它
      if (this.props.fallback) {
        return this.props.fallback
      }
      
      const { error, errorInfo, errorId } = this.state
      
      return (
        <div style={{ 
          minHeight: '100vh', 
          display: 'flex', 
          alignItems: 'center', 
          justifyContent: 'center',
          padding: '20px',
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)'
        }}>
          <Card 
            style={{ 
              maxWidth: '600px', 
              width: '100%',
              boxShadow: '0 8px 32px rgba(0,0,0,0.1)',
              borderRadius: '12px'
            }}
          >
            <Result
              status="error"
              title="页面出现错误"
              subTitle="抱歉，页面遇到了一个意外错误。我们已经记录了这个问题，请尝试以下解决方案："
              extra={
                <Space direction="vertical" size="middle" style={{ width: '100%' }}>
                  <Space>
                    <Button 
                      type="primary" 
                      icon={<ReloadOutlined />} 
                      onClick={this.handleReload}
                    >
                      刷新页面
                    </Button>
                    <Button 
                      icon={<HomeOutlined />} 
                      onClick={this.handleGoHome}
                    >
                      返回首页
                    </Button>
                  </Space>
                  
                  <Button 
                    type="link" 
                    icon={<BugOutlined />}
                    onClick={this.handleReportError}
                  >
                    报告此错误
                  </Button>
                </Space>
              }
            />
            
            {/* 错误详情 */}
            {this.props.showDetails && error && (
              <div style={{ marginTop: '24px' }}>
                <Title level={5}>错误详情</Title>
                <Paragraph>
                  <Text code>错误 ID: {errorId}</Text>
                </Paragraph>
                
                <Collapse size="small">
                  <Panel header="错误信息" key="1">
                    <pre style={{ 
                      background: '#f5f5f5', 
                      padding: '12px', 
                      borderRadius: '4px',
                      fontSize: '12px',
                      overflow: 'auto',
                      maxHeight: '200px'
                    }}>
                      {error.message}
                    </pre>
                  </Panel>
                  
                  {error.stack && (
                    <Panel header="错误堆栈" key="2">
                      <pre style={{ 
                        background: '#f5f5f5', 
                        padding: '12px', 
                        borderRadius: '4px',
                        fontSize: '12px',
                        overflow: 'auto',
                        maxHeight: '300px'
                      }}>
                        {error.stack}
                      </pre>
                    </Panel>
                  )}
                  
                  {errorInfo?.componentStack && (
                    <Panel header="组件堆栈" key="3">
                      <pre style={{ 
                        background: '#f5f5f5', 
                        padding: '12px', 
                        borderRadius: '4px',
                        fontSize: '12px',
                        overflow: 'auto',
                        maxHeight: '300px'
                      }}>
                        {errorInfo.componentStack}
                      </pre>
                    </Panel>
                  )}
                </Collapse>
              </div>
            )}
            
            {/* 常见解决方案 */}
            <div style={{ marginTop: '24px' }}>
              <Title level={5}>常见解决方案</Title>
              <ul style={{ paddingLeft: '20px' }}>
                <li>刷新页面重试</li>
                <li>清除浏览器缓存和 Cookie</li>
                <li>检查网络连接</li>
                <li>尝试使用其他浏览器</li>
                <li>如果问题持续存在，请联系技术支持</li>
              </ul>
            </div>
          </Card>
        </div>
      )
    }
    
    return this.props.children
  }
}

export default ErrorBoundary
