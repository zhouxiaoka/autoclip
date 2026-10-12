type Translate = (key: string, values?: Record<string, unknown>) => string

/** 组件安装（Whisper / 人物识别）失败原因：后端给稳定的 error_code，界面按语言显示。没有 code 时用后端原文。 */
export function pipInstallErrorText(t: Translate, status?: { error_code?: string; message?: string } | null): string {
  switch (status?.error_code) {
    case 'pip_network':
      return t('安装失败：网络连不上 pip 源。请检查网络或代理后重试；也可以设置环境变量 PIP_INDEX_URL 指定可用的源。')
    case 'pip_timeout':
      return t('安装失败：下载超时。请检查网络后重试。')
    case 'pip_source_build':
      return t('安装失败：没有拿到预编译包，已停止从源码编译。请检查网络后重试。')
    case 'pip_cancelled':
      return t('安装已取消')
    default:
      return status?.message || ''
  }
}
