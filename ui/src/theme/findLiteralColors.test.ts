import { findLiteralColors } from './findLiteralColors'

describe('findLiteralColors con nombres de color', () => {
  it('detecta colores con nombre en atributos SVG', () => {
    expect(findLiteralColors('<rect fill="white" />')).toHaveLength(1)
    expect(findLiteralColors("<line stroke='red' />")).toHaveLength(1)
    expect(findLiteralColors('<stop stop-color="Black" />')).toHaveLength(1)
    expect(findLiteralColors('<circle fill={"white"} />')).toHaveLength(1)
  })

  it('detecta colores con nombre en CSS y estilos', () => {
    expect(findLiteralColors('a{color: black}')).toHaveLength(1)
    expect(findLiteralColors('a{color:black;}')).toHaveLength(1)
    expect(findLiteralColors('a{background: red url(x.png)}')).toHaveLength(1)
    expect(findLiteralColors('a{border:1px solid blue}')).toHaveLength(1)
    expect(findLiteralColors("style={{ color: 'orange' }}")).toHaveLength(1)
    expect(
      findLiteralColors("style={{ backgroundColor: 'tan' }}"),
    ).toHaveLength(1)
  })

  it('sigue detectando hex y funciones', () => {
    expect(findLiteralColors('fill="#fff"')).toHaveLength(1)
    expect(findLiteralColors('a{color:rgb(1,2,3)}')).toHaveLength(1)
  })

  it('no marca valores legítimos', () => {
    expect(findLiteralColors('<rect fill="none" />')).toHaveLength(0)
    expect(findLiteralColors('<rect fill="var(--wood)" />')).toHaveLength(0)
    expect(findLiteralColors('<rect fill="currentColor" />')).toHaveLength(0)
    expect(findLiteralColors('a{color: transparent}')).toHaveLength(0)
    expect(findLiteralColors('a{color: inherit}')).toHaveLength(0)
    expect(findLiteralColors('a{color: var(--text)}')).toHaveLength(0)
    expect(findLiteralColors('a{background: url(white.png)}')).toHaveLength(0)
    expect(findLiteralColors('a{border: 1px solid var(--line)}')).toHaveLength(
      0,
    )
  })

  it('no marca palabras sueltas que no son valor de propiedad de color', () => {
    expect(
      findLiteralColors('const white = 1 // fill the red box'),
    ).toHaveLength(0)
    expect(
      findLiteralColors('<p>El color rojo y white space</p>'),
    ).toHaveLength(0)
    expect(findLiteralColors('a{white-space: nowrap}')).toHaveLength(0)
    expect(
      findLiteralColors('a{font-weight: bold; text-align: left}'),
    ).toHaveLength(0)
    expect(findLiteralColors('color: string')).toHaveLength(0)
  })
})
