import { useState, useCallback } from 'react';
import { TaskUpdateMessage, ProjectUpdateMessage } from './useWebSocket';

export interface TaskStatus {
  id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  message?: string;
  error?: string;
  updatedAt: string;
  project_id?: string; // 添加项目ID字段
}

export interface ProjectStatus {
  id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  message?: string;
  updatedAt: string;
}

export const useTaskStatus = () => {
  console.log('🔧 useTaskStatus Hook已初始化');
  
  const [tasks, setTasks] = useState<Map<string, TaskStatus>>(new Map());
  const [projects, setProjects] = useState<Map<string, ProjectStatus>>(new Map());
  const [loading, setLoading] = useState(false);

  const updateTask = useCallback((taskUpdate: TaskUpdateMessage) => {
    setTasks(prev => {
      const newTasks = new Map(prev);
      const existing = newTasks.get(taskUpdate.task_id);
      
      newTasks.set(taskUpdate.task_id, {
        id: taskUpdate.task_id,
        status: taskUpdate.status as TaskStatus['status'],
        progress: taskUpdate.progress || (existing?.progress || 0),
        message: taskUpdate.message,
        error: taskUpdate.error,
        updatedAt: taskUpdate.timestamp
      });
      
      return newTasks;
    });
  }, []);

  const updateProject = useCallback((projectUpdate: ProjectUpdateMessage) => {
    setProjects(prev => {
      const newProjects = new Map(prev);
      const existing = newProjects.get(projectUpdate.project_id);
      
      newProjects.set(projectUpdate.project_id, {
        id: projectUpdate.project_id,
        status: projectUpdate.status as ProjectStatus['status'],
        progress: projectUpdate.progress || (existing?.progress || 0),
        message: projectUpdate.message,
        updatedAt: projectUpdate.timestamp
      });
      
      return newProjects;
    });
  }, []);

  const getTask = useCallback((taskId: string): TaskStatus | undefined => {
    return tasks.get(taskId);
  }, [tasks]);

  const getProject = useCallback((projectId: string): ProjectStatus | undefined => {
    return projects.get(projectId);
  }, [projects]);

  const getAllTasks = useCallback((): TaskStatus[] => {
    return Array.from(tasks.values());
  }, [tasks]);

  const getAllProjects = useCallback((): ProjectStatus[] => {
    return Array.from(projects.values());
  }, [projects]);

  const getActiveTasks = useCallback((): TaskStatus[] => {
    return Array.from(tasks.values()).filter(
      task => task.status === 'pending' || task.status === 'running'
    );
  }, [tasks]);

  const getActiveProjects = useCallback((): ProjectStatus[] => {
    return Array.from(projects.values()).filter(
      project => project.status === 'pending' || project.status === 'processing'
    );
  }, [projects]);

  const clearTask = useCallback((taskId: string) => {
    setTasks(prev => {
      const newTasks = new Map(prev);
      newTasks.delete(taskId);
      return newTasks;
    });
  }, []);

  const clearProject = useCallback((projectId: string) => {
    setProjects(prev => {
      const newProjects = new Map(prev);
      newProjects.delete(projectId);
      return newProjects;
    });
  }, []);

  const clearAll = useCallback(() => {
    setTasks(new Map());
    setProjects(new Map());
  }, []);

  const loadProjectTasks = useCallback(async (projectId: string) => {
    console.log('📤 开始加载项目任务:', projectId);
    setLoading(true);
    try {
      const response = await fetch(`/api/v1/tasks/project/${projectId}`);
      console.log('📡 API响应状态:', response.status);
      
      if (response.ok) {
        const data = await response.json();
        const projectTasks = data.data.tasks || [];
        console.log('📋 获取到任务数量:', projectTasks.length);
        
        setTasks(prev => {
          const newTasks = new Map(prev);
          projectTasks.forEach((task: any) => {
            console.log('📝 添加任务:', task.task_id, task.status, task.progress);
            newTasks.set(task.task_id, {
              id: task.task_id,
              status: task.status as TaskStatus['status'],
              progress: task.progress || 0,
              message: task.name,
              updatedAt: task.updated_at,
              project_id: task.project_id || projectId
            });
          });
          return newTasks;
        });
      } else {
        console.error('❌ API调用失败:', response.status, response.statusText);
      }
    } catch (error) {
      console.error('❌ 加载项目任务失败:', error);
    } finally {
      setLoading(false);
      console.log('✅ 任务加载完成');
    }
  }, []); // 空依赖数组，避免无限循环

  return {
    tasks: getAllTasks(),
    projects: getAllProjects(),
    activeTasks: getActiveTasks(),
    activeProjects: getActiveProjects(),
    loading,
    getTask,
    getProject,
    updateTask,
    updateProject,
    clearTask,
    clearProject,
    clearAll,
    loadProjectTasks
  };
}; 