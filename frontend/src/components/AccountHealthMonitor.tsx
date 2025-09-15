import React, { useState, useEffect } from 'react';
import {
  Card,
  Table,
  Tag,
  Button,
  Space,
  Tooltip,
  Progress,
  Modal,
  message,
  Statistic,
  Row,
  Col,
  Alert,
  Spin,
  Badge
} from 'antd';
import {
  CheckCircleOutlined,
  ExclamationCircleOutlined,
  CloseCircleOutlined,
  QuestionCircleOutlined,
  ReloadOutlined,
  SettingOutlined,
  ClockCircleOutlined
} from '@ant-design/icons';
// 移除date-fns依赖，使用内置方法

// 接口定义
interface AccountHealth {
  account_id: number;
  username: string;
  status: 'healthy' | 'warning' | 'critical' | 'unknown';
  message: string;
  details: {
    cookie?: {
      status: string;
      message: string;
      expires_in?: number;
    };
    login?: {
      status: string;
      message: string;
      user_info?: {
        uname: string;
        mid: number;
        level: number;
      };
    };
    upload?: {
      status: string;
      message: string;
    };
  };
  last_check: string;
  expires_in?: number;
}

interface HealthSummary {
  total_accounts: number;
  healthy_count: number;
  warning_count: number;
  critical_count: number;
  unknown_count: number;
  accounts: AccountHealth[];
  last_updated: string;
}

interface AccountHealthMonitorProps {
  onRefresh?: () => void;
}

