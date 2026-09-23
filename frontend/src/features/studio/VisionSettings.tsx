import { useTranslation } from 'react-i18next'
import { t } from '../../i18n'
import { useEffect, useState } from 'react'
import api from '../../services/api'
import axios from 'axios'
import { Btn, Row, Section } from '../../ui'
import { errorText } from './api'
import './studio.css'
interface Config { base_url: string; model: string; timeout: number; has_key: boolean; source: string }
export default function VisionSettings() {
  useTranslation()
  const [config, setConfig] = useState<Config>({ base_url: '', model: '', timeout: 180, has_key: false, source: '' })
  const [key, setKey] = useState('')
  const [clearKey, setClearKey] = useState(false)
  const [busy, setBusy] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  useEffect(() => { let live = true; api.get<unknown, Config>('/studio/vision-settings').then(c => { if(live) setConfig(c) }).catch(e => live && setError(t(errorText(e)))).finally(() => live && setLoading(false)); return () => {live = false} }, [])
  const run = async (action: 'save' | 'test') => {
    setBusy(action); setError(''); setNotice('')
    const body = { base_url: config.base_url.trim(), model: config.model.trim(), timeout: config.timeout, api_key: key.trim() || null, clear_key: clearKey }
    try {
      if (action === 'save') {
        const { data: result } = await axios.put<Config>(`${api.defaults.baseURL}/studio/vision-settings`, body)
        setConfig(result); setKey(''); setClearKey(false); setNotice("视觉模型配置已保存")
      } else {
        await axios.post(`${api.defaults.baseURL}/studio/vision-settings/test`, body, { timeout: (config.timeout + 10) * 1000 })
        setNotice("连接与图片理解测试通过。若修改了配置，请保存后生效")
      }
    } catch(e) { setError(t(errorText(e))) } finally { setBusy('') }
  }
  return <Section title={t("视觉理解模型")} description={t("用于识别游戏画面、寻找高光和规划成片。与文本模型独立配置。")}>
    <fieldset disabled={loading || !!busy} className="studio-fieldset">
      <Row label={t("接口地址")} hint={t("支持 OpenAI 兼容的 Chat Completions 图片接口")}><input className="studio-input" aria-label={t("视觉接口地址")} placeholder="https://…/api/v3" value={config.base_url} onChange={e => { setConfig({...config, base_url:e.target.value});setNotice('') }} /></Row>
      <Row label="API Key" hint={config.has_key ? t("已配置；留空保留已有密钥") : t("自建服务无需鉴权时可留空")}><input className="studio-input" aria-label={t("视觉 API Key")} type="password" autoComplete="new-password" placeholder={config.has_key ? t("已配置 · 输入可替换") : t("输入 API Key")} value={key} onChange={e => {setKey(e.target.value);setClearKey(false);setNotice('')}} /></Row>
      <Row label={t("模型名称")} hint={t("填写模型 ID 或服务商的推理接入点 ID")}><input className="studio-input" aria-label={t("视觉模型名称")} value={config.model} placeholder={t("例如 doubao-seed-2-1-pro-260915")} onChange={e => {setConfig({...config,model:e.target.value});setNotice('')}} /></Row>
      <details className="studio-details"><summary>{t("高级设置")}</summary><Row label={t("请求超时")}><input type="number" aria-label={t("视觉请求超时")} min={10} max={300} value={config.timeout} onChange={e => setConfig({...config,timeout:Number(e.target.value)})} />{t("秒")}</Row>{config.has_key && <label><input type="checkbox" checked={clearKey} onChange={e => setClearKey(e.target.checked)} />{t("清除已保存的密钥（无需鉴权的服务）")}</label>}</details>
      <div className="studio-row" style={{marginTop:24}}><span className="studio-muted">{config.source === 'environment' && config.base_url ? t("当前使用环境默认配置，保存后使用此处的设置。") : t("测试会发送一张内置测试图片，不发送项目素材。")}</span><div className="studio-actions"><Btn loading={busy==='test'} disabled={!config.base_url.trim() || !config.model.trim()} onClick={() => run('test')}>{t("测试连接")}</Btn><Btn variant="cta" loading={busy==='save'} disabled={!config.base_url.trim() || !config.model.trim()} onClick={() => run('save')}>{t("保存视觉配置")}</Btn></div></div>
    </fieldset>
    {error && <p className="studio-error" role="alert">{error}</p>}{notice && <p role="status">{t(notice)}</p>}
  </Section>
}
