import { useRef, useState } from 'react'
import { t } from '../../i18n'
import { useTranslation } from 'react-i18next'
import { Btn } from '../../ui'
import { modelSettingsApi } from './modelSettingsApi'
import { LOCAL_RECOMMENDED_MODELS, localRecommendCopy } from './localModelGate'

/** T3: recommend qwen2.5 / llama3.1 and one-click Ollama pull with SSE progress. */
export default function LocalRecommendPull({
  baseUrl,
  provider,
  onPulled,
}: {
  baseUrl: string
  provider?: string | null
  onPulled?: (model: string) => void
}) {
  useTranslation()
  const [pulling, setPulling] = useState<string | null>(null)
  const [progress, setProgress] = useState('')
  const [error, setError] = useState('')
  const abortRef = useRef<AbortController | null>(null)

  if (provider !== 'ollama') return null

  const pull = async (model: string) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setPulling(model)
    setProgress(t('正在拉取…'))
    setError('')
    try {
      const response = await modelSettingsApi.ollamaPull(model, baseUrl || 'http://127.0.0.1:11434/v1', controller.signal)
      if (!response.ok || !response.body) {
        setError(t('拉取失败，请确认本机 Ollama 已启动。'))
        return
      }
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const chunks = buffer.split('\n\n')
        buffer = chunks.pop() || ''
        for (const chunk of chunks) {
          const line = chunk.split('\n').find(row => row.startsWith('data: '))
          if (!line) continue
          let payload: { status?: string; completed?: number; total?: number; done?: boolean; error?: string } = {}
          try { payload = JSON.parse(line.slice(6)) } catch { continue }
          if (payload.error) {
            setError(t('拉取失败，请确认本机 Ollama 已启动。'))
            return
          }
          if (typeof payload.completed === 'number' && typeof payload.total === 'number' && payload.total > 0) {
            const pct = Math.min(100, Math.round((payload.completed / payload.total) * 100))
            setProgress(t('正在拉取 {{model}}… {{pct}}%', { model, pct }))
          } else if (payload.status) {
            setProgress(`${payload.status}`)
          }
          if (payload.done) {
            setProgress(t('已拉取 {{model}}', { model }))
            onPulled?.(model)
            return
          }
        }
      }
    } catch (e) {
      if ((e as { name?: string })?.name === 'AbortError') return
      setError(t('拉取失败，请确认本机 Ollama 已启动。'))
    } finally {
      if (abortRef.current === controller) abortRef.current = null
      setPulling(null)
    }
  }

  return (
    <div className="ac-local-recommend" data-testid="local-recommend-pull" style={{ marginTop: 10 }}>
      <p className="ac-note" style={{ marginBottom: 6 }}>{t(localRecommendCopy())}</p>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
        {LOCAL_RECOMMENDED_MODELS.map(item => (
          <Btn
            key={item.id}
            size="sm"
            className="ac-btn--pill"
            loading={pulling === item.id}
            disabled={!!pulling && pulling !== item.id}
            onClick={() => void pull(item.id)}
          >
            {t('一键拉取')} {item.label}
          </Btn>
        ))}
        {pulling && (
          <Btn size="sm" variant="text" onClick={() => abortRef.current?.abort()}>{t('取消')}</Btn>
        )}
      </div>
      {progress && <p className="ac-note" role="status" data-testid="ollama-pull-progress">{progress}</p>}
      {error && <p className="ac-note ac-note--error" role="alert">{error}</p>}
    </div>
  )
}
