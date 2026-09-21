/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** PostHog project API key（公开 key，可打包进前端）。未配置则禁用埋点。 */
  readonly VITE_PUBLIC_POSTHOG_KEY?: string
  /** PostHog 实例地址，US: https://us.i.posthog.com，EU: https://eu.i.posthog.com */
  readonly VITE_PUBLIC_POSTHOG_HOST?: string
  /** Sentry DSN（公开客户端 DSN）。未配置则崩溃上报 no-op。 */
  readonly VITE_PUBLIC_SENTRY_DSN?: string
  /** 打包时注入的应用版本，给 Sentry release 用。 */
  readonly VITE_APP_VERSION?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare module '*.svg' {
  const content: string
  export default content
}

declare module '*.svg?react' {
  import React from 'react'
  const ReactComponent: React.FunctionComponent<React.SVGProps<SVGSVGElement>>
  export default ReactComponent
}