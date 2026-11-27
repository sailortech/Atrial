import { readFileSync } from 'node:fs'

import { act, renderHook } from '@testing-library/react'
import { afterEach, expect, it } from 'vitest'

import useTema from './useTema.js'

const raiz = () => document.documentElement

afterEach(() => {
  localStorage.clear()
  delete raiz().dataset.tema
})

it('sem escolha salva: automático (o <html> fica sem data-tema)', () => {
  const { result } = renderHook(() => useTema())

  expect(result.current[0]).toBe('auto')
  expect(raiz()).not.toHaveAttribute('data-tema')
})

it('escolher escuro: marca o <html> e guarda a escolha', () => {
  const { result } = renderHook(() => useTema())

  // act(): "faça isto e espere o React terminar de atualizar"
  act(() => result.current[1]('escuro'))

  expect(raiz()).toHaveAttribute('data-tema', 'escuro')
  expect(localStorage.getItem('atrial-tema')).toBe('escuro')
})

it('voltar para automático: tira a marca e esquece a escolha', () => {
  const { result } = renderHook(() => useTema())
  act(() => result.current[1]('claro'))

  act(() => result.current[1]('auto'))

  expect(raiz()).not.toHaveAttribute('data-tema')
  expect(localStorage.getItem('atrial-tema')).toBeNull()
})

it('lembra a escolha ao abrir de novo', () => {
  localStorage.setItem('atrial-tema', 'escuro')

  const { result } = renderHook(() => useTema())

  expect(result.current[0]).toBe('escuro')
  expect(raiz()).toHaveAttribute('data-tema', 'escuro')
})

it('valor estranho salvo vira automático', () => {
  localStorage.setItem('atrial-tema', 'roxo')

  const { result } = renderHook(() => useTema())

  expect(result.current[0]).toBe('auto')
})

it('no CSS, o escuro "escolhido" e o escuro "do sistema" têm as mesmas cores', () => {
  // Lido do disco: nos testes, o Vitest entrega os arquivos .css vazios.
  // (Caminho a partir de frontend/, de onde o "npm test" roda.)
  const css = readFileSync('src/app.css', 'utf-8')

  // O CSS não deixa um bloco reaproveitar o outro, então as cores
  // escuras estão escritas duas vezes. Se alguém mudar só uma, isto avisa.
  const bloco = (inicio) => {
    const depois = css.slice(css.indexOf(inicio))
    return depois.slice(depois.indexOf('{') + 1, depois.indexOf('}'))
  }
  const declaracoes = (texto) => texto
    .replace(/\/\*[\s\S]*?\*\//g, '') // tira os comentários
    .split(';').map((d) => d.trim()).filter(Boolean)

  const escolhido = declaracoes(bloco(":root[data-tema='escuro']"))
  const doSistema = declaracoes(bloco(':root:not([data-tema])'))

  expect(escolhido.length).toBeGreaterThan(20)
  expect(doSistema).toEqual(escolhido)
})
