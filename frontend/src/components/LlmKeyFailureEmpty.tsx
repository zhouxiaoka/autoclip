import React from 'react'
import { useTranslation } from 'react-i18next'
import { t } from '../i18n'
import { Btn } from '../ui'

/** 失败空态：一句原因、自备密钥的下一步、打开「设置 → 模型」的主按钮。 */
const LlmKeyFailureEmpty: React.FC<{
  errorMessage?: string
  onOpenSettings: () => void
}> = ({ errorMessage, onOpenSettings }) => {
  useTranslation()
  return (
    <div className="ac-empty" style={{ marginTop: 32 }}>
      <b>{t("还没有可用的模型")}</b>
      <span style={{ display: 'block', maxWidth: 520, margin: '6px auto 0', lineHeight: 1.5 }}>
        {t("切片分析需要你自己的 API Key。打开「设置 → 模型」，填上提供商、密钥和模型名，再点「测试连接」。密钥在该提供商的控制台申请，只保存在这台机器上。")}
      </span>
      {errorMessage && (
        <span className="ac-mono" style={{ display: 'block', marginTop: 10, color: 'var(--ac-muted)', wordBreak: 'break-word' }}>
          {errorMessage}
        </span>
      )}
      <div style={{ marginTop: 16 }}>
        <Btn variant="cta" size="sm" onClick={onOpenSettings}>{t("打开模型设置")}</Btn>
      </div>
    </div>
  )
}

export default LlmKeyFailureEmpty
