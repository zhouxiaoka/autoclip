import { useMemo, useState } from 'react'
import { t } from '../../i18n'
import { Btn, Dialog } from '../../ui'
import ProviderQualityMarks from '../settings/providerQualityMarks'
import { defaultSwitchOption, type SwitchModelOption } from './switchModelOptions'

export default function SwitchModelDialog({
  open,
  options,
  busy,
  onClose,
  onConfirm,
}: {
  open: boolean
  options: SwitchModelOption[]
  busy?: boolean
  onClose: () => void
  onConfirm: (choice: { connectionId: string; model: string }) => void
}) {
  const initial = useMemo(() => defaultSwitchOption(options), [options])
  const [selected, setSelected] = useState<string | null>(null)
  const keyOf = (o: SwitchModelOption) => `${o.connectionId}::${o.model}`
  const currentKey = selected ?? (initial ? keyOf(initial) : null)
  const current = options.find(o => keyOf(o) === currentKey) || initial

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={t('换模型重试')}
      description={t('选择一个已通过测试的连接继续制作。默认选中成功率最高的。')}
      footer={
        <div className="studio-actions">
          <Btn disabled={busy} onClick={onClose}>{t('取消')}</Btn>
          <Btn
            variant="cta"
            disabled={busy || !current}
            loading={busy}
            onClick={() => current && onConfirm({ connectionId: current.connectionId, model: current.model })}
          >
            {t('切换并重试')}
          </Btn>
        </div>
      }
    >
      {!options.length ? (
        <p className="studio-muted">{t('还没有其他可用连接。请先在设置里添加并测试一个服务商。')}</p>
      ) : (
        <ul className="studio-switch-model-list" role="listbox" aria-label={t('可用模型')}>
          {options.map(option => {
            const key = keyOf(option)
            const checked = key === currentKey
            return (
              <li key={key}>
                <button
                  type="button"
                  role="option"
                  aria-selected={checked}
                  className={`studio-switch-model-option${checked ? ' is-selected' : ''}`}
                  onClick={() => setSelected(key)}
                  disabled={busy}
                >
                  <span className="studio-switch-model-name">
                    <strong>{option.displayName}</strong>
                    <span className="studio-muted">{option.model}</span>
                  </span>
                  <ProviderQualityMarks preset={{ success_tier: option.success_tier }} />
                </button>
              </li>
            )
          })}
        </ul>
      )}
    </Dialog>
  )
}
