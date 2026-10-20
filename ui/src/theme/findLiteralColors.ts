const LITERAL_COLOR = /(?<![&\w])#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(/g

/** Devuelve los colores literales (hex, rgb(), hsl()) que aparecen en un texto. */
export function findLiteralColors(source: string): string[] {
  return source.match(LITERAL_COLOR) ?? []
}
