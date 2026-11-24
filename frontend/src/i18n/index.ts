import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import zh from './locales/zh.json'
import zhTW from './locales/zh-TW.json'
import en from './locales/en.json'
import ja from './locales/ja.json'
import ko from './locales/ko.json'
import es from './locales/es.json'
import pt from './locales/pt.json'
import ru from './locales/ru.json'
import fr from './locales/fr.json'
import id from './locales/id.json'
import tr from './locales/tr.json'
import vi from './locales/vi.json'
import de from './locales/de.json'
import { resolveLanguage, readPreference, LANGUAGE_STORAGE_KEY, type LanguagePreference } from './language'
import { setPromoLocale } from '../features/settings/sponsorPromoState'

export const languages = [
  { value: 'zh', label: '简体中文' }, { value: 'zh-TW', label: '繁體中文' },
  { value: 'en', label: 'English' },
  { value: 'ja', label: '日本語' }, { value: 'ko', label: '한국어' },
  { value: 'es', label: 'Español' }, { value: 'pt', label: 'Português (Brasil)' },
  { value: 'ru', label: 'Русский' }, { value: 'fr', label: 'Français' },
  { value: 'id', label: 'Bahasa Indonesia' }, { value: 'tr', label: 'Türkçe' },
  { value: 'vi', label: 'Tiếng Việt' }, { value: 'de', label: 'Deutsch' },
] as const

export const localeTags = { zh: 'zh-CN', 'zh-TW': 'zh-TW', en: 'en', ja: 'ja', ko: 'ko', es: 'es', pt: 'pt-BR', ru: 'ru', fr: 'fr', id: 'id', tr: 'tr', vi: 'vi', de: 'de' } as const
export { readPreference } from './language'

let currentPreference: LanguagePreference = readPreference()

void i18n.use(initReactI18next).init({
  resources: {
    zh: { translation: zh }, 'zh-TW': { translation: zhTW }, en: { translation: en },
    ja: { translation: ja }, ko: { translation: ko }, es: { translation: es },
    pt: { translation: pt }, ru: { translation: ru }, fr: { translation: fr },
    id: { translation: id }, tr: { translation: tr }, vi: { translation: vi }, de: { translation: de },
  },
  lng: resolveLanguage(currentPreference, navigator.languages),
  fallbackLng: 'en',
  supportedLngs: languages.map(l => l.value),
  keySeparator: false,
  nsSeparator: false,
  initAsync: false,
  interpolation: { escapeValue: false }, // React escapes text and interpolated user content.
  react: { useSuspense: false },
})

export const t = (key: string, values?: Record<string, unknown>): string => i18n.t(key, values ?? {}) as string
export const getLocale = () => localeTags[i18n.language as keyof typeof localeTags] ?? 'en'
const updateDocument = () => {
  document.documentElement.lang = getLocale()
  setPromoLocale(i18n.language)
}
updateDocument()
i18n.on('languageChanged', updateDocument)

export async function setLanguage(preference: LanguagePreference) {
  currentPreference = preference
  try { localStorage.setItem(LANGUAGE_STORAGE_KEY, preference) } catch { /* Private/restricted storage: selection still works for this session. */ }
  await i18n.changeLanguage(resolveLanguage(preference, navigator.languages))
}
window.addEventListener('languagechange', () => {
  if (currentPreference === 'system') void i18n.changeLanguage(resolveLanguage('system', navigator.languages))
})

export default i18n
