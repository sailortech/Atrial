// Testes de funções "puras": entra um valor, sai outro. Os mais simples.
import { describe, expect, it } from 'vitest'

import { marcarErro, mascaraCpf } from './formularios.js'

describe('mascaraCpf', () => {
  // it.each roda o MESMO teste para cada linha (o parametrize do pytest)
  it.each([
    ['', ''],
    ['529', '529'],
    ['5299', '529.9'],
    ['5299822', '529.982.2'],
    ['529982247', '529.982.247'],
    ['5299822472', '529.982.247-2'],
    ['52998224725', '529.982.247-25'],
  ])('"%s" vira "%s"', (digitado, esperado) => {
    expect(mascaraCpf(digitado)).toBe(esperado)
  })

  it('tira letras e símbolos, e para em 11 números', () => {
    expect(mascaraCpf('529.982.247-25999')).toBe('529.982.247-25')
    expect(mascaraCpf('abc529xyz')).toBe('529')
  })

  it('formatar de novo o que já está formatado não muda nada', () => {
    expect(mascaraCpf('529.982.247-25')).toBe('529.982.247-25')
  })
})

describe('marcarErro', () => {
  it('campo com erro: marcado e ligado à mensagem', () => {
    expect(marcarErro('cpf', { cpf: 'CPF inválido' })).toEqual({
      'aria-invalid': true,
      'aria-describedby': 'erro-cpf',
    })
  })

  it('campo sem erro: nada marcado', () => {
    expect(marcarErro('nome', { cpf: 'CPF inválido' })).toEqual({
      'aria-invalid': undefined,
      'aria-describedby': undefined,
    })
  })
})
