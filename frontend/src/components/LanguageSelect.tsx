import { Select } from 'antd'
import { GlobalOutlined } from '@ant-design/icons'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { languages, readPreference, setLanguage, t } from '../i18n'
import type { LanguagePreference } from '../i18n/language'

export default function LanguageSelect() {
  useTranslation()
  const [preference, setPreference] = useState(readPreference)
  return (
    <Select
      aria-label={t('界面语言')}
      title={t('界面语言')}
      value={preference}
      onChange={(value: LanguagePreference) => {
        setPreference(value)
        void setLanguage(value)
      }}
      suffixIcon={<GlobalOutlined />}
      style={{ width: 150, maxWidth: '38vw' }}
      options={[{ value: 'system', label: t('跟随系统') }, ...languages]}
      popupMatchSelectWidth={200}
    />
  )
}
