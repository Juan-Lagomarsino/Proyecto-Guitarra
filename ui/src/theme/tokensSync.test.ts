import tokensCss from './tokens.css?raw'
import { defaultTheme } from './defaultTheme'

const normalize = (value: string) => value.replaceAll("'", '"').trim()

describe('tokens.css', () => {
  it('coincide con defaultTheme', () => {
    const declared = Object.fromEntries(
      [...tokensCss.matchAll(/(--[\w-]+):\s*([^;]+);/g)].map(
        ([, name, value]) => [name, normalize(value)],
      ),
    )
    const expected = Object.fromEntries(
      Object.entries(defaultTheme).map(([name, value]) => [
        name,
        normalize(value),
      ]),
    )

    expect(declared).toEqual(expected)
  })
})
