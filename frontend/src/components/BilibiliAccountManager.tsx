import React, { useState, useEffect } from 'react'
import { Card, Button, Modal, Form, Input, Table, Tag, Space, message, Popconfirm, Tabs, Alert, Typography, Divider } from 'antd'
import { PlusOutlined, DeleteOutlined, UserOutlined, CheckCircleOutlined, CloseCircleOutlined, QrcodeOutlined, KeyOutlined, WechatOutlined, QqOutlined, ExclamationCircleOutlined, QuestionCircleOutlined } from '@ant-design/icons'
import { uploadApi, BilibiliAccount } from '../services/uploadApi'
import CookieHelper from './CookieHelper'

const { TextArea } = Input
const { Text, Paragraph } = Typography
const { TabPane } = Tabs

interface LoginMethod {
  id: string
  name: string
  description: string
  icon: string
  recommended: boolean
  risk_level: string
}

const BilibiliAccountManager: React.FC = () => {
  const [accounts, setAccounts] = useState<BilibiliAccount[]>([])
  const [loading, setLoading] = useState(false)
  const [modalVisible, setModalVisible] = useState(false)
  const [loginMethods, setLoginMethods] = useState<LoginMethod[]>([])
  const [activeTab, setActiveTab] = useState('cookie')
  const [cookieHelperVisible, setCookieHelperVisible] = useState(false)
  
  // 表单相关状态
  const [passwordForm] = Form.useForm()
  const [cookieForm] = Form.useForm()
  const [qrSessionId, setQrSessionId] = useState<string>('')
  const [qrLoginStatus, setQrLoginStatus] = useState<string>('')
  const [qrCodeUrl, setQrCodeUrl] = useState<string>('')
  const [statusCheckInterval, setStatusCheckInterval] = useState<NodeJS.Timeout | null>(null)

  // 获取账号列表
  const fetchAccounts = async () => {
    try {
      setLoading(true)
      const data = await uploadApi.getAccounts()
      setAccounts(data)
    } catch (error: any) {
      message.error('获取账号列表失败: ' + (error.message || '未知错误'))
    } finally {
      setLoading(false)
    }
  }

  // 获取登录方式列表
  const fetchLoginMethods = async () => {
    try {
      const response = await uploadApi.getLoginMethods()
      setLoginMethods(response.methods)
    } catch (error: any) {
      console.error('获取登录方式失败:', error)
    }
  }

  useEffect(() => {
    fetchAccounts()
    fetchLoginMethods()
    
    // 清理定时器
    return () => {
      if (statusCheckInterval) {
        clearInterval(statusCheckInterval)
      }
    }
  }, [])

  // 账号密码登录
  const handlePasswordLogin = async (values: any) => {
    try {
      setLoading(true)
      const account = await uploadApi.passwordLogin(values.username, values.password, values.nickname)
      message.success('账号密码登录成功！')
      setModalVisible(false)
      passwordForm.resetFields()
      fetchAccounts()
    } catch (error: any) {
      message.error('账号密码登录失败: ' + (error.message || '未知错误'))
    } finally {
      setLoading(false)
    }
  }

  // Cookie导入登录
  const handleCookieLogin = async (values: any) => {
    try {
      setLoading(true)
      
      // 解析Cookie字符串
      const cookieStr = values.cookies.trim()
      const cookies: Record<string, string> = {}
      
      cookieStr.split(';').forEach(cookie => {
        const [key, value] = cookie.trim().split('=')
        if (key && value) {
          cookies[key] = value
        }
      })
      
      if (Object.keys(cookies).length === 0) {
        message.error('Cookie格式不正确，请检查输入')
        return
      }
      
      const account = await uploadApi.cookieLogin(cookies, values.nickname)
      message.success('Cookie导入成功！')
      setModalVisible(false)
      cookieForm.resetFields()
      fetchAccounts()
    } catch (error: any) {
      message.error('Cookie导入失败: ' + (error.message || '未知错误'))
    } finally {
      setLoading(false)
    }
  }

  // 开始二维码登录
  const startQRLogin = async (nickname?: string) => {
    try {
      setLoading(true)
      
      // 清除之前的轮询
      if (statusCheckInterval) {
        clearInterval(statusCheckInterval)
        setStatusCheckInterval(null)
      }
      
      const response = await uploadApi.startQRLogin(nickname)
      setQrSessionId(response.session_id)
      setQrLoginStatus(response.status)
      
      // 开始轮询登录状态
      let pollCount = 0
      const maxPolls = 60
      
      const interval = setInterval(async () => {
        try {
          pollCount++
          if (pollCount > maxPolls) {
            message.error('二维码登录超时，请重试')
            setQrSessionId('')
            setQrLoginStatus('')
            setQrCodeUrl('')
            clearInterval(interval)
            return
          }
          
          const statusResponse = await uploadApi.checkQRLoginStatus(response.session_id)
          setQrLoginStatus(statusResponse.status)
          
          if (statusResponse.qr_code) {
            setQrCodeUrl(statusResponse.qr_code)
          }
          
          if (statusResponse.status === 'success') {
            message.success('二维码登录成功！')
            clearInterval(interval)
            setModalVisible(false)
            fetchAccounts()
          } else if (statusResponse.status === 'failed') {
            message.error('二维码登录失败，请重试')
            clearInterval(interval)
          }
        } catch (error: any) {
          console.error('检查登录状态失败:', error)
        }
      }, 1000)
      
      setStatusCheckInterval(interval)
      
    } catch (error: any) {
      message.error('启动二维码登录失败: ' + (error.message || '未知错误'))
    } finally {
      setLoading(false)
    }
  }

  // 删除账号
  const handleDeleteAccount = async (accountId: string) => {
    try {
      await uploadApi.deleteAccount(accountId)
      message.success('账号删除成功')
      fetchAccounts()
    } catch (error: any) {
      message.error('删除账号失败: ' + (error.message || '未知错误'))
    }
  }

  // 获取风险等级标签
  const getRiskLevelTag = (riskLevel: string) => {
    switch (riskLevel) {
      case 'low':
        return <Tag color="green">低风险</Tag>
      case 'medium':
        return <Tag color="orange">中风险</Tag>
      case 'high':
        return <Tag color="red">高风险</Tag>
      default:
        return <Tag>未知</Tag>
    }
  }

  // 获取推荐标签
  const getRecommendedTag = (recommended: boolean) => {
    return recommended ? <Tag color="blue">推荐</Tag> : null
  }

  const columns = [
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
    },
    {
      title: '昵称',
      dataIndex: 'nickname',
      key: 'nickname',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => (
        <Tag color={status === 'active' ? 'green' : 'red'}>
          {status === 'active' ? '正常' : '异常'}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_, record: BilibiliAccount) => (
        <Space size="middle">
          <Popconfirm
            title="确定要删除这个账号吗？"
            onConfirm={() => handleDeleteAccount(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="text" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <Card title="B站账号管理" extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => setModalVisible(true)}>添加账号</Button>}>
      <Table
        columns={columns}
        dataSource={accounts}
        rowKey="id"
        loading={loading}
        pagination={false}
      />

      <Modal
        title="添加B站账号"
        open={modalVisible}
        onCancel={() => {
          setModalVisible(false)
          setQrSessionId('')
          setQrLoginStatus('')
          setQrCodeUrl('')
          if (statusCheckInterval) {
            clearInterval(statusCheckInterval)
            setStatusCheckInterval(null)
          }
        }}
        footer={null}
        width={600}
      >
        <Alert
          message="登录方式说明"
          description="为了避免B站风控，建议使用Cookie导入方式。扫码登录可能触发风控机制。"
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
        />

        <Tabs activeKey={activeTab} onChange={setActiveTab}>
          <TabPane tab="Cookie导入" key="cookie">
            <Form form={cookieForm} onFinish={handleCookieLogin} layout="vertical">
              <Form.Item
                name="nickname"
                label="昵称"
                rules={[{ required: true, message: '请输入昵称' }]}
              >
                <Input placeholder="请输入账号昵称" />
              </Form.Item>
              
                             <Form.Item
                 name="cookies"
                 label={
                   <Space>
                     <span>Cookie</span>
                     <Button 
                       type="link" 
                       size="small" 
                       icon={<QuestionCircleOutlined />}
                       onClick={() => setCookieHelperVisible(true)}
                     >
                       获取帮助
                     </Button>
                   </Space>
                 }
                 rules={[{ required: true, message: '请输入Cookie' }]}
               >
                 <TextArea
                   rows={6}
                   placeholder="请从浏览器开发者工具中复制Cookie，格式如：SESSDATA=xxx; bili_jct=xxx; DedeUserID=xxx"
                 />
               </Form.Item>
              
              <Form.Item>
                <Button type="primary" htmlType="submit" loading={loading} block>
                  导入Cookie
                </Button>
              </Form.Item>
            </Form>
            
                         <Divider />
             <Paragraph type="secondary" style={{ fontSize: '12px' }}>
               <Text strong>快速获取Cookie：</Text>
               <br />
               点击上方的"获取帮助"按钮，查看详细的Cookie获取步骤指南
             </Paragraph>
          </TabPane>

          <TabPane tab="账号密码" key="password">
            <Form form={passwordForm} onFinish={handlePasswordLogin} layout="vertical">
              <Form.Item
                name="username"
                label="用户名"
                rules={[{ required: true, message: '请输入用户名' }]}
              >
                <Input placeholder="请输入B站用户名或手机号" />
              </Form.Item>
              
              <Form.Item
                name="password"
                label="密码"
                rules={[{ required: true, message: '请输入密码' }]}
              >
                <Input.Password placeholder="请输入密码" />
              </Form.Item>
              
              <Form.Item
                name="nickname"
                label="昵称"
                rules={[{ required: true, message: '请输入昵称' }]}
              >
                <Input placeholder="请输入账号昵称" />
              </Form.Item>
              
              <Form.Item>
                <Button type="primary" htmlType="submit" loading={loading} block>
                  登录
                </Button>
              </Form.Item>
            </Form>
            
            <Alert
              message="注意"
              description="账号密码登录可能需要处理验证码，如果遇到问题建议使用Cookie导入方式。"
              type="warning"
              showIcon
            />
          </TabPane>

          <TabPane tab="扫码登录" key="qr">
            <div style={{ textAlign: 'center' }}>
              {!qrSessionId ? (
                <div>
                  <Form.Item label="昵称">
                    <Input placeholder="请输入账号昵称（可选）" />
                  </Form.Item>
                  <Button 
                    type="primary" 
                    icon={<QrcodeOutlined />}
                    onClick={() => startQRLogin()}
                    loading={loading}
                    block
                  >
                    开始扫码登录
                  </Button>
                </div>
              ) : (
                <div>
                  {qrCodeUrl && (
                    <div style={{ marginBottom: '16px' }}>
                      <img src={qrCodeUrl} alt="二维码" style={{ maxWidth: '200px' }} />
                    </div>
                  )}
                  
                  {qrLoginStatus === 'pending' && (
                    <p>正在生成二维码...</p>
                  )}
                  
                  {qrLoginStatus === 'processing' && (
                    <p>请使用B站APP扫描二维码</p>
                  )}
                  
                  {qrLoginStatus === 'success' && (
                    <p style={{ color: '#52c41a' }}>✅ 登录成功！</p>
                  )}
                  
                  {qrLoginStatus === 'failed' && (
                    <p style={{ color: '#ff4d4f' }}>❌ 登录失败，请重试</p>
                  )}
                </div>
              )}
            </div>
            
            <Alert
              message="风险提示"
              description="扫码登录可能触发B站风控机制，建议优先使用Cookie导入方式。"
              type="error"
              showIcon
            />
          </TabPane>
                 </Tabs>
       </Modal>

       <CookieHelper 
         visible={cookieHelperVisible}
         onClose={() => setCookieHelperVisible(false)}
       />
     </Card>
   )
 }

export default BilibiliAccountManager
