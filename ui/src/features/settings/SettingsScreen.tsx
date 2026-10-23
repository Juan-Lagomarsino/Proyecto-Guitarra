import { useEffect, useState, type FormEvent } from 'react'
import { defaultTheme } from '../../theme/defaultTheme'
import { ColorField } from './ColorField'
import {
  COLOR_FIELDS,
  FONT_FIELDS,
  FONT_PRESETS,
  fontLabel,
  sameFont,
  timezoneOptions,
} from './options'
import { useSavedTheme } from './SavedTheme'
import {
  describeSaveError,
  getSettings,
  putSettings,
  toTheme,
  type AppSettings,
} from './settingsApi'
import { ThemePreview } from './ThemePreview'
import './settings.css'

type LoadState = 'loading' | 'ready' | 'failed'

const fontOptions = (token: string, current: string) => {
  const presets = FONT_PRESETS[token] ?? []
  const known = presets.some((preset) => sameFont(preset, current))
  return known ? presets : [current, ...presets]
}

export function SettingsScreen() {
  const { applyTheme } = useSavedTheme()
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const [saved, setSaved] = useState<AppSettings | null>(null)
  const [draft, setDraft] = useState<Record<string, string>>({})
  const [timezone, setTimezone] = useState('')
  const [errors, setErrors] = useState<string[]>([])
  const [notice, setNotice] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    getSettings(controller.signal)
      .then((settings) => {
        setSaved(settings)
        setDraft({ ...defaultTheme, ...toTheme(settings) })
        setTimezone(settings.timezone)
        setLoadState('ready')
      })
      .catch(() => {
        if (!controller.signal.aborted) setLoadState('failed')
      })
    return () => controller.abort()
  }, [])

  if (loadState !== 'ready' || !saved) {
    return (
      <section className="page">
        <h2 className="display page-title">Ajustes</h2>
        <p
          className="page-note"
          role={loadState === 'failed' ? 'alert' : 'status'}
        >
          {loadState === 'failed'
            ? 'No se pudieron cargar los ajustes.'
            : 'Cargando ajustes…'}
        </p>
      </section>
    )
  }

  const setToken = (token: string, value: string) => {
    setNotice('')
    setDraft((current) => ({ ...current, [token]: value }))
  }

  const restoreDefaults = () => {
    setNotice('Tema por defecto cargado. Guardá para aplicarlo.')
    setErrors([])
    setDraft({ ...defaultTheme })
  }

  const save = async (event: FormEvent) => {
    event.preventDefault()
    setSaving(true)
    setErrors([])
    setNotice('')
    try {
      const result = await putSettings({
        ...saved,
        timezone,
        theme_tokens: Object.fromEntries(
          COLOR_FIELDS.map(({ token }) => [token, draft[token]]),
        ),
        fonts: Object.fromEntries(
          FONT_FIELDS.map(({ token }) => [token, draft[token]]),
        ),
      })
      setSaved(result)
      applyTheme({ ...defaultTheme, ...toTheme(result) })
      setNotice('Ajustes guardados.')
    } catch (error) {
      setErrors(describeSaveError(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="page settings">
      <h2 className="display page-title">Ajustes</h2>
      <p className="page-note">
        Elegí los colores, las tipografías y tu zona horaria. La vista previa
        cambia mientras editás.
      </p>

      <ThemePreview theme={draft} />

      <form className="settings-form" onSubmit={save} noValidate>
        <fieldset>
          <legend>Colores</legend>
          <div className="settings-grid">
            {COLOR_FIELDS.map(({ token, label }) => (
              <ColorField
                key={token}
                token={token}
                label={label}
                value={draft[token]}
                onChange={(value) => setToken(token, value)}
              />
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend>Tipografías</legend>
          <div className="settings-grid">
            {FONT_FIELDS.map(({ token, label }) => (
              <div className="settings-field" key={token}>
                <label htmlFor={`font-${token}`}>{label}</label>
                <select
                  id={`font-${token}`}
                  value={
                    fontOptions(token, draft[token]).find((option) =>
                      sameFont(option, draft[token]),
                    ) ?? draft[token]
                  }
                  onChange={(event) => setToken(token, event.target.value)}
                >
                  {fontOptions(token, draft[token]).map((option) => (
                    <option key={option} value={option}>
                      {fontLabel(option)}
                    </option>
                  ))}
                </select>
              </div>
            ))}
          </div>
        </fieldset>

        <fieldset>
          <legend>Zona horaria</legend>
          <div className="settings-field">
            <label htmlFor="timezone">Zona horaria</label>
            <select
              id="timezone"
              value={timezone}
              onChange={(event) => {
                setNotice('')
                setTimezone(event.target.value)
              }}
            >
              {timezoneOptions(timezone).map((zone) => (
                <option key={zone} value={zone}>
                  {zone}
                </option>
              ))}
            </select>
          </div>
        </fieldset>

        {errors.length > 0 && (
          <div className="settings-errors" role="alert">
            <p>No se pudo guardar:</p>
            <ul>
              {errors.map((message) => (
                <li key={message}>{message}</li>
              ))}
            </ul>
          </div>
        )}
        {notice && (
          <p className="settings-notice" role="status">
            {notice}
          </p>
        )}

        <div className="settings-actions">
          <button type="submit" className="btn btn-primary" disabled={saving}>
            {saving ? 'Guardando…' : 'Guardar'}
          </button>
          <button type="button" className="btn" onClick={restoreDefaults}>
            Volver al tema por defecto
          </button>
        </div>
      </form>
    </section>
  )
}
