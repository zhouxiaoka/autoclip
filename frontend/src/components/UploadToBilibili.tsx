import React from 'react'
import { Card, Tag, Space, Typography } from 'antd'
import { BILIBILI_PARTITIONS } from '../services/uploadApi'

const { Title, Text } = Typography

interface UploadToBilibiliProps {
  partitionId?: number
}

const UploadToBilibili: React.FC<UploadToBilibiliProps> = ({ partitionId }) => {
  // 获取分区名称
  const getPartitionName = (id: number) => {
    const partition = BILIBILI_PARTITIONS.find(p => p.id === id)
    return partition ? partition.name : '未知分区'
  }

  return (
    <Card
      title={
        <Space>
          <span>B站分区信息</span>
          {partitionId && (
            <Tag color="blue">当前分区: {getPartitionName(partitionId)}</Tag>
          )}
        </Space>
      }
      size="small"
      style={{ marginBottom: '16px' }}
    >
      <div>
        <Text type="secondary">
          支持的分区类型：动画、游戏、音乐、知识、娱乐、影视、科技数码等
        </Text>
        <div style={{ marginTop: '12px' }}>
          <Text strong>分区ID: </Text>
          <Text code>{partitionId || '未设置'}</Text>
        </div>
      </div>
    </Card>
  )
}

export default UploadToBilibili

