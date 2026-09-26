import { useEffect, useState, type ReactNode, type FormEvent } from 'react'
import { authenticatedFetch, isDesktop } from '../utils/auth'

export default function AuthGate({ children }: { children: ReactNode }) {
  const [ready, setReady] = useState(false)
  const [checking, setChecking] = useState(true)
  const [token, setToken] = useState('')
  const [error, setError] = useState('')
  const check = async () => {
    setChecking(true)
    try { setReady((await authenticatedFetch('/api/auth/session')).ok) }
    catch { setError('Unable to connect. Check that AutoClip is running.') }
    finally { setChecking(false) }
  }
  useEffect(() => {
    void check()
    const required = () => setReady(false)
    window.addEventListener('autoclip-auth-required', required)
    return () => window.removeEventListener('autoclip-auth-required', required)
  }, [])
  const login = async (event: FormEvent) => {
    event.preventDefault()
    setError('')
    setChecking(true)
    try {
      const response = await authenticatedFetch('/api/auth/login', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token }),
      })
      setToken('')
      if (!response.ok) throw new Error('Access key was not accepted.')
      setReady(true)
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to sign in.') }
    finally { setChecking(false) }
  }
  if (ready) return <>{children}</>
  return <main style={{ maxWidth: 420, margin: '15vh auto', padding: 32, color: 'var(--ac-ink)' }}>
    <h1>AutoClip</h1>
    {isDesktop() ? <><p>{checking ? 'Connecting securely…' : 'Unable to connect to AutoClip.'}</p><button className="ac-btn" onClick={() => void check()} disabled={checking}>Retry</button></> :
      <form onSubmit={login}>
        <h2>Sign in</h2>
        <p>Enter the access key provided by your AutoClip administrator.</p>
        <label htmlFor="access-key">Access key</label>
        <input id="access-key" className="ac-input" type="password" value={token} onChange={event => setToken(event.target.value)} autoComplete="current-password" required />
        <button className="ac-btn" type="submit" disabled={checking || !token}>{checking ? 'Connecting…' : 'Continue'}</button>
      </form>}
    {error && <p role="alert">{error}</p>}
  </main>
}
