import { categoryLabel } from './categories'

describe('categoryLabel', () => {
  it.each([
    ['warmup', 'Calentamiento'],
    ['technique', 'Técnica'],
    ['riff', 'Riff'],
    ['improvisation', 'Improvisación'],
  ])('traduce %s', (slug, label) => {
    expect(categoryLabel(slug)).toBe(label)
  })

  it('con un slug desconocido devuelve el slug', () => {
    expect(categoryLabel('otra-cosa')).toBe('otra-cosa')
  })
})
