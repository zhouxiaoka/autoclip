import { getLocale, t } from '../i18n'
import { useTranslation } from 'react-i18next'
import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { Btn, Icon, Segmented, StatusDot } from '../ui'
import { dayKey, focusMonth, platformLabel, readApiDetail, recordInstant, recordStatusKey, recordTone, monthCells } from '../publish/uploadPost'
import { uploadPostApi, type PublishRecord } from '../publish/uploadPostApi'

function formatWhen(record: PublishRecord): string {
  const date = recordInstant(record)
  if (!date) {
    const raw = record.scheduled_date || record.submitted_at || ''
    return raw ? raw.replace('T', ' ').slice(0, 16) : ''
  }
  return new Intl.DateTimeFormat(getLocale(), { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(date)
}

function monthTitle(year: number, month: number): string {
  return new Intl.DateTimeFormat(getLocale(), { year: 'numeric', month: 'long' }).format(new Date(year, month, 1))
}

function weekdayLabels(): string[] {
  const monday = new Date(2026, 0, 5)
  return Array.from({ length: 7 }, (_, index) => {
    const date = new Date(monday)
    date.setDate(monday.getDate() + index)
    return new Intl.DateTimeFormat(getLocale(), { weekday: 'short' }).format(date)
  })
}

function shiftMonth(cursor: { year: number; month: number }, delta: number) {
  const date = new Date(cursor.year, cursor.month + delta, 1)
  return { year: date.getFullYear(), month: date.getMonth() }
}

const PublishListPage: React.FC = () => {
  useTranslation()
  const { id: projectId = '' } = useParams()
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const view = params.get('view') === 'calendar' ? 'calendar' : 'list'
  const [records, setRecords] = useState<PublishRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [cancelling, setCancelling] = useState<string | null>(null)
  const [cursor, setCursor] = useState<{ year: number; month: number } | null>(null)

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

  useEffect(() => {
    if (loading) return
    setCursor((current) => current ?? focusMonth(records, new Date()))
  }, [loading, records])

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

  const setView = (next: 'list' | 'calendar') => {
    const nextParams = new URLSearchParams(params)
    if (next === 'calendar') nextParams.set('view', 'calendar')
    else nextParams.delete('view')
    setParams(nextParams, { replace: true })
  }

  const today = dayKey(new Date())
  const cells = useMemo(() => cursor ? monthCells(cursor.year, cursor.month) : [], [cursor])
  const byDay = useMemo(() => {
    const grouped = new Map<string, PublishRecord[]>()
    records.filter((record) => record.status !== 'cancelled').forEach((record) => {
      const date = recordInstant(record)
      if (!date) return
      const key = dayKey(date)
      const list = grouped.get(key) || []
      list.push(record)
      grouped.set(key, list)
    })
    grouped.forEach((list) => list.sort((a, b) => (recordInstant(a)?.getTime() || 0) - (recordInstant(b)?.getTime() || 0)))
    return grouped
  }, [records])

  return (
    <div className="ac-page ac-page--narrow">
      <header>
        <button className="ac-back" onClick={() => navigate(`/project/${projectId}`)}>
          <Icon.Back />{t("项目")}
        </button>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, marginTop: 10, flexWrap: 'wrap' }}>
          <h1 className="ac-title" style={{ marginTop: 0 }}>{t("发布")}</h1>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <Btn size="sm" onClick={() => navigate(`/project/${projectId}/publish/week`)}>{t("排这一周")}</Btn>
            <Segmented
              size="sm"
              ariaLabel={t("发布")}
              value={view}
              onChange={setView}
              options={[{ value: 'list', label: t("列表") }, { value: 'calendar', label: t("月历") }]}
            />
          </div>
        </div>
      </header>

      {loading && <div style={{ marginTop: 28 }}><StatusDot tone="accent" label={t("还在处理中")} /></div>}
      {!loading && view === 'list' && !records.length && !error && (
        <div className="ac-empty" style={{ marginTop: 28 }}>
          <b>{t("还没有发布记录。")}</b>
          <span>{t("从切片的导出里选择发到海外平台。")}</span>
        </div>
      )}
      {!loading && view === 'list' && records.length > 0 && (
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
      {!loading && view === 'calendar' && cursor && (
        <div className="ac-cal">
          <div className="ac-cal-nav">
            <Btn size="sm" aria-label={t("上个月")} onClick={() => setCursor(shiftMonth(cursor, -1))}>‹</Btn>
            <div className="ac-cal-title">{monthTitle(cursor.year, cursor.month)}</div>
            <Btn size="sm" aria-label={t("下个月")} onClick={() => setCursor(shiftMonth(cursor, 1))}>›</Btn>
          </div>
          <div className="ac-cal-dow">
            {weekdayLabels().map((label, index) => <span key={index}>{label}</span>)}
          </div>
          <div className="ac-cal-grid">
            {cells.map(({ date, inMonth }) => {
              const key = dayKey(date)
              const items = byDay.get(key) || []
              const classes = ['ac-cal-day']
              if (!inMonth) classes.push('ac-cal-day--out')
              if (key === today) classes.push('ac-cal-day--today')
              return (
                <div className={classes.join(' ')} key={key} aria-current={key === today ? 'date' : undefined}>
                  <div className="ac-cal-num">{date.getDate()}</div>
                  {items.map((record) => (
                    <div className="ac-cal-item" key={record.request_id} title={record.title || t("切片")}>
                      <i className={`ac-dot ac-dot--${recordTone(record.status)}`} aria-hidden />
                      <b>{record.title || t("切片")}</b>
                    </div>
                  ))}
                </div>
              )
            })}
          </div>
        </div>
      )}
      {error && <p style={{ marginTop: 12, color: 'var(--ac-error)', fontSize: 13 }}>{error}</p>}
    </div>
  )
}

export default PublishListPage
