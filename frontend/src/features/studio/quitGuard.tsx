/** Intercept window close / tray Quit while Studio projects are running. */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { captureBusinessEvent } from '../../analytics/posthog'
import { safeStudioProperties } from '../../analytics/workflow'
import { isDesktopMode } from '../../utils/desktopMode'
import { useProjectStore } from '../../store/useProjectStore'
import { Btn, Dialog } from '../../ui'
import { t } from '../../i18n'
import { getKeepAwakeController, projectIsProducing, type KeepAwakeProjectLike } from './keepAwake'

type ClosePayload = { from?: 'window' | 'tray' | string }
type GuardProjectLike = KeepAwakeProjectLike & { id?: string }

/** Same producing signal as keep-awake — includes both projects list and active detail-page workspace/statusbar sources. */
export function runningCount(projects: GuardProjectLike[], activeSources?: Map<string, boolean>): number {
  const activeIds = new Set<string>()
  let anonymous = 0
  for (const project of projects) {
    if (!projectIsProducing(project)) continue
    if (project.id) activeIds.add(String(project.id))
    else anonymous += 1
  }
  if (activeSources) {
    for (const [key, producing] of activeSources.entries()) {
      if (!producing || key === 'projects') continue
      const sep = key.indexOf(':')
      const id = sep >= 0 ? key.slice(sep + 1) : key
      if (id) activeIds.add(id)
      else anonymous += 1
    }
  }
  return activeIds.size + anonymous
}

async function invokeQuit(choice: 'background' | 'quit') {
  const { invoke } = await import('@tauri-apps/api/core')
  if (choice === 'background') await invoke('hide_to_tray')
  else await invoke('confirm_quit')
}

export function emitQuitPrompt(choice: 'background' | 'quit', count: number) {
  captureBusinessEvent('quit_prompt', safeStudioProperties({ choice, running_count: Math.max(0, count) }))
}

/** Single listener + dialog. Mount once under App. */
export default function QuitGuard() {
  useTranslation()
  useProjectStore(state => state.projects)
  const [open, setOpen] = useState(false)
  const [count, setCount] = useState(0)

  useEffect(() => {
    let unlisten: (() => void) | undefined
    let cancelled = false
    void (async () => {
      if (!(await isDesktopMode())) return
      const { listen } = await import('@tauri-apps/api/event')
      unlisten = await listen<ClosePayload>('close-requested', () => {
        if (cancelled) return
        const nextCount = runningCount(useProjectStore.getState().projects, getKeepAwakeController().getSources())
        if (nextCount <= 0) {
          emitQuitPrompt('quit', 0)
          void invokeQuit('quit')
          return
        }
        setCount(nextCount)
        setOpen(true)
      })
      // P2 #10: tell Rust the close-requested listener is live so prevent_close is safe.
      if (!cancelled) {
        try {
          const { invoke } = await import('@tauri-apps/api/core')
          await invoke('quit_guard_ready')
        } catch (error) {
          console.warn('quit_guard_ready failed', error)
        }
      }
    })()
    return () => {
      cancelled = true
      unlisten?.()
    }
  }, [])

  const choose = (choice: 'background' | 'quit') => {
    setOpen(false)
    emitQuitPrompt(choice, count)
    void invokeQuit(choice)
  }

  return (
    <Dialog
      open={open}
      onClose={() => setOpen(false)}
      title={t('正在制作 {{count}} 个项目', { count })}
      description={t('退出会中断正在进行的制作。可以选择后台继续，完成后会通知你。')}
      footer={
        <div className="studio-actions">
          <Btn variant="cta" onClick={() => choose('background')}>{t('后台继续')}</Btn>
          <Btn onClick={() => choose('quit')}>{t('仍然退出')}</Btn>
        </div>
      }
    />
  )
}
