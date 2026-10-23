const HEX6 = /^#[0-9a-f]{6}$/i

interface ColorFieldProps {
  token: string
  label: string
  value: string
  onChange: (value: string) => void
}

/** Texto libre para cualquier color CSS, más el muestrario nativo cuando el valor es #rrggbb. */
export function ColorField({ token, label, value, onChange }: ColorFieldProps) {
  return (
    <div className="color-field">
      <label className="color-field-label" htmlFor={`color-${token}`}>
        {label}
        <code>{token}</code>
      </label>
      <div className="color-field-inputs">
        {HEX6.test(value) && (
          <input
            type="color"
            aria-label={`Muestrario de ${label}`}
            value={value}
            onChange={(event) => onChange(event.target.value)}
          />
        )}
        <input
          id={`color-${token}`}
          type="text"
          spellCheck={false}
          autoComplete="off"
          value={value}
          onChange={(event) => onChange(event.target.value)}
        />
      </div>
    </div>
  )
}
