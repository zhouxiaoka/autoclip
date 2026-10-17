import { useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { SETTINGS_SAVED_EVENT, returnAfterSave } from './settingsReturn'

/** Mounted once in App: after a successful model-settings save opened from a failed project, go back to it. */
export default function SettingsReturnListener() {
  const location = useLocation()
  const navigate = useNavigate()
  useEffect(() => {
    const onSaved = () => {
      if (location.pathname !== '/settings') return
      const target = returnAfterSave(location.search)
      if (target) navigate(target)
    }
    window.addEventListener(SETTINGS_SAVED_EVENT, onSaved)
    return () => window.removeEventListener(SETTINGS_SAVED_EVENT, onSaved)
  }, [location.pathname, location.search, navigate])
  return null
}
