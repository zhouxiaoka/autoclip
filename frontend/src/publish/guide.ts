/** 发布操作教程在官网，应用内只给入口，方便以后改步骤而不发版。 */
export const PUBLISH_GUIDE_ORIGIN = 'https://zhouxiaoka.github.io/autoclip_intro'
export const PUBLISH_GUIDE_PATH = '/guides/publish/'

const LANGS = ['zh', 'en', 'ja', 'ko', 'es', 'pt', 'ru', 'fr'] as const

export function publishGuideHref(lang?: string): string {
  const raw = (lang || '').toLowerCase().replace('_', '-')
  const code = raw.split('-')[0]
  const q = (LANGS as readonly string[]).includes(code) ? code : 'en'
  return `${PUBLISH_GUIDE_ORIGIN}${PUBLISH_GUIDE_PATH}?lang=${q}`
}
