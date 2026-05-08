/**
 * API 配置管理器
 * 处理动态后端地址和端口配置
 */

interface ApiConfig {
  baseUrl: string;
  port: number;
  isReady: boolean;
}

class ApiConfigManager {
  private static instance: ApiConfigManager;
  private config: ApiConfig = {
    baseUrl: '/api/v1',
    port: 0,
    isReady: false
  };
  private listeners: Array<(config: ApiConfig) => void> = [];

  private constructor() {
    this.initializeConfig();
  }

  static getInstance(): ApiConfigManager {
    if (!ApiConfigManager.instance) {
      ApiConfigManager.instance = new ApiConfigManager();
    }
    return ApiConfigManager.instance;
  }

  private async initializeConfig() {
    // 检查是否在 Tauri 环境中
    if (typeof window !== 'undefined' && ((window as any).__TAURI__ || (window as any).__TAURI_INTERNALS__)) {
      try {
        // 监听后端启动事件
        const { listen } = await import('@tauri-apps/api/event');
        const { invoke } = await import('@tauri-apps/api/core');
        
        await listen('backend-started', (event: any) => {
          const backendStatus = event.payload;
          if (backendStatus && backendStatus.port) {
            this.updateFromPort(backendStatus.port);
          }
        });

        const backendStatus = await invoke('get_service_status') as any;
        if (backendStatus?.is_running && backendStatus?.port) {
          this.updateFromPort(backendStatus.port);
        }

        // 尝试从全局变量获取配置
        if ((window as any).__BACKEND_BASE__) {
          this.updateConfig({
            baseUrl: (window as any).__BACKEND_BASE__,
            port: this.extractPortFromUrl((window as any).__BACKEND_BASE__),
            isReady: true
          });
        }
      } catch (error) {
        console.warn('无法初始化 Tauri 事件监听:', error);
      }
    }
  }

  private updateFromPort(port: number) {
    this.updateConfig({
      baseUrl: `http://127.0.0.1:${port}/api/v1`,
      port,
      isReady: true
    });
  }

  private extractPortFromUrl(url: string): number {
    const match = url.match(/:(\d+)/);
    return match ? parseInt(match[1], 10) : 0;
  }

  private updateConfig(newConfig: Partial<ApiConfig>) {
    this.config = { ...this.config, ...newConfig };
    this.notifyListeners();
  }

  private notifyListeners() {
    this.listeners.forEach(listener => listener(this.config));
  }

  /**
   * 获取当前 API 配置
   */
  getConfig(): ApiConfig {
    return { ...this.config };
  }

  /**
   * 获取 API 基础 URL
   */
  getBaseUrl(): string {
    return this.config.baseUrl;
  }

  /**
   * 检查 API 是否就绪
   */
  isReady(): boolean {
    return this.config.isReady;
  }

  /**
   * 添加配置变化监听器
   */
  addListener(listener: (config: ApiConfig) => void): () => void {
    this.listeners.push(listener);
    return () => {
      const index = this.listeners.indexOf(listener);
      if (index > -1) {
        this.listeners.splice(index, 1);
      }
    };
  }

  /**
   * 等待 API 就绪
   */
  async waitForReady(timeout: number = 30000): Promise<boolean> {
    if (this.isReady()) {
      return true;
    }

    return new Promise((resolve) => {
      const timeoutId = setTimeout(() => {
        resolve(false);
      }, timeout);

      const removeListener = this.addListener((config) => {
        if (config.isReady) {
          clearTimeout(timeoutId);
          removeListener();
          resolve(true);
        }
      });
    });
  }

  /**
   * 构建完整的 API URL
   */
  buildUrl(path: string): string {
    const normalizedPath = path.startsWith('/') ? path : `/${path}`;
    return `${this.config.baseUrl}${normalizedPath}`;
  }

  /**
   * 健康检查
   */
  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(this.buildUrl('/health'), {
        method: 'GET',
        timeout: 5000
      } as any);
      return response.ok;
    } catch (error) {
      console.warn('API 健康检查失败:', error);
      return false;
    }
  }
}

// 导出单例实例
export const apiConfigManager = ApiConfigManager.getInstance();

// 导出便捷函数
export const getApiBaseUrl = () => apiConfigManager.getBaseUrl();
export const isApiReady = () => apiConfigManager.isReady();
export const waitForApiReady = (timeout?: number) => apiConfigManager.waitForReady(timeout);
export const buildApiUrl = (path: string) => apiConfigManager.buildUrl(path);
export const checkApiHealth = () => apiConfigManager.healthCheck();
