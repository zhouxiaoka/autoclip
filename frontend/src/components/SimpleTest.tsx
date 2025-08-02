import React, { useEffect, useState } from 'react';
import { Card, Typography } from 'antd';

const { Text } = Typography;

export const SimpleTest: React.FC = () => {
  const [count, setCount] = useState(0);
  const [tasks, setTasks] = useState<any[]>([]);

  useEffect(() => {
    console.log('🎯 SimpleTest组件已加载');
    setCount(prev => prev + 1);
  }, []);

  useEffect(() => {
    console.log('📤 开始API调用测试');
    fetch('http://localhost:8000/api/v1/tasks/project/64d5768e-7b6b-40d0-9aed-f216768a6526')
      .then(response => response.json())
      .then(data => {
        console.log('📋 API响应:', data);
        setTasks(data.data.tasks || []);
      })
      .catch(error => {
        console.error('❌ API调用失败:', error);
      });
  }, []);

  return (
    <div style={{ padding: 16 }}>
      <Card title="简单测试组件">
        <Text>组件加载次数: {count}</Text>
        <br />
        <Text>任务数量: {tasks.length}</Text>
        <br />
        <Text>任务列表:</Text>
        <ul>
          {tasks.map((task, index) => (
            <li key={index}>
              {task.task_id} - {task.status} - {task.progress}%
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}; 