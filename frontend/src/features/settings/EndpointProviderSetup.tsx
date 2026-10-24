import { useState } from 'react'
import { Input } from 'antd'
import { t } from '../../i18n'
import { Btn, Row } from '../../ui'
import ProviderFields from './ProviderFields'
import { validationCopy } from './providerAccess'
import type { Connection } from './modelSettingsApi'
import type { ModelSettingsStore } from './useModelSettings'

/** User-owned compatible gateway; native-only protocols remain documented by the guide. */
export default function EndpointProviderSetup({ connection, onEdit, m }: {
  connection: Connection
  onEdit: (patch: Partial<Connection>) => void
  m: ModelSettingsStore
}) {
  const [model, setModel] = useState('')
  return <div className="ac-rows">
    <p className="ac-note">{t('本版仅支持 OpenAI 兼容接口。')}</p>
    <ProviderFields connection={connection} hideProvider placement="settings_model"
      onChoose={() => undefined} onEdit={onEdit} />
    <Row wide label={t('模型 ID')}>
      <Input aria-label={t('模型 ID')} value={model} onChange={event => setModel(event.target.value)} />
    </Row>
    <Btn size="sm" disabled={!connection.base_url.trim() || !model.trim()} loading={m.testing}
      onClick={() => void m.validateCatalogConnection(connection, model.trim())}>{t('测试连接')}</Btn>
    {connection.validation_status === 'failed' && <p className="ac-note ac-note--error" role="alert">
      {validationCopy(connection.validation_error_type)}
    </p>}
  </div>
}
