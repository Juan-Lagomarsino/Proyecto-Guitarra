import { findLiteralColors } from './findLiteralColors'

describe('findLiteralColors', () => {
  it('detecta hex, rgb() y hsl()', () => {
    expect(findLiteralColors('a{color:#fff}')).toHaveLength(1)
    expect(findLiteralColors('a{color:#14121f}')).toHaveLength(1)
    expect(findLiteralColors('a{color:rgb(1,2,3)}')).toHaveLength(1)
    expect(findLiteralColors('a{color:hsl(1,2%,3%)}')).toHaveLength(1)
  })

  it('ignora variables y cosas que no son colores', () => {
    expect(findLiteralColors('a{color:var(--text)}')).toHaveLength(0)
    expect(findLiteralColors('href="#main" &#39;')).toHaveLength(0)
  })
})

const sources = import.meta.glob('/src/**/*.{ts,tsx,css}', {
  query: '?raw',
  import: 'default',
  eager: true,
}) as Record<string, string>

describe('ui/src no usa colores literales fuera de theme/', () => {
  const files = Object.entries(sources).filter(
    ([path]) => !path.includes('/src/theme/') && !/\.test\.tsx?$/.test(path),
  )

  it('encuentra archivos para revisar', () => {
    expect(files.length).toBeGreaterThan(3)
  })

  it.each(files)('%s', (_path, content) => {
    expect(findLiteralColors(content)).toEqual([])
  })
})
