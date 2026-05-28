/**
 * API工具函数
 * 统一处理API URL和请求
 */

import { apiConfigManager, getApiBaseUrl, buildApiUrl } from './apiConfig'

// 动态获取API基础URL
export const getApiBaseUrlAsync = async () => {
  // 等待 API 配置就绪
  await apiConfigManager.waitForReady(5000);
  return getApiBaseUrl();
}

// 构建完整的API URL
export const buildApiUrlAsync = async (path: string) => {
  // 等待 API 配置就绪
  await apiConfigManager.waitForReady(5000);
  return buildApiUrl(path);
}

// 统一的fetch函数
export const apiFetch = async (path: string, options?: RequestInit) => {
  const url = await buildApiUrlAsync(path);
  return fetch(url, options);
}

// 统一的GET请求
export const apiGet = async (path: string) => {
  return apiFetch(path, {
    method: 'GET',
    headers: {
      'Content-Type': 'application/json',
    },
  })
}

// 统一的POST请求
export const apiPost = async (path: string, data?: any) => {
  return apiFetch(path, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: data ? JSON.stringify(data) : undefined,
  })
}

// 统一的PUT请求
export const apiPut = async (path: string, data?: any) => {
  return apiFetch(path, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: data ? JSON.stringify(data) : undefined,
  })
}

// 统一的DELETE请求
export const apiDelete = async (path: string) => {
  return apiFetch(path, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
    },
  })
}
