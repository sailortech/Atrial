// Renomear na página de Locais: o formulário aparece NA linha, salva
// com PUT, mostra o erro do servidor e some com Esc ou Cancelar.
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'

import Locais from '../../paginas/Locais.jsx'
import { simularApi } from '../../testes/simularApi.js'

const LISTA = {
  locais: [
    { id: 2, nome: 'Consultório 2', ativo: true },
    { id: 4, nome: 'Triagem', ativo: true },
  ],
}

async function abrirEdicao(nome) {
  await screen.findByRole('cell', { name: nome })
  const linha = screen.getByRole('cell', { name: nome }).closest('tr')
  await userEvent.click(within(linha).getByRole('button', { name: 'Renomear' }))
  return screen.getByLabelText(`Novo nome para ${nome}`)
}

it('abre com o nome atual, já selecionado para digitar por cima', async () => {
  simularApi({ 'GET /api/locais': LISTA })
  render(<Locais />)

  const campo = await abrirEdicao('Consultório 2')

  expect(campo).toHaveValue('Consultório 2')
  expect(campo).toHaveFocus()
  // Texto todo selecionado: digitar substitui em vez de juntar
  expect([campo.selectionStart, campo.selectionEnd]).toEqual([0, 'Consultório 2'.length])
  // Na linha em edição, o botão Renomear some
  expect(screen.getAllByRole('button', { name: 'Renomear' })).toHaveLength(1)
})

it('salvar: manda PUT com o nome novo e volta a mostrar a lista', async () => {
  const api = simularApi({
    'GET /api/locais': LISTA,
    'PUT /api/locais/2': (corpo) => ({ mensagem: `Local "Consultório 2" agora se chama "${corpo.nome}".` }),
  })
  render(<Locais />)

  const campo = await abrirEdicao('Consultório 2')
  // skipClick: digita direto no campo já focado (um clique tiraria a seleção)
  await userEvent.type(campo, 'Pediatria{Enter}', { skipClick: true }) // {Enter} = apertar Enter

  expect(await screen.findByRole('status')).toHaveTextContent('agora se chama "Pediatria"')
  expect(api.pedidos).toContainEqual({ metodo: 'PUT', caminho: '/api/locais/2', corpo: { nome: 'Pediatria' } })
  expect(screen.queryByLabelText(/Novo nome/)).not.toBeInTheDocument()
})

it('nome repetido: o erro aparece embaixo do campo, e o campo continua aberto', async () => {
  simularApi({
    'GET /api/locais': LISTA,
    'PUT /api/locais/2': [422, {
      erro: 'Confira os campos destacados.',
      erros: { nome: 'Já existe um local chamado "triagem" (veja a lista abaixo).' },
    }],
  })
  render(<Locais />)

  const campo = await abrirEdicao('Consultório 2')
  await userEvent.type(campo, 'triagem{Enter}', { skipClick: true })

  expect(await screen.findByText(/Já existe um local/)).toBeInTheDocument()
  expect(campo).toBeInvalid()
  expect(campo).toHaveValue('triagem')
})

it.each([
  ['Esc', async () => userEvent.keyboard('{Escape}')],
  ['Cancelar', async () => userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))],
])('%s desiste sem salvar nada', async (_nome, desistir) => {
  const api = simularApi({ 'GET /api/locais': LISTA })
  render(<Locais />)

  const campo = await abrirEdicao('Triagem')
  await userEvent.type(campo, 'Outro nome')
  await desistir()

  expect(screen.queryByLabelText(/Novo nome/)).not.toBeInTheDocument()
  expect(screen.getByRole('cell', { name: 'Triagem' })).toBeInTheDocument()
  expect(api.pedidos.every((p) => p.metodo === 'GET')).toBe(true)
})
