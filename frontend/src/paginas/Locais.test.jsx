// Teste de uma PÁGINA inteira, com a API simulada: abre, carrega a
// lista, a pessoa clica e digita, e conferimos tela e pedidos.
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import { simularApi } from '../testes/simularApi.js'
import Locais from './Locais.jsx'

const QUATRO_ATIVOS = {
  locais: [
    { id: 1, nome: 'Consultório 1', ativo: true },
    { id: 2, nome: 'Consultório 2', ativo: true },
    { id: 3, nome: 'Consultório 3', ativo: true },
    { id: 4, nome: 'Triagem', ativo: true },
  ],
}

const linhaDe = (nome) => screen.getByRole('cell', { name: nome }).closest('tr')

it('lista os locais vindos da API', async () => {
  simularApi({ 'GET /api/locais': QUATRO_ATIVOS })
  render(<Locais />)

  expect(await screen.findByRole('cell', { name: 'Triagem' })).toBeInTheDocument()
  expect(screen.getAllByRole('button', { name: 'Desativar' })).toHaveLength(4)
})

it('o último local ativo não pode ser desativado', async () => {
  simularApi({
    'GET /api/locais': {
      locais: [
        { id: 4, nome: 'Triagem', ativo: true },
        { id: 1, nome: 'Consultório 1', ativo: false },
      ],
    },
  })
  render(<Locais />)

  await screen.findByRole('cell', { name: 'Triagem' })
  const botao = within(linhaDe('Triagem')).getByRole('button', { name: 'Desativar' })
  expect(botao).toBeDisabled()
  expect(botao).toHaveAttribute('title', 'É preciso ter pelo menos um local ativo.')
  expect(within(linhaDe('Consultório 1')).getByRole('button', { name: 'Reativar' })).toBeEnabled()
})

it('adicionar: manda o nome, mostra a mensagem e limpa o campo', async () => {
  const api = simularApi({
    'GET /api/locais': QUATRO_ATIVOS,
    'POST /api/locais': (corpo) => [201, { mensagem: `Local "${corpo.nome}" adicionado.` }],
  })
  render(<Locais />)

  const campo = await screen.findByLabelText('Nome do novo local')
  await userEvent.type(campo, 'Raio X')
  await userEvent.click(screen.getByRole('button', { name: 'Adicionar' }))

  expect(await screen.findByRole('status')).toHaveTextContent('Local "Raio X" adicionado.')
  expect(campo).toHaveValue('')
  expect(api.pedidos).toContainEqual({ metodo: 'POST', caminho: '/api/locais', corpo: { nome: 'Raio X' } })
  // Depois de adicionar, a lista é pedida de novo
  expect(api.pedidos.filter((p) => p.metodo === 'GET')).toHaveLength(2)
})

it('adicionar repetido: o erro do servidor aparece embaixo do campo', async () => {
  simularApi({
    'GET /api/locais': QUATRO_ATIVOS,
    'POST /api/locais': [422, {
      erro: 'Confira os campos destacados.',
      erros: { nome: 'Já existe um local chamado "triagem" (veja a lista abaixo).' },
    }],
  })
  render(<Locais />)

  const campo = await screen.findByLabelText('Nome do novo local')
  await userEvent.type(campo, 'triagem')
  await userEvent.click(screen.getByRole('button', { name: 'Adicionar' }))

  expect(await screen.findByText(/Já existe um local/)).toBeInTheDocument()
  expect(campo).toBeInvalid()
  expect(campo).toHaveValue('triagem') // o que foi digitado continua lá
})

it('desativar: erro 409 do servidor vira mensagem vermelha', async () => {
  simularApi({
    'GET /api/locais': QUATRO_ATIVOS,
    'POST /api/locais/2/alternar': [409, { erro: 'É preciso ter pelo menos um local ativo.' }],
  })
  render(<Locais />)

  await screen.findByRole('cell', { name: 'Consultório 2' })
  await userEvent.click(within(linhaDe('Consultório 2')).getByRole('button', { name: 'Desativar' }))

  const mensagem = await screen.findByRole('status')
  expect(mensagem).toHaveClass('erro')
  expect(mensagem).toHaveTextContent('É preciso ter pelo menos um local ativo.')
})