const AccountHealthMonitor: React.FC<AccountHealthMonitorProps> = ({ onRefresh }) => {
  const [healthData, setHealthData] = useState<HealthSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState<number[]>([]);
  const [detailsVisible, setDetailsVisible] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState<AccountHealth | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [refreshInterval, setRefreshInterval] = useState<number | null>(null);

  // 时间格式化函数
  const getTimeAgo = (dateString: string) => {
    const now = new Date();
    const date = new Date(dateString);
    const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);
    
    if (diffInSeconds < 60) {
      return '刚刚';
    } else if (diffInSeconds < 3600) {
      const minutes = Math.floor(diffInSeconds / 60);
      return `${minutes}分钟前`;
    } else if (diffInSeconds < 86400) {
      const hours = Math.floor(diffInSeconds / 3600);
      return `${hours}小时前`;
    } else {
      const days = Math.floor(diffInSeconds / 86400);
      return `${days}天前`;
    }
  };

  // 获取健康状态摘要
  const fetchHealthSummary = async (forceCheck = false) => {
    try {
      setLoading(true);
      const endpoint = forceCheck ? '/api/v1/health/check' : '/api/v1/health/summary';
      const method = forceCheck ? 'POST' : 'GET';
      const body = forceCheck ? JSON.stringify({ force_check: true }) : undefined;
      
      const response = await fetch(endpoint, {
        method,
        headers: {
          'Content-Type': 'application/json',
        },
        body,
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const data = await response.json();
      setHealthData(data);
      
      if (forceCheck) {
        message.success('健康检查完成');
      }
    } catch (error) {
      console.error('获取健康状态失败:', error);
      message.error('获取健康状态失败');
    } finally {
      setLoading(false);
    }
  };

  // 检查单个账号
  const checkSingleAccount = async (accountId: number, forceCheck = true) => {
    try {
      setRefreshing(prev => [...prev, accountId]);
      
      const response = await fetch(`/api/v1/health/check/${accountId}?force_check=${forceCheck}`, {
        method: 'GET',
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const updatedAccount = await response.json();
      
      // 更新健康数据
      setHealthData(prev => {
        if (!prev) return prev;
        
        const updatedAccounts = prev.accounts.map(account => 
          account.account_id === accountId ? updatedAccount : account
        );
        
        // 重新计算统计数据
        const statusCounts = {
          healthy: 0,
          warning: 0,
          critical: 0,
          unknown: 0
        };
        
        updatedAccounts.forEach(account => {
          statusCounts[account.status as keyof typeof statusCounts]++;
        });
        
        return {
          ...prev,
          accounts: updatedAccounts,
          healthy_count: statusCounts.healthy,
          warning_count: statusCounts.warning,
          critical_count: statusCounts.critical,
          unknown_count: statusCounts.unknown,
          last_updated: new Date().toISOString()
        };
      });
      
      message.success(`账号 ${updatedAccount.username} 检查完成`);
    } catch (error) {
      console.error('检查账号失败:', error);
      message.error('检查账号失败');
    } finally {
      setRefreshing(prev => prev.filter(id => id !== accountId));
    }
  };

  // 刷新Cookie
  const refreshCookie = async (accountId: number) => {
    try {
      const response = await fetch('/api/v1/health/refresh-cookie', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          account_id: accountId,
          auto_refresh: true
        }),
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const result = await response.json();
      
      if (result.success) {
        message.success(result.message);
      } else {
        message.warning(result.message);
      }
    } catch (error) {
      console.error('刷新Cookie失败:', error);
      message.error('刷新Cookie失败');
    }
  };

  // 获取状态标签
  const getStatusTag = (status: string) => {
    const statusConfig = {
      healthy: { color: 'success', icon: <CheckCircleOutlined />, text: '健康' },
      warning: { color: 'warning', icon: <ExclamationCircleOutlined />, text: '警告' },
      critical: { color: 'error', icon: <CloseCircleOutlined />, text: '严重' },
      unknown: { color: 'default', icon: <QuestionCircleOutlined />, text: '未知' }
    };
    
    const config = statusConfig[status as keyof typeof statusConfig] || statusConfig.unknown;
    
    return (
      <Tag color={config.color} icon={config.icon}>
        {config.text}
      </Tag>
    );
  };

  // 获取过期时间进度条
  const getExpirationProgress = (expiresIn?: number) => {
    if (expiresIn === undefined || expiresIn === null) {
      return null;
    }
    
    const totalDays = 30; // 假设Cookie总有效期为30天
    const percentage = Math.max(0, Math.min(100, (expiresIn / totalDays) * 100));
    
    let status: 'success' | 'normal' | 'exception' = 'success';
    if (expiresIn <= 0) {
      status = 'exception';
    } else if (expiresIn <= 7) {
      status = 'normal';
    }
    
    return (
      <Tooltip title={`还有 ${expiresIn} 天过期`}>
        <Progress
          percent={percentage}
          status={status}
          size="small"
          showInfo={false}
          strokeWidth={6}
        />
      </Tooltip>
    );
  };

  // 表格列定义
  const columns = [
    {
      title: '账号',
      dataIndex: 'username',
      key: 'username',
      render: (username: string, record: AccountHealth) => (
        <Space>
          <span>{username}</span>
          {record.details.login?.user_info && (
            <Tooltip title={`等级: ${record.details.login.user_info.level}`}>
              <Badge count={record.details.login.user_info.level} color="blue" />
            </Tooltip>
          )}
        </Space>
      ),
    },
    {
      title: '健康状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => getStatusTag(status),
    },
    {
      title: 'Cookie状态',
      key: 'cookie_status',
      render: (record: AccountHealth) => (
        <Space direction="vertical" size="small">
          {getStatusTag(record.details.cookie?.status || 'unknown')}
          {getExpirationProgress(record.expires_in)}
        </Space>
      ),
    },
    {
      title: '最后检查',
      dataIndex: 'last_check',
      key: 'last_check',
      render: (lastCheck: string) => (
        <Tooltip title={new Date(lastCheck).toLocaleString()}>
          <Space>
            <ClockCircleOutlined />
            {getTimeAgo(lastCheck)}
          </Space>
        </Tooltip>
      ),
    },
    {
      title: '操作',
      key: 'actions',
      render: (record: AccountHealth) => (
        <Space>
          <Button
            type="text"
            icon={<ReloadOutlined />}
            loading={refreshing.includes(record.account_id)}
            onClick={() => checkSingleAccount(record.account_id)}
          >
            检查
          </Button>
          <Button
            type="text"
            icon={<SettingOutlined />}
            onClick={() => {
              setSelectedAccount(record);
              setDetailsVisible(true);
            }}
          >
            详情
          </Button>
          {record.status === 'critical' || record.status === 'warning' ? (
            <Button
              type="text"
              danger
              onClick={() => refreshCookie(record.account_id)}
            >
              刷新Cookie
            </Button>
          ) : null}
        </Space>
      ),
    },
  ];

  // 组件挂载时获取数据
  useEffect(() => {
    fetchHealthSummary();
  }, []);

  // 自动刷新
  useEffect(() => {
    if (autoRefresh) {
      const interval = setInterval(() => {
        fetchHealthSummary();
      }, 60000); // 每分钟刷新一次
      setRefreshInterval(interval);
    } else {
      if (refreshInterval) {
        clearInterval(refreshInterval);
        setRefreshInterval(null);
      }
    }
    
    return () => {
      if (refreshInterval) {
        clearInterval(refreshInterval);
      }
    };
  }, [autoRefresh]);

  return (
    <div>
      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="总账号数"
              value={healthData?.total_accounts || 0}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="健康账号"
              value={healthData?.healthy_count || 0}
              valueStyle={{ color: '#3f8600' }}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="警告账号"
              value={healthData?.warning_count || 0}
              valueStyle={{ color: '#cf1322' }}
              prefix={<ExclamationCircleOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="严重问题"
              value={healthData?.critical_count || 0}
              valueStyle={{ color: '#cf1322' }}
              prefix={<CloseCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {/* 操作栏 */}
      <Card style={{ marginBottom: 16 }}>
        <Space>
          <Button
            type="primary"
            icon={<ReloadOutlined />}
            loading={loading}
            onClick={() => fetchHealthSummary(true)}
          >
            全部检查
          </Button>
          <Button
            icon={<ReloadOutlined />}
            loading={loading}
            onClick={() => fetchHealthSummary()}
          >
            刷新状态
          </Button>
          <Button
            type={autoRefresh ? 'primary' : 'default'}
            onClick={() => setAutoRefresh(!autoRefresh)}
          >
            {autoRefresh ? '停止自动刷新' : '开启自动刷新'}
          </Button>
        </Space>
        
        {healthData?.last_updated && (
          <div style={{ float: 'right', color: '#666' }}>
            最后更新: {getTimeAgo(healthData.last_updated)}
          </div>
        )}
      </Card>

      {/* 警告信息 */}
      {healthData && (healthData.critical_count > 0 || healthData.warning_count > 0) && (
        <Alert
          message="账号健康警告"
          description={`发现 ${healthData.critical_count} 个严重问题和 ${healthData.warning_count} 个警告，请及时处理`}
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
        />
      )}

      {/* 账号列表 */}
      <Card title="账号健康状态">
        <Spin spinning={loading}>
          <Table
            columns={columns}
            dataSource={healthData?.accounts || []}
            rowKey="account_id"
            pagination={{
              pageSize: 10,
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total) => `共 ${total} 个账号`,
            }}
          />
        </Spin>
      </Card>

      {/* 详情弹窗 */}
      <Modal
        title={`账号详情 - ${selectedAccount?.username}`}
        open={detailsVisible}
        onCancel={() => setDetailsVisible(false)}
        footer={[
          <Button key="close" onClick={() => setDetailsVisible(false)}>
            关闭
          </Button>,
          <Button
            key="refresh"
            type="primary"
            icon={<ReloadOutlined />}
            onClick={() => {
              if (selectedAccount) {
                checkSingleAccount(selectedAccount.account_id);
              }
            }}
          >
            重新检查
          </Button>,
        ]}
        width={600}
      >
        {selectedAccount && (
          <div>
            <Row gutter={16}>
              <Col span={12}>
                <Card title="基本信息" size="small">
                  <p><strong>账号ID:</strong> {selectedAccount.account_id}</p>
                  <p><strong>用户名:</strong> {selectedAccount.username}</p>
                  <p><strong>整体状态:</strong> {getStatusTag(selectedAccount.status)}</p>
                  <p><strong>状态消息:</strong> {selectedAccount.message}</p>
                </Card>
              </Col>
              <Col span={12}>
                <Card title="检查时间" size="small">
                  <p><strong>最后检查:</strong> {new Date(selectedAccount.last_check).toLocaleString()}</p>
                  {selectedAccount.expires_in !== undefined && (
                    <p><strong>Cookie过期:</strong> {selectedAccount.expires_in} 天后</p>
                  )}
                </Card>
              </Col>
            </Row>
            
            <Card title="详细状态" size="small" style={{ marginTop: 16 }}>
              {selectedAccount.details.cookie && (
                <div style={{ marginBottom: 12 }}>
                  <strong>Cookie状态:</strong> {getStatusTag(selectedAccount.details.cookie.status)}
                  <p>{selectedAccount.details.cookie.message}</p>
                </div>
              )}
              
              {selectedAccount.details.login && (
                <div style={{ marginBottom: 12 }}>
                  <strong>登录状态:</strong> {getStatusTag(selectedAccount.details.login.status)}
                  <p>{selectedAccount.details.login.message}</p>
                  {selectedAccount.details.login.user_info && (
                    <p>用户信息: {selectedAccount.details.login.user_info.uname} (等级 {selectedAccount.details.login.user_info.level})</p>
                  )}
                </div>
              )}
              
              {selectedAccount.details.upload && (
                <div>
                  <strong>上传权限:</strong> {getStatusTag(selectedAccount.details.upload.status)}
                  <p>{selectedAccount.details.upload.message}</p>
                </div>
              )}
            </Card>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default AccountHealthMonitor;