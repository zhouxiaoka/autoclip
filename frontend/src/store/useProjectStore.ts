import { create } from 'zustand'
import { projectApi } from '../services/api'

export interface Clip {
  id: string
  title?: string  // 可能没有原始title
  start_time: string
  end_time: string
  final_score: number  // 匹配后端字段名
  recommend_reason: string  // 匹配后端字段名
  generated_title?: string
  outline: string
  content: string[]
  chunk_index?: number  // 添加缺失字段
}

export interface Collection {
  id: string
  collection_title: string
  collection_summary: string
  clip_ids: string[]
  collection_type?: string // "ai_recommended" or "manual"
  created_at?: string
  project_id?: string
  thumbnail_path?: string
}

// 项目状态类型定义，与后端保持一致
type ProjectStatus = 'pending' | 'processing' | 'completed' | 'failed' | 'error'

export interface Project {
  id: string
  name: string
  description?: string
  project_type?: string
  status: ProjectStatus
  source_url?: string
  source_file?: string
  settings?: any
  processing_config?: {
    download_status?: string
    download_progress?: number
    download_message?: string
    [key: string]: any
  }
  created_at: string
  updated_at: string
  completed_at?: string
  total_clips?: number
  total_collections?: number
  total_tasks?: number
  // 前端特有字段
  video_path?: string
  video_category?: string
  thumbnail?: string
  clips?: Clip[]
  collections?: Collection[]
  current_step?: number
  total_steps?: number
  error_message?: string
}

interface ProjectStore {
  projects: Project[]
  currentProject: Project | null
  loading: boolean
  error: string | null
  lastEditTimestamp: number
  isDragging: boolean
  
  // Actions
  setProjects: (projects: Project[]) => void
  setCurrentProject: (project: Project | null) => void
  addProject: (project: Project) => void
  updateProject: (id: string, updates: Partial<Project>) => void
  deleteProject: (id: string) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  updateClip: (projectId: string, clipId: string, updates: Partial<Clip>) => void
  updateCollection: (projectId: string, collectionId: string, updates: Partial<Collection>) => void
  addCollection: (projectId: string, collection: Collection) => void
  deleteCollection: (projectId: string, collectionId: string) => void
  removeClipFromCollection: (projectId: string, collectionId: string, clipId: string) => void
  reorderCollectionClips: (projectId: string, collectionId: string, newClipIds: string[]) => Promise<void>
  addClipToCollection: (projectId: string, collectionId: string, clipIds: string[]) => Promise<void>
  setDragging: (isDragging: boolean) => void
}

