import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import zhTranslations from '../locales/zh.json'
import enTranslations from '../locales/en.json'
import dayjs from 'dayjs'

export const STORAGE_KEY = 'autoclip_language'

export type SupportedLanguage = 'zh' | 'en'

const savedLanguage = (localStorage.getItem(STORAGE_KEY) as SupportedLanguage) || 'zh'

i18n.use(initReactI18next).init({
  resources: {
    zh: { translation: zhTranslations },
    en: { translation: enTranslations },
  },
  lng: savedLanguage,
  fallbackLng: 'zh',
  interpolation: {
    escapeValue: false,
  },
})

export const updateDayjsLocale = (lng: string) => {
  if (lng && lng.startsWith('en')) {
    dayjs.locale('en')
  } else {
    dayjs.locale('zh-cn')
  }
}

updateDayjsLocale(savedLanguage)

export const changeAppLanguage = (lng: SupportedLanguage) => {
  try {
    localStorage.setItem(STORAGE_KEY, lng)
  } catch (e) {
    console.warn('Failed to save language to localStorage:', e)
  }
  i18n.changeLanguage(lng)
  updateDayjsLocale(lng)
}

export default i18n