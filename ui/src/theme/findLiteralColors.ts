const FUNCTIONAL_OR_HEX = /(?<![&\w])#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(/g

/** Nombres de color CSS. No incluye `transparent`, `currentColor`, `inherit` ni `none`. */
const NAMED_COLORS = new Set(
  (
    'aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue ' +
    'blueviolet brown burlywood cadetblue chartreuse chocolate coral cornflowerblue cornsilk ' +
    'crimson cyan darkblue darkcyan darkgoldenrod darkgray darkgreen darkgrey darkkhaki ' +
    'darkmagenta darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen ' +
    'darkslateblue darkslategray darkslategrey darkturquoise darkviolet deeppink deepskyblue ' +
    'dimgray dimgrey dodgerblue firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite ' +
    'gold goldenrod gray green greenyellow grey honeydew hotpink indianred indigo ivory khaki ' +
    'lavender lavenderblush lawngreen lemonchiffon lightblue lightcoral lightcyan ' +
    'lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon lightseagreen ' +
    'lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime limegreen linen ' +
    'magenta maroon mediumaquamarine mediumblue mediumorchid mediumpurple mediumseagreen ' +
    'mediumslateblue mediumspringgreen mediumturquoise mediumvioletred midnightblue mintcream ' +
    'mistyrose moccasin navajowhite navy oldlace olive olivedrab orange orangered orchid ' +
    'palegoldenrod palegreen paleturquoise palevioletred papayawhip peachpuff peru pink plum ' +
    'powderblue purple rebeccapurple red rosybrown royalblue saddlebrown salmon sandybrown ' +
    'seagreen seashell sienna silver skyblue slateblue slategray slategrey snow springgreen ' +
    'steelblue tan teal thistle tomato turquoise violet wheat white whitesmoke yellow ' +
    'yellowgreen'
  ).split(' '),
)

const COLOR_ATTRIBUTES =
  'fill|stroke|color|stop-color|flood-color|lighting-color|stopColor|floodColor|lightingColor'

/** fill="white", stroke='red', fill={"white"} */
const ATTRIBUTE_VALUE = new RegExp(
  `(?<![\\w-])(?:${COLOR_ATTRIBUTES})\\s*=\\s*\\{?\\s*["'\`]\\s*([a-zA-Z]+)\\s*["'\`]`,
  'g',
)

const COLOR_PROPERTIES = [
  'color',
  'background',
  'background-color',
  'border',
  'border-color',
  'border-top',
  'border-right',
  'border-bottom',
  'border-left',
  'border-top-color',
  'border-right-color',
  'border-bottom-color',
  'border-left-color',
  'outline',
  'outline-color',
  'fill',
  'stroke',
  'stop-color',
  'flood-color',
  'caret-color',
  'accent-color',
  'column-rule',
  'text-decoration',
  'text-decoration-color',
  'text-shadow',
  'box-shadow',
]
const toCamelCase = (name: string) =>
  name.replace(/-(\w)/g, (_, c: string) => c.toUpperCase())
const DECLARATION_PROPERTIES = [
  ...new Set([...COLOR_PROPERTIES, ...COLOR_PROPERTIES.map(toCamelCase)]),
]
  .sort((a, b) => b.length - a.length)
  .join('|')

/** color: black; border: 1px solid blue; { color: 'orange' } */
const DECLARATION = new RegExp(
  `(?<![\\w-])(?:${DECLARATION_PROPERTIES})["']?\\s*:\\s*([^;{}\\n]*)`,
  'gi',
)

function namedColorsIn(value: string): string[] {
  const withoutFunctions = value.replace(/\b(?:var|url)\([^)]*\)/g, ' ')
  const words = withoutFunctions.match(/[a-zA-Z]+/g) ?? []
  return words.filter((word) => NAMED_COLORS.has(word.toLowerCase()))
}

function namedColorsInAttributes(source: string): string[] {
  return [...source.matchAll(ATTRIBUTE_VALUE)].flatMap(([, value]) =>
    namedColorsIn(value),
  )
}

function namedColorsInDeclarations(source: string): string[] {
  return [...source.matchAll(DECLARATION)].flatMap(([, value]) =>
    namedColorsIn(value),
  )
}

/**
 * Devuelve los colores literales que aparecen en un texto: hex, rgb()/hsl(),
 * y nombres de color (white, red…) en atributos SVG y en declaraciones CSS.
 */
export function findLiteralColors(source: string): string[] {
  return [
    ...(source.match(FUNCTIONAL_OR_HEX) ?? []),
    ...namedColorsInAttributes(source),
    ...namedColorsInDeclarations(source),
  ]
}
