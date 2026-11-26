import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import GraficoPorHora from './GraficoPorHora.jsx'

// Igual ao que a API manda: todas as horas do eixo, inclusive as com zero
const POR_HORA = [7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18].map((hora) => ({
  hora,
  total: { 8: 4, 9: 6, 14: 1 }[hora] ?? 0,
}))

it('dia sem ninguém: avisa em vez de desenhar um gráfico vazio', () => {
  render(<GraficoPorHora porHora={[]} />)

  expect(screen.getByText('Nenhuma chegada registrada neste dia.')).toBeInTheDocument()
  expect(screen.queryByRole('img')).not.toBeInTheDocument()
})

it('uma coluna por hora, mas barra só onde houve chegada', () => {
  const { container } = render(<GraficoPorHora porHora={POR_HORA} />)

  // aria-label de cada coluna: o que o leitor de tela anuncia
  expect(screen.getByLabelText('09h: 6 chegadas')).toBeInTheDocument()
  expect(screen.getByLabelText('14h: 1 chegada')).toBeInTheDocument()
  expect(container.querySelectorAll('.coluna')).toHaveLength(12)
  expect(container.querySelectorAll('.barra')).toHaveLength(3)
})

it('passar o mouse mostra a dica; sair esconde', async () => {
  render(<GraficoPorHora porHora={POR_HORA} />)
  const coluna = screen.getByLabelText('09h: 6 chegadas')

  await userEvent.hover(coluna)
  expect(screen.getByText('6 chegadas').parentElement).toHaveTextContent('6 chegadas às 09h')

  await userEvent.unhover(coluna)
  expect(screen.queryByText('6 chegadas')).not.toBeInTheDocument()
})

it('teclado também mostra a dica (Tab até a coluna)', async () => {
  render(<GraficoPorHora porHora={POR_HORA} />)

  await userEvent.tab() // primeira coluna: 07h, sem ninguém
  expect(screen.getByText('0 chegadas').parentElement).toHaveTextContent('0 chegadas às 07h')
})

it('a tabela traz só as horas com chegada', () => {
  render(<GraficoPorHora porHora={POR_HORA} />)

  const linhas = within(screen.getByRole('table')).getAllByRole('row')
  expect(linhas.map((l) => l.textContent)).toEqual(['HoraChegadas', '08h4', '09h6', '14h1'])
})
