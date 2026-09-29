import { forwardRef, useEffect, useImperativeHandle, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Input, Select, Switch } from 'antd'
import { t } from '../../i18n'
import { Row, Segmented } from '../../ui'
import { coverApi, type CoverConfigView, type CoverProvider } from '../../publish/coverApi'

export interface CoverModelHandle { save: () => Promise<void> }

const NONE = '__frame__'
const OTHER = '__other__'

// 接口没返回生图名单时的兜底；与 backend/core/model_catalog.py IMAGE_MODELS 对齐
const FALLBACK_IMAGE_MODELS: Record<string, string[]> = {
  dashscope: ['wanx2.1-t2i-turbo', 'wanx2.1-t2i-plus'],
  seed: ['doubao-seedream-5-0-260128'],
  openai: ['gpt-image-1'],
  infistar: ['gpt-image-1', 'dall-e-3', 'doubao-seedream-5-0-260128', 'flux-1.1-pro', 'imagen-4', 'wanx2.1-t2i-turbo'],
}
const OTHER_PRESETS: Record<CoverProvider, { model: string; baseUrl: string }> = {
  openai: { model: 'gpt-image-1', baseUrl: 'https://api.openai.com/v1' },
  seedream: { model: 'doubao-seedream-5-0-260128', baseUrl: 'https://ark.cn-beijing.volces.com/api/v3' },
  dashscope: { model: 'wanx2.1-t2i-turbo', baseUrl: '' },
}

/**
 * 「模型」里的封面生图：默认跟着上面的服务商和 Key 走（通义→通义万相、Seed→Seedream、
 * OpenAI / Infistar→images 接口，Infistar 可选各家主流生图模型）。
 * 上面的服务商没有接入生图时，可以「用其他服务生图」，就地填一组生图配置。
 */
const CoverModelRow = forwardRef<CoverModelHandle, { provider: string; imageModels: string[] }>(({ provider, imageModels }, ref) => {
  useTranslation()
  const [config, setConfig] = useState<CoverConfigView | null>(null)
  const [choice, setChoice] = useState<string>(NONE)
  const [draft, setDraft] = useState('')
  const [allowFrame, setAllowFrame] = useState(false)
  const [other, setOther] = useState({ provider: 'openai' as CoverProvider, model: '', key: '', baseUrl: '' })
  const [touched, setTouched] = useState(false)

  const followModels = imageModels.length ? imageModels : (FALLBACK_IMAGE_MODELS[provider] || [])

  useEffect(() => {
    let live = true
    coverApi.getConfig().then((c) => {
      if (!live) return
      setConfig(c)
      setAllowFrame(!!c.allow_send_frame)
      if (c.mode === 'custom' && (c.configured || c.enabled)) {
        setChoice(c.enabled ? OTHER : NONE)
        setOther({ provider: (c.provider as CoverProvider) || 'openai', model: c.model || '', key: '', baseUrl: c.base_url || '' })
      } else {
        setChoice(c.enabled && c.model ? c.model : NONE)
      }
    }).catch(() => undefined)
    return () => { live = false }
  }, [])

  useImperativeHandle(ref, () => ({
    save: async () => {
      if (!touched) return
      const enabled = choice !== NONE
      const body = choice === OTHER
        ? { mode: 'custom' as const, enabled: true, provider: other.provider, model: other.model.trim(), base_url: other.baseUrl.trim(), api_key: other.key.trim() || undefined, allow_send_frame: allowFrame }
        : { mode: 'text_model' as const, enabled, model: enabled ? choice : '', allow_send_frame: enabled && allowFrame }
      const saved = await coverApi.saveConfig(body)
      setConfig(saved)
      setOther((o) => ({ ...o, key: '' }))
      setTouched(false)
    },
  }), [touched, choice, other, allowFrame])

  const pick = (v: string) => {
    setChoice(v); setDraft(''); setTouched(true)
    if (v === OTHER && !other.model) setOther((o) => ({ ...o, model: OTHER_PRESETS[o.provider].model, baseUrl: o.baseUrl || OTHER_PRESETS[o.provider].baseUrl }))
  }
  const chooseOtherProvider = (next: CoverProvider) => {
    const prev = OTHER_PRESETS[other.provider]
    setOther((o) => ({
      ...o,
      provider: next,
      model: !o.model || o.model === prev.model ? OTHER_PRESETS[next].model : o.model,
      baseUrl: !o.baseUrl || o.baseUrl === prev.baseUrl ? OTHER_PRESETS[next].baseUrl : o.baseUrl,
    }))
    setTouched(true)
  }

  const custom = choice !== NONE && choice !== OTHER && !followModels.includes(choice) ? [choice] : []
  const typed = draft && draft !== choice && !followModels.includes(draft) ? [draft] : []
  const options = [
    ...(followModels.length ? [{ label: t('同一服务商'), options: [...typed, ...custom, ...followModels].map((m) => ({ value: m, label: m })) }] : []),
    { label: t('其他'), options: [{ value: OTHER, label: t('用其他服务生图…') }, { value: NONE, label: t('不生成，用视频截帧') }] },
  ]
  const ownKey = config?.mode === 'custom' && config.key_source === 'own'

  return (
    <>
      <Row
        wide
        label={t('封面生图')}
        hint={followModels.length
          ? t('默认用同一个服务商和 Key。可从列表选，也可以直接输入账号里可用的生图模型 ID；生图失败会自动改用视频截帧。')
          : t('上面的服务商还没接入生图，可以选「用其他服务生图」单独填一个；不选则用视频截帧。')}
      >
        <Select
          value={choice}
          style={{ width: '100%' }}
          className="ac-mono"
          showSearch={followModels.length > 0}
          onSearch={(text) => setDraft(text.trim())}
          onChange={pick}
          options={options}
        />
      </Row>
      {choice === OTHER && (
        <>
          <Row label={t('生图服务')}>
            <Segmented size="sm" ariaLabel={t('生图服务')} value={other.provider} onChange={chooseOtherProvider}
              options={[{ value: 'openai', label: t('OpenAI 兼容') }, { value: 'seedream', label: 'Seedream' }, { value: 'dashscope', label: t('通义万相') }]} />
          </Row>
          <Row wide label="API Key" hint={ownKey ? t('已配置；留空保留已有密钥') : t('和上面是同一家服务时可以留空，自动复用。')}>
            <Input.Password className="ac-mono" autoComplete="new-password" placeholder={ownKey ? (config?.api_key_masked || '') : 'sk-…'} value={other.key} onChange={(e) => { setOther({ ...other, key: e.target.value }); setTouched(true) }} />
          </Row>
          <Row wide label={t('生图模型')}>
            <Input className="ac-mono" placeholder={OTHER_PRESETS[other.provider].model} value={other.model} onChange={(e) => { setOther({ ...other, model: e.target.value }); setTouched(true) }} />
          </Row>
          {other.provider !== 'dashscope' && (
            <Row wide label={t('接口地址')}>
              <Input className="ac-mono" placeholder={OTHER_PRESETS[other.provider].baseUrl} value={other.baseUrl} onChange={(e) => { setOther({ ...other, baseUrl: e.target.value }); setTouched(true) }} />
            </Row>
          )}
        </>
      )}
      {choice !== NONE && (
        <Row label={t('允许上传参考帧')} hint={t('把视频截帧一起发给生图服务做参考，封面更贴近画面。默认关闭。')}>
          <Switch checked={allowFrame} onChange={(on) => { setAllowFrame(on); setTouched(true) }} />
        </Row>
      )}
    </>
  )
})

export default CoverModelRow
