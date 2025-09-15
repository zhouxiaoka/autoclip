import { useState, useCallback, useRef, useEffect } from 'react';
import { useWebSocket, TaskProgressUpdateMessage } from './useWebSocket';
import { projectApi } from '../services/api';

export interface TaskProgressState {
  task_id: string;
  progress: number;
  step: number;
  total: number;
  phase: string;
  message: string;
  status: string;
  seq: number;
  ts: number;
  meta?: any;
  last_updated: number;
}

export interface UseTaskProgressOptions {
  userId: string;
  taskId: string;
  onProgressUpdate?: (state: TaskProgressState) => void;
  onTaskComplete?: (state: TaskProgressState) => void;
  onTaskFailed?: (state: TaskProgressState) => void;
}

export const useTaskProgress = (options: UseTaskProgressOptions) => {
  const { userId, taskId, onProgressUpdate, onTaskComplete, onTaskFailed } = options;
  
  const [taskState, setTaskState] = useState<TaskProgressState | null>(null);
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [lastSeq, setLastSeq] = useState(0);
  const [lastTs, setLastTs] = useState(0);
  const finalStateChecked = useRef(false);

  // 处理WebSocket消息
  const handleWebSocketMessage = useCallback((message: any) => {
    if (message.type === 'task_progress_update' && message.task_id === taskId) {
      const progressMessage = message as TaskProgressUpdateMessage;
      
      // 消息去重和排序检查
      if (progressMessage.seq <= lastSeq && progressMessage.ts <= lastTs) {
        console.log(`忽略过期消息: seq=${progressMessage.seq}, ts=${progressMessage.ts}`);
        return;
      }
      
      // 更新状态
      const newState: TaskProgressState = {
        task_id: progressMessage.task_id,
        progress: progressMessage.progress,
        step: progressMessage.step,
        total: progressMessage.total,
        phase: progressMessage.phase,
        message: progressMessage.message,
        status: progressMessage.status,
        seq: progressMessage.seq,
        ts: progressMessage.ts,
        meta: progressMessage.meta,
        last_updated: Date.now()
      };
      
      setTaskState(newState);
      setLastSeq(progressMessage.seq);
      setLastTs(progressMessage.ts);
      
      // 触发回调
      onProgressUpdate?.(newState);
      
      // 检查终态
      if (progressMessage.status === 'DONE') {
        onTaskComplete?.(newState);
        // 延迟进行终态校准
        setTimeout(() => performFinalStateCheck(), 1000);
      } else if (progressMessage.status === 'FAIL') {
        onTaskFailed?.(newState);
        // 延迟进行终态校准
        setTimeout(() => performFinalStateCheck(), 1000);
      }
    }
  }, [taskId, lastSeq, lastTs, onProgressUpdate, onTaskComplete, onTaskFailed]);

  // WebSocket连接
  const { 
    isConnected, 
    subscribeToTask, 
    unsubscribeFromTask,
    connect,
    disconnect 
  } = useWebSocket({
    userId,
    onMessage: handleWebSocketMessage
  });

  // 终态校准：从HTTP API获取最新状态
  const performFinalStateCheck = useCallback(async () => {
    if (finalStateChecked.current) return;
    finalStateChecked.current = true;
    
    try {
      console.log(`执行终态校准: ${taskId}`);
      const response = await projectApi.getTaskProgress(taskId);
      
      if (response.data) {
        const apiState: TaskProgressState = {
          task_id: taskId,
          progress: response.data.progress || 0,
          step: response.data.current_step || 0,
          total: 6,
          phase: 'unknown',
          message: response.data.current_step || '未知状态',
          status: response.data.status || 'unknown',
          seq: lastSeq + 1,
          ts: Date.now() / 1000,
          last_updated: Date.now()
        };
        
        setTaskState(apiState);
        console.log('终态校准完成:', apiState);
      }
    } catch (error) {
      console.error('终态校准失败:', error);
    }
  }, [taskId, lastSeq]);

  // 订阅任务进度
  const subscribe = useCallback(() => {
    if (isConnected && !isSubscribed) {
      const success = subscribeToTask(taskId);
      if (success) {
        setIsSubscribed(true);
        console.log(`已订阅任务进度: ${taskId}`);
      }
    }
  }, [isConnected, isSubscribed, subscribeToTask, taskId]);

  // 取消订阅任务进度
  const unsubscribe = useCallback(() => {
    if (isConnected && isSubscribed) {
      const success = unsubscribeFromTask(taskId);
      if (success) {
        setIsSubscribed(false);
        console.log(`已取消订阅任务进度: ${taskId}`);
      }
    }
  }, [isConnected, isSubscribed, unsubscribeFromTask, taskId]);

  // 自动订阅/取消订阅
  useEffect(() => {
    if (isConnected) {
      subscribe();
    } else {
      setIsSubscribed(false);
    }
    
    return () => {
      if (isSubscribed) {
        unsubscribe();
      }
    };
  }, [isConnected, subscribe, unsubscribe, isSubscribed]);

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      if (isSubscribed) {
        unsubscribe();
      }
    };
  }, [isSubscribed, unsubscribe]);

  return {
    taskState,
    isConnected,
    isSubscribed,
    subscribe,
    unsubscribe,
    performFinalStateCheck
  };
};

