import { describe, expect, it } from 'vitest'

import { caminhoBarra, chegadas, doisDigitos, escalaDoEixo } from './escala.js'

describe('escalaDoEixo', () => {
  it.each([
    [1, 1, [0, 1]],
    [5, 5, [0, 1, 2, 3, 4, 5]],
    [6, 6, [0, 2, 4, 6]],
    [7, 8, [0, 2, 4, 6, 8]],
    [23, 25, [0, 5, 10, 15, 20, 25]],
  ])('maior = %i -> topo %i', (maior, topo, marcas) => {
    expect(escalaDoEixo(maior)).toEqual({ topo, marcas })
  })

  it('nunca passa de 6 marcas (0 + no máximo 5)', () => {
    for (let maior = 1; maior <= 500; maior++) {
      const { topo, marcas } = escalaDoEixo(maior)
      expect(marcas.length).toBeLessThanOrEqual(6)
      expect(topo).toBeGreaterThanOrEqual(maior) // a barra maior cabe
    }
  })
})

describe('caminhoBarra', () => {
  it('começa e termina no chão (base reta)', () => {
    const d = caminhoBarra(10, 50, 20, 200)
    expect(d.startsWith('M10,200')).toBe(true)
    expect(d.endsWith('V200 Z')).toBe(true)
  })

  it('barra baixinha: o canto arredondado não passa da altura dela', () => {
    // altura 2 -> raio no máximo 2 (e não 4)
    expect(caminhoBarra(0, 198, 20, 200)).toContain('V200 Q0,198 2,198')
  })
})

describe('textos', () => {
  it('hora com dois dígitos', () => {
    expect(doisDigitos(9)).toBe('09h')
    expect(doisDigitos(14)).toBe('14h')
  })

  it('singular e plural', () => {
    expect(chegadas(1)).toBe('1 chegada')
    expect(chegadas(0)).toBe('0 chegadas')
    expect(chegadas(6)).toBe('6 chegadas')
  })
})
