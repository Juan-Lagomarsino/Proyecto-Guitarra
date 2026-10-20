import { useLayoutEffect, useRef, useState } from 'react'
import type { RefObject } from 'react'

/**
 * Mide el ancho del elemento con ResizeObserver. Si se pasa `fixedWidth`
 * no observa nada y lo devuelve tal cual (útil en tests).
 * Devuelve 0 mientras no hay medida.
 */
export function useContainerWidth<T extends HTMLElement>(
  fixedWidth?: number,
): [RefObject<T | null>, number] {
  const ref = useRef<T | null>(null)
  const [measured, setMeasured] = useState(0)

  useLayoutEffect(() => {
    const element = ref.current
    if (fixedWidth !== undefined || !element) return
    setMeasured(element.getBoundingClientRect().width)
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(([entry]) =>
      setMeasured(entry.contentRect.width),
    )
    observer.observe(element)
    return () => observer.disconnect()
  }, [fixedWidth])

  return [ref, fixedWidth ?? measured]
}
