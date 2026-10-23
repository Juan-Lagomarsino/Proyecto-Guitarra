import { ApiError } from '../../api/client'
import { errorText, looksLikeSongLink, stepLabel } from './analysis'

describe('stepLabel', () => {
  it.each([
    ['source', 'Buscando la canción'],
    ['download', 'Descargando el audio'],
    ['tempo', 'Detectando el tempo'],
    ['chords', 'Reconociendo acordes'],
    ['structure', 'Detectando secciones'],
    ['cifraclub', 'Consultando Cifra Club'],
    ['strum', 'Proponiendo rasgueo'],
    ['assemble', 'Armando la canción'],
  ])('traduce %s', (step, label) => {
    expect(stepLabel(step)).toBe(label)
  })

  it('deja el paso desconocido tal cual', () => {
    expect(stepLabel('paso_nuevo')).toBe('paso_nuevo')
  })
})

describe('looksLikeSongLink', () => {
  it.each([
    'https://www.youtube.com/watch?v=abc',
    'https://youtu.be/abc',
    'https://music.youtube.com/watch?v=abc',
    'https://m.youtube.com/shorts/abc',
    'https://open.spotify.com/track/123',
    'spotify:track:123',
    '  https://youtu.be/abc  ',
  ])('acepta %s', (link) => {
    expect(looksLikeSongLink(link)).toBe(true)
  })

  it.each(['', 'hola', 'https://example.com/x', 'youtube'])(
    'rechaza %s',
    (link) => {
      expect(looksLikeSongLink(link)).toBe(false)
    },
  )
})

describe('errorText', () => {
  it('usa el detail string de la API', () => {
    expect(errorText(new ApiError(422, 'x', 'Link inválido'))).toBe(
      'Link inválido',
    )
  })

  it('une los msg de un detail en lista', () => {
    const detail = [{ msg: 'Falta el título' }, { msg: 'Falta el artista' }]
    expect(errorText(new ApiError(422, 'x', detail))).toBe(
      'Falta el título. Falta el artista',
    )
  })

  it('cae al mensaje del error o a un texto genérico', () => {
    expect(errorText(new Error('boom'))).toBe('boom')
    expect(errorText('algo')).toBe('Error desconocido')
  })
})
