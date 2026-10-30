/** R1: intercept window close / tray Quit while Studio projects are running. */

import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { captureBusinessEvent } from '../../analytics/posthog'
import { safeStudioProperties } from '../../analytics/workflow'
import { isDesktopMode } from '../../utils/desktopMode'
import { useProjectStore } from '../../store/useProjectStore'
import { Btn, Dialog } from '../../ui'
import { t } from '../../i18n'

type ClosePayload = { from?: 'window' | 'tray' | string }

function runningCount(projects: { status?: string }[]): number {
  return projects.filter(project => project.status === 'processing').length
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
        const nextCount = runningCount(useProjectStore.getState().projects)
        if (nextCount <= 0) {
          emitQuitPrompt('quit', 0)
          void invokeQuit('quit')
          return
        }
        setCount(nextCount)
        setOpen(true)
      })
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
      onClose={() => choose('background')}
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
