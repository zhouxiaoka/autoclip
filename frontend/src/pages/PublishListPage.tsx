import { t } from '../i18n'
import { useTranslation } from 'react-i18next'
import React, { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Btn, Icon, StatusDot } from '../ui'
import { platformLabel, readApiDetail, recordStatusKey, recordTone } from '../publish/uploadPost'
import { uploadPostApi, type PublishRecord } from '../publish/uploadPostApi'

function formatWhen(record: PublishRecord): string {
  const raw = record.scheduled_date || record.submitted_at || ''
  if (!raw) return ''
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw.replace('T', ' ').slice(0, 16)
  return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(date)
}

const PublishListPage: React.FC = () => {
  useTranslation()
  const { id: projectId = '' } = useParams()
  const navigate = useNavigate()
  const [records, setRecords] = useState<PublishRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [cancelling, setCancelling] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await uploadPostApi.records(projectId)
      setRecords(res.records || [])
    } catch (err) {
      setError(readApiDetail(err, t("发布失败")))
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => { void load() }, [load])

  const cancel = async (requestId: string) => {
    setCancelling(requestId)
    setError(null)
    try {
      await uploadPostApi.cancel(projectId, requestId)
      setRecords((cur) => cur.map((record) => record.request_id === requestId ? { ...record, status: 'cancelled' } : record))
    } catch (err) {
      setError(readApiDetail(err, t("发布失败")))
    } finally {
      setCancelling(null)
    }
  }

  return (
    <div className="ac-page ac-page--narrow">
      <header>
        <button className="ac-back" onClick={() => navigate(`/project/${projectId}`)}>
          <Icon.Back />{t("项目")}
        </button>
        <h1 className="ac-title">{t("发布")}</h1>
      </header>

      {loading && <div style={{ marginTop: 28 }}><StatusDot tone="accent" label={t("还在处理中")} /></div>}
      {!loading && !records.length && !error && (
        <div className="ac-empty" style={{ marginTop: 28 }}>
          <b>{t("还没有发布记录。")}</b>
          <span>{t("从切片的导出里选择发到海外平台。")}</span>
        </div>
      )}
      {!loading && records.length > 0 && (
        <div className="ac-rows" style={{ marginTop: 12 }}>
          {records.map((record) => (
            <div className="ac-row" key={record.request_id}>
              <div className="ac-row-label">
                <b>{record.title || t("切片")}</b>
                <small>
                  <StatusDot tone={recordTone(record.status)} label={t(recordStatusKey(record.status))} />
                  {formatWhen(record) ? <span className="ac-mono"> · {formatWhen(record)}</span> : null}
                  {(record.platforms || []).length > 0 && ` · ${(record.platforms || []).map(platformLabel).join(' · ')}`}
                </small>
              </div>
              {record.status === 'scheduled' && (
                <div className="ac-row-control">
                  <Btn size="sm" variant="text" loading={cancelling === record.request_id} onClick={() => void cancel(record.request_id)}>{t("取消排期")}</Btn>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {error && <p style={{ marginTop: 12, color: 'var(--ac-error)', fontSize: 13 }}>{error}</p>}
    </div>
  )
}

export default PublishListPage
