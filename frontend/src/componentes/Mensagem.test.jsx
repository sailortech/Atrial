// Teste de COMPONENTE: desenha de verdade (num navegador simulado,
// o jsdom) e confere o que a pessoa veria e o que acontece ao clicar.
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import Mensagem from './Mensagem.jsx'

it('sem mensagem, não desenha nada', () => {
  const { container } = render(<Mensagem mensagem={null} aoFechar={() => {}} />)
  expect(container).toBeEmptyDOMElement()
})

it('mostra o texto com a cor do tipo', () => {
  render(<Mensagem mensagem={{ tipo: 'erro', texto: 'Fila vazia.' }} aoFechar={() => {}} />)

  // getByRole procura como um leitor de tela procuraria
  const faixa = screen.getByRole('status')
  expect(faixa).toHaveTextContent('Fila vazia.')
  expect(faixa).toHaveClass('mensagem', 'erro')
})

it('o × avisa quem usa o componente', async () => {
  // vi.fn() = função "espiã": lembra se e como foi chamada
  const aoFechar = vi.fn()
  render(<Mensagem mensagem={{ tipo: 'sucesso', texto: 'Ok' }} aoFechar={aoFechar} />)

  await userEvent.click(screen.getByRole('button', { name: 'Fechar mensagem' }))

  expect(aoFechar).toHaveBeenCalledOnce()
})
