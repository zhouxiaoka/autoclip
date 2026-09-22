import i18n, { t } from '../i18n'
import { useTranslation } from 'react-i18next'
import React, { useCallback, useEffect, useState } from 'react'
import { message } from 'antd'
import { Btn, Icon, Row, Section, Segmented, StatusDot } from '../ui'
import { openExternalLink } from '../utils/externalLinks'
import { publishGuideHref } from '../publish/guide'
import { platformLabel, readApiDetail } from '../publish/uploadPost'
import { bilibiliApi } from '../publish/bilibiliApi'
import { uploadPostApi, type UploadPostConfigView, type UploadPostProfile } from '../publish/uploadPostApi'

const openPublishGuide = () => openExternalLink(publishGuideHref(i18n.language))

const KEY_URL = 'https://app.upload-post.com/api-keys'
const USERS_URL = 'https://app.upload-post.com/manage-users'

const emptyConfig = (): UploadPostConfigView => ({
  configured: false, source: 'none', api_key_masked: '', user: '',
})

const PublishSettings: React.FC = () => {
  useTranslation()
  const [config, setConfig] = useState<UploadPostConfigView>(emptyConfig)
  const [profiles, setProfiles] = useState<UploadPostProfile[]>([])
  const [apiKey, setApiKey] = useState('')
  const [user, setUser] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [biliConfigured, setBiliConfigured] = useState(false)
  const [biliName, setBiliName] = useState('')
  const [biliSource, setBiliSource] = useState('none')
  const [cookie, setCookie] = useState('')
  const [savingBili, setSavingBili] = useState(false)
  const [clearingBili, setClearingBili] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadProfiles = useCallback(async (preferred: string) => {
    const res = await uploadPostApi.profiles()
    const list = res.profiles || []
    setProfiles(list)
    const next = list.some((p) => p.username === preferred) ? preferred : (list[0]?.username || preferred || '')
    setUser(next)
    return list
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [cfg, bili] = await Promise.all([uploadPostApi.getConfig(), bilibiliApi.getConfig()])
      setConfig(cfg)
      setUser(cfg.user || '')
      setBiliConfigured(bili.configured)
      setBiliName(bili.nickname || '')
      setBiliSource(bili.source || 'none')
      if (cfg.configured) await loadProfiles(cfg.user || '')
      else setProfiles([])
    } catch (err) {
      setError(readApiDetail(err, t("发布失败")))
    } finally {
      setLoading(false)
    }
  }, [loadProfiles])

  useEffect(() => { void load() }, [load])

  const selected = profiles.find((p) => p.username === user)
  const connected = (selected?.connected_platforms || []).map(platformLabel).join(' · ')
  const reconnect = (selected?.reconnect_platforms || []).map(platformLabel).join(' · ')

  const save = async () => {
    const key = apiKey.trim()
    const profile = user.trim()
    if (!key && !profile) {
      setError(t("填写密钥，或选择一个默认账号"))
      return
    }
    if (!config.configured && !key) {
      setError(t("填写密钥，或选择一个默认账号"))
      return
    }
    setSaving(true)
    setError(null)
    try {
      const saved = await uploadPostApi.saveConfig({
        ...(key ? { api_key: key } : {}),
        ...(profile ? { user: profile } : {}),
      })
      setApiKey('')
      setConfig(saved)
      if (saved.configured) await loadProfiles(saved.user || profile)
      const who = key ? saved.account?.email : ''
      message.success(key ? (who ? `${t("密钥已校验并保存")} · ${who}` : t("密钥已校验并保存")) : t("已保存"))
    } catch (err) {
      setError(readApiDetail(err, t("发布失败")))
    } finally {
      setSaving(false)
    }
  }

  const clear = async () => {
    setClearing(true)
    setError(null)
    try {
      await uploadPostApi.clearConfig()
      setApiKey('')
      message.success(t("已清除本机保存的密钥"))
      await load()
    } catch (err) {
      setError(readApiDetail(err, t("发布失败")))
    } finally {
      setClearing(false)
    }
  }

  const saveBili = async () => {
    const value = cookie.trim()
    if (!value) {
      setError(t("登录 B 站后，打开开发者工具 Application → Cookies，复制 SESSDATA、bili_jct、DedeUserID。只保存在这台机器上。"))
      return
    }
    setSavingBili(true)
    setError(null)
    try {
      const saved = await bilibiliApi.saveConfig({ cookie: value })
      setCookie('')
      setBiliConfigured(saved.configured)
      setBiliName(saved.nickname || '')
      setBiliSource(saved.source || 'file')
      message.success(saved.nickname ? `${t("Cookie 已校验并保存")} · ${saved.nickname}` : t("Cookie 已校验并保存"))
    } catch (err) {
      setError(readApiDetail(err, t("发布失败")))
    } finally {
      setSavingBili(false)
    }
  }

  const clearBili = async () => {
    setClearingBili(true)
    setError(null)
    try {
      const cleared = await bilibiliApi.clearConfig()
      setCookie('')
      setBiliConfigured(cleared.configured)
      setBiliName(cleared.nickname || '')
      setBiliSource(cleared.source || 'none')
      message.success(t("已清除本机保存的 B 站账号"))
    } catch (err) {
      setError(readApiDetail(err, t("发布失败")))
    } finally {
      setClearingBili(false)
    }
  }

  return (
    <>
      <Section
        title={t("B 站")}
        description={t("贴三个 Cookie 后保存。配好后，发布页会出现 B 站。")}
        right={<Btn size="sm" onClick={() => void openPublishGuide()}>{t("操作教程")}<Icon.External size={12} /></Btn>}
      >
        <div className="ac-rows">
          <Row
            wide
            stack
            label={t("B 站 Cookie")}
            hint={<>
              {t("登录 B 站后，打开开发者工具 Application → Cookies，复制 SESSDATA、bili_jct、DedeUserID。只保存在这台机器上。")}
              {biliConfigured ? ` ${t("再贴一次会换成这个账号。")}` : ''}
            </>}
          >
            <textarea
              className="ac-input ac-textarea"
              style={{ minHeight: 72 }}
              name="bilibili-cookie"
              autoComplete="off"
              spellCheck={false}
              aria-label={t("B 站 Cookie")}
              value={cookie}
              onChange={(e) => setCookie(e.target.value)}
            />
          </Row>
          <Row label={t("状态")} hint={biliSource === 'env' ? t("Cookie 来自环境变量，这里的修改不会覆盖它。") : undefined}>
            {loading ? (
              <StatusDot tone="muted" label={t("还在处理中")} />
            ) : biliConfigured ? (
              <StatusDot tone="ok" label={t("已连接 {{name}}", { name: biliName || t("B站") })} />
            ) : (
              <StatusDot tone="muted" label={t("未配置")} />
            )}
          </Row>
          <Row label={t("保存")}>
            <Btn size="sm" variant="cta" loading={savingBili} onClick={() => void saveBili()}>{t("保存并校验")}</Btn>
            {biliSource === 'file' && (
              <Btn size="sm" variant="danger" loading={clearingBili} onClick={() => void clearBili()}>{t("清除本机保存的账号")}</Btn>
            )}
          </Row>
        </div>
      </Section>
      <Section
        title={t("海外")}
        description={t("在 Upload-Post 填密钥。配好后，在切片的发布页直接选。")}
      >
        <div className="ac-rows">
          <Row
            wide
            label={t("发布密钥")}
            hint={<>
              {t("在 Upload-Post 生成，只保存在这台机器上。")}{' '}
              <a href={KEY_URL} onClick={(e) => { e.preventDefault(); void openExternalLink(KEY_URL) }} style={{ color: 'var(--ac-accent)' }}>{t("获取密钥")}</a>
            </>}
          >
            <input
              className="ac-input ac-input--mono"
              type="password"
              name="upload-post-api-key"
              autoComplete="new-password"
              spellCheck={false}
              aria-label={t("发布密钥")}
              placeholder={config.api_key_masked || ''}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
            />
          </Row>
          <Row label={t("状态")} hint={config.source === 'env' ? t("密钥来自环境变量，这里的修改不会覆盖它。") : undefined}>
            {loading ? (
              <StatusDot tone="muted" label={t("还在处理中")} />
            ) : config.configured ? (
              <StatusDot tone="ok" label={config.api_key_masked ? t("当前密钥 {{key}}", { key: config.api_key_masked }) : t("已配置")} />
            ) : (
              <StatusDot tone="muted" label={t("未配置")} />
            )}
          </Row>
          <Row
            stack
            label={t("默认账号")}
            hint={<>
              {t("Upload-Post 里已连接社交账号的 profile。")}{' '}
              <a href={USERS_URL} onClick={(e) => { e.preventDefault(); void openExternalLink(USERS_URL) }} style={{ color: 'var(--ac-accent)' }}>{t("管理账号")}</a>
            </>}
          >
            {profiles.length > 0 ? (
              <Segmented
                className="ac-segmented"
                size="sm"
                ariaLabel={t("默认账号")}
                value={user}
                onChange={setUser}
                options={profiles.map((p) => ({ value: p.username, label: p.username }))}
              />
            ) : (
              <span style={{ color: 'var(--ac-sub)', fontSize: 13 }}>{config.configured && !error ? t("还没有 profile。到 Upload-Post 创建一个，并连接要发布的账号。") : '—'}</span>
            )}
          </Row>
          {selected && (
            <Row label={t("已连接的平台")} hint={<>
              {connected || t("这个账号还没有连接平台。")}
              {reconnect ? ` ${t("需要重新连接：{{platforms}}", { platforms: reconnect })}` : null}
            </>}>
              <Btn size="sm" onClick={() => void loadProfiles(user).catch((err) => setError(readApiDetail(err, t("发布失败"))))}>{t("刷新账号")}</Btn>
            </Row>
          )}
          <Row label={t("保存")}>
            <Btn size="sm" variant="cta" loading={saving} onClick={() => void save()}>{t("保存并校验")}</Btn>
            {config.source === 'file' && (
              <Btn size="sm" variant="danger" loading={clearing} onClick={() => void clear()}>{t("清除本机保存的密钥")}</Btn>
            )}
          </Row>
        </div>
      </Section>
      {error && <p style={{ marginTop: 12, color: 'var(--ac-error)', fontSize: 13 }}>{error}</p>}
    </>
  )
}

export default PublishSettings