export const useProjectStore = create<ProjectStore>((set, get) => ({
  projects: [],
  currentProject: null,
  loading: false,
  error: null,
  lastEditTimestamp: 0,
  isDragging: false,

  setProjects: (projects) => {
    const state = get()
    
    console.log('setProjects called:', {
      isDragging: state.isDragging,
      projectsCount: projects.length,
      projects: projects
    })
    
    // 如果正在拖拽，则跳过更新以避免冲突
    if (state.isDragging) {
      console.log('Skipping update: dragging in progress')
      return
    }
    
    console.log('Applying update with new data')
    set({ projects })
  },
  
  setCurrentProject: (project) => set({ currentProject: project }),
  
  addProject: (project) => set((state) => ({ 
    projects: [project, ...state.projects] 
  })),
  
  updateProject: (id, updates) => set((state) => ({
    projects: state.projects.map(p => p.id === id ? { ...p, ...updates } : p),
    currentProject: state.currentProject?.id === id 
      ? { ...state.currentProject, ...updates } 
      : state.currentProject
  })),
  
  deleteProject: (id) => {
    // 清理缩略图缓存
    const thumbnailCacheKey = `thumbnail_${id}`
    localStorage.removeItem(thumbnailCacheKey)
    
    set((state) => ({
      projects: state.projects.filter(p => p.id !== id),
      currentProject: state.currentProject?.id === id ? null : state.currentProject
    }))
  },
  
  setLoading: (loading) => set({ loading }),
  
  setError: (error) => set({ error }),
  
  updateClip: (projectId, clipId, updates) => set((state) => ({
    projects: state.projects.map(p => 
      p.id === projectId 
        ? { ...p, clips: (p.clips || []).map(c => c.id === clipId ? { ...c, ...updates } : c) }
        : p
    ),
    currentProject: state.currentProject?.id === projectId
      ? { 
          ...state.currentProject, 
          clips: (state.currentProject.clips || []).map(c => c.id === clipId ? { ...c, ...updates } : c)
        }
      : state.currentProject
  })),
  
  updateCollection: (projectId, collectionId, updates) => set((state) => ({
    projects: state.projects.map(p => 
      p.id === projectId 
        ? { ...p, collections: (p.collections || []).map(c => c.id === collectionId ? { ...c, ...updates } : c) }
        : p
    ),
    currentProject: state.currentProject?.id === projectId
      ? { 
          ...state.currentProject, 
          collections: (state.currentProject.collections || []).map(c => c.id === collectionId ? { ...c, ...updates } : c)
        }
      : state.currentProject
  })),

  addCollection: (projectId: string, collection: Collection) => {
    set((state) => ({
      projects: state.projects.map(project => 
        project.id === projectId 
          ? {
              ...project,
              collections: [...(project.collections || []), collection]
            }
          : project
      ),
      currentProject: state.currentProject?.id === projectId
        ? {
            ...state.currentProject,
            collections: [...(state.currentProject.collections || []), collection]
          }
        : state.currentProject
    }))
  },

  deleteCollection: (projectId: string, collectionId: string) => {
    set((state) => ({
      projects: state.projects.map(project => 
        project.id === projectId 
          ? {
              ...project,
              collections: project.collections?.filter(c => c.id !== collectionId) || []
            }
          : project
      ),
      currentProject: state.currentProject?.id === projectId
        ? {
            ...state.currentProject,
            collections: state.currentProject.collections?.filter(c => c.id !== collectionId) || []
          }
        : state.currentProject
    }))
  },

  removeClipFromCollection: async (projectId: string, collectionId: string, clipId: string) => {
    const state = get()
    const project = state.projects.find(p => p.id === projectId)
    const collection = project?.collections?.find(c => c.id === collectionId)
    
    if (!collection) {
      throw new Error('Collection not found')
    }
    
    const originalClipIds = [...collection.clip_ids]
    const updatedClipIds = collection.clip_ids.filter(id => id !== clipId)
    
    // 检查是否真的有变化
    if (originalClipIds.length === updatedClipIds.length) {
      console.log('Clip not found in collection, skipping update')
      return
    }
    
    // 乐观更新：立即更新前端状态
    const updateState = (clipIds: string[]) => {
      set((state) => ({
        projects: state.projects.map(project => 
          project.id === projectId 
            ? {
                ...project,
                collections: project.collections?.map(collection =>
                  collection.id === collectionId
                    ? {
                        ...collection,
                        clip_ids: clipIds
                      }
                    : collection
                ) || []
              }
            : project
        ),
        currentProject: state.currentProject?.id === projectId
          ? {
              ...state.currentProject,
              collections: state.currentProject.collections?.map(collection =>
                collection.id === collectionId
                  ? {
                      ...collection,
                      clip_ids: clipIds
                    }
                  : collection
              ) || []
            }
          : state.currentProject,
        lastEditTimestamp: Date.now()
      }))
    }
    
    // 立即应用更新
    updateState(updatedClipIds)
    
    // 调用后端API
    try {
      console.log('Removing clip from collection:', { projectId, collectionId, clipId })
      await projectApi.updateCollection(projectId, collectionId, { clip_ids: updatedClipIds })
      console.log('Clip removed successfully')
    } catch (error) {
      console.error('Failed to remove clip from collection, rolling back:', error)
      console.error('Error details:', {
        message: error instanceof Error ? error.message : 'Unknown error',
        status: (error as any)?.response?.status,
        statusText: (error as any)?.response?.statusText,
        data: (error as any)?.response?.data
      })
      // 回滚到原始状态
      updateState(originalClipIds)
      throw error
    }
  },

  setDragging: (isDragging) => set({ isDragging }),

  reorderCollectionClips: async (projectId: string, collectionId: string, newClipIds: string[]) => {
    console.log('Starting reorderCollectionClips:', { projectId, collectionId, newClipIds })
    
    // 获取原始状态
    const state = get()
    console.log('Current state projects:', state.projects.map(p => ({ id: p.id, collectionsCount: p.collections?.length || 0 })))
    console.log('Current state currentProject:', state.currentProject ? { id: state.currentProject.id, collectionsCount: state.currentProject.collections?.length || 0 } : null)
    
    // 优先从currentProject中查找，如果找不到再从projects数组中查找
    let originalProject = state.currentProject?.id === projectId ? state.currentProject : null
    let originalCollection = originalProject?.collections?.find(c => c.id === collectionId)
    
    // 如果currentProject中没有找到，尝试从projects数组中查找
    if (!originalCollection) {
      const projectFromArray = state.projects.find(p => p.id === projectId)
      if (projectFromArray) {
        originalProject = projectFromArray
        originalCollection = originalProject.collections?.find(c => c.id === collectionId)
      }
    }
    
    console.log('Found project:', originalProject ? { id: originalProject.id, collectionsCount: originalProject.collections?.length || 0 } : null)
    
    if (originalProject?.collections) {
      console.log('Project collections:', originalProject.collections.map(c => ({ id: c.id, title: c.collection_title })))
    }
    
    console.log('Found collection:', originalCollection ? { id: originalCollection.id, title: originalCollection.collection_title } : null)
    
    if (!originalCollection) {
      console.error('Collection not found in store. Available collections:', 
        originalProject?.collections?.map(c => c.id) || [])
      throw new Error('Collection not found')
    }
    
    const originalClipIds = [...originalCollection.clip_ids]
    
    // 检查是否真的有变化
    if (JSON.stringify(originalClipIds) === JSON.stringify(newClipIds)) {
      console.log('No changes detected, skipping update')
      return
    }
    
    // 记录编辑时间戳
    const now = Date.now()
    
    // 乐观更新：立即更新前端状态
    const updateState = (clipIds: string[]) => {
      set((state) => ({
        projects: state.projects.map(project => 
          project.id === projectId 
            ? {
                ...project,
                collections: project.collections?.map(collection =>
                  collection.id === collectionId
                    ? { ...collection, clip_ids: clipIds }
                    : collection
                ) || []
              }
            : project
        ),
        currentProject: state.currentProject?.id === projectId
          ? {
              ...state.currentProject,
              collections: state.currentProject.collections?.map(collection =>
                collection.id === collectionId
                  ? { ...collection, clip_ids: clipIds }
                  : collection
              ) || []
            }
          : state.currentProject,
        lastEditTimestamp: now
      }))
    }
    
    // 立即应用新顺序
    updateState(newClipIds)
    
    // 调用后端API
    try {
      console.log('Calling backend API for reorder...')
      await projectApi.reorderCollectionClips(projectId, collectionId, newClipIds)
      console.log('Backend API call successful')
    } catch (error) {
      console.error('Backend API call failed:', error)
      // 回滚到原始状态
      updateState(originalClipIds)
      throw error
    }
  },

  addClipToCollection: async (projectId: string, collectionId: string, clipIds: string[]) => {
    console.log('Starting addClipToCollection:', { projectId, collectionId, clipIds })
    
    // 获取原始状态
    const state = get()
    
    // 优先从currentProject中查找，如果找不到再从projects数组中查找
    let originalProject = state.currentProject?.id === projectId ? state.currentProject : null
    let originalCollection = originalProject?.collections?.find(c => c.id === collectionId)
    
    // 如果currentProject中没有找到，尝试从projects数组中查找
    if (!originalCollection) {
      const projectFromArray = state.projects.find(p => p.id === projectId)
      if (projectFromArray) {
        originalProject = projectFromArray
        originalCollection = originalProject.collections?.find(c => c.id === collectionId)
      }
    }
    
    if (!originalCollection) {
      throw new Error('Collection not found')
    }
    
    const originalClipIds = [...originalCollection.clip_ids]
    const updatedClipIds = [...originalClipIds, ...clipIds.filter(id => !originalClipIds.includes(id))]
    
    // 检查是否真的有变化
    if (originalClipIds.length === updatedClipIds.length) {
      console.log('No new clips to add, skipping update')
      return
    }
    
    // 乐观更新：立即更新前端状态
    const updateState = (clipIds: string[]) => {
      set((state) => ({
        projects: state.projects.map(project => 
          project.id === projectId 
            ? {
                ...project,
                collections: project.collections?.map(collection =>
                  collection.id === collectionId
                    ? { ...collection, clip_ids: clipIds }
                    : collection
                ) || []
              }
            : project
        ),
        currentProject: state.currentProject?.id === projectId
          ? {
              ...state.currentProject,
              collections: state.currentProject.collections?.map(collection =>
                collection.id === collectionId
                  ? { ...collection, clip_ids: clipIds }
                  : collection
              ) || []
            }
          : state.currentProject,
        lastEditTimestamp: Date.now()
      }))
    }
    
    // 立即应用更新
    updateState(updatedClipIds)
    
    // 调用后端API
    try {
      console.log('Adding clips to collection:', { projectId, collectionId, clipIds })
      await projectApi.updateCollection(projectId, collectionId, { clip_ids: updatedClipIds })
      console.log('Clips added to collection successfully')
    } catch (error) {
      console.error('Failed to add clips to collection, rolling back:', error)
      // 回滚到原始状态
      updateState(originalClipIds)
      throw error
    }
  }
}))