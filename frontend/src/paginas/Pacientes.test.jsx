// A tela principal da recepção: listas, chamar, atender, buscar.
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { expect, it, vi } from 'vitest'

import { SessaoProvider } from '../sessao.jsx'
import { simularApi } from '../testes/simularApi.js'
import Pacientes from './Pacientes.jsx'

const ANA = { nome: 'Ana Recepção', login: 'ana', admin: false, trocar_senha: false }

// Um paciente como a API manda (só o que a tela usa)
function paciente(id, nome, extra = {}) {
  return {
    id, nome, cpf: '529.982.247-25', telefone: '', observacoes: '',
    prioridade: 'Normal', status: 'Aguardando', local: null, posicao: null,
    chegada: '08:00', chamado_em: '-', esperando_ha: '10 min', esperou: '-',
    duracao: '-', encerrado_em: null, foi_rechamado: false, ultima_chamada: '-',
    ...extra,
  }
}

const LISTAS = {
  em_atendimento: [
    paciente(7, 'Carla Dias', { status: 'Em atendimento', local: 'Triagem', chamado_em: '08:30' }),
  ],
  fila: [
    paciente(1, 'Bruno Lima', { prioridade: 'Urgente', posicao: 1 }),
    paciente(2, 'Davi Souza', { posicao: 2 }),
  ],
  historico: [
    paciente(9, 'Eva Rocha', { status: 'Não compareceu', encerrado_em: '27/11 07:50' }),
  ],
  total_na_fila: 2,
  locais: ['Consultório 1', 'Triagem'],
  ultimo_local: null,
}

/** A API com a sessão (logado como Ana) e as listas, mais o que o teste pedir. */
function api(rotas = {}, listas = LISTAS) {
  return simularApi({
    'GET /api/sessao': { usuario: ANA, csrf: 'codigo' },
    'GET /api/pacientes': listas,
    ...rotas,
  })
}

/** A página, dentro da sessão e de um roteador (como no App de verdade). */
function desenhar(estado) {
  render(
    <SessaoProvider>
      <MemoryRouter initialEntries={[{ pathname: '/pacientes', state: estado }]}>
        <Pacientes />
      </MemoryRouter>
    </SessaoProvider>,
  )
}

const secao = (titulo) => screen.getByRole('heading', { name: titulo }).closest('section')
const pedidosDe = (fetchFalso, metodo, caminho) =>
  fetchFalso.pedidos.filter((p) => p.metodo === metodo && p.caminho.startsWith(caminho))

// ---------- Listas ----------

it('mostra as três listas que a API mandou', async () => {
  api()
  desenhar()

  expect(await screen.findByRole('heading', { name: 'Fila de espera (2)' })).toBeInTheDocument()

  const fila = within(secao('Fila de espera (2)')).getAllByRole('row').slice(1)
  expect(fila.map((linha) => linha.cells[0].textContent + ' ' + linha.cells[1].textContent))
    .toEqual(['1º Bruno Limaeditar', '2º Davi Souzaeditar'])

  expect(within(secao('Em atendimento (1)')).getByText('Carla Dias')).toBeInTheDocument()
  expect(within(secao('Histórico de atendimentos (1)')).getByText('Não compareceu')).toBeInTheDocument()
})

it('cada paciente tem o link de edição certo', async () => {
  api()
  desenhar()

  const linha = (await screen.findByText('Davi Souza')).closest('tr')

  expect(within(linha).getByRole('link', { name: 'editar' })).toHaveAttribute('href', '/pacientes/2/editar')
})

// ---------- Chamar próximo ----------

it('o botão só liga depois de escolher o local', async () => {
  api()
  desenhar()

  const botao = await screen.findByRole('button', { name: 'Chamar próximo' })
  expect(botao).toBeDisabled()

  await userEvent.selectOptions(screen.getByLabelText('Chamar para'), 'Triagem')

  expect(botao).toBeEnabled()
})

it('o último local usado já vem escolhido', async () => {
  api({}, { ...LISTAS, ultimo_local: 'Consultório 1' })
  desenhar()

  expect(await screen.findByLabelText('Chamar para')).toHaveValue('Consultório 1')
  expect(screen.getByRole('button', { name: 'Chamar próximo' })).toBeEnabled()
})

it('fila vazia: não dá para chamar', async () => {
  api({}, { ...LISTAS, fila: [], total_na_fila: 0, ultimo_local: 'Triagem' })
  desenhar()

  expect(await screen.findByRole('button', { name: 'Chamar próximo' })).toBeDisabled()
  expect(screen.getByText('A fila está vazia.')).toBeInTheDocument()
})

it('chamar: manda o local, mostra a mensagem e atualiza as listas', async () => {
  const fetchFalso = api({
    'POST /api/pacientes/chamar-proximo': (corpo) => ({
      mensagem: `Chamando Bruno Lima (Urgente) para ${corpo.local}.`,
    }),
  })
  desenhar()

  await userEvent.selectOptions(await screen.findByLabelText('Chamar para'), 'Triagem')
  await userEvent.click(screen.getByRole('button', { name: 'Chamar próximo' }))

  expect(await screen.findByRole('status')).toHaveTextContent('Chamando Bruno Lima (Urgente) para Triagem.')
  expect(pedidosDe(fetchFalso, 'POST', '/api/pacientes/chamar-proximo')[0].corpo).toEqual({ local: 'Triagem' })
  // Depois da ação, a lista é pedida de novo (para mostrar quem foi chamado)
  await waitFor(() => expect(pedidosDe(fetchFalso, 'GET', '/api/pacientes')).toHaveLength(2))
})

it('erro do servidor (409) vira mensagem vermelha', async () => {
  api({
    'POST /api/pacientes/chamar-proximo': [409, { erro: 'Não há pacientes aguardando na fila.' }],
  })
  desenhar()

  await userEvent.selectOptions(await screen.findByLabelText('Chamar para'), 'Triagem')
  await userEvent.click(screen.getByRole('button', { name: 'Chamar próximo' }))

  const mensagem = await screen.findByRole('status')
  expect(mensagem).toHaveClass('erro')
  expect(mensagem).toHaveTextContent('Não há pacientes aguardando na fila.')
})

// ---------- Atendimento ----------

it('concluir manda o pedido para o paciente certo', async () => {
  const fetchFalso = api({
    'POST /api/pacientes/7/concluir': { mensagem: 'Atendimento de Carla Dias concluído.' },
  })
  desenhar()

  await userEvent.click(await screen.findByRole('button', { name: 'Concluir' }))

  expect(await screen.findByRole('status')).toHaveTextContent('Atendimento de Carla Dias concluído.')
  expect(pedidosDe(fetchFalso, 'POST', '/api/pacientes/7/concluir')).toHaveLength(1)
})

it('"não compareceu" pergunta antes, e cancelar não faz nada', async () => {
  const fetchFalso = api({
    'POST /api/pacientes/7/nao-compareceu': { mensagem: 'Carla Dias marcada como não compareceu.' },
  })
  // vi.spyOn troca o confirm do navegador: o teste "responde" a pergunta
  const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(false)
  desenhar()

  const botao = await screen.findByRole('button', { name: 'Não compareceu' })
  await userEvent.click(botao)
  expect(confirmar).toHaveBeenCalledOnce()
  expect(pedidosDe(fetchFalso, 'POST', '/api/pacientes/7/nao-compareceu')).toHaveLength(0)

  confirmar.mockReturnValue(true)
  await userEvent.click(botao)
  expect(await screen.findByRole('status')).toHaveTextContent('não compareceu')
  expect(pedidosDe(fetchFalso, 'POST', '/api/pacientes/7/nao-compareceu')).toHaveLength(1)
})

it('mostra quando o paciente foi chamado de novo', async () => {
  api({}, {
    ...LISTAS,
    em_atendimento: [paciente(7, 'Carla Dias', {
      status: 'Em atendimento', foi_rechamado: true, ultima_chamada: '08:45',
    })],
  })
  desenhar()

  expect(await screen.findByText('chamado de novo às 08:45')).toBeInTheDocument()
})

// ---------- Busca ----------

it('a busca espera parar de digitar antes de pedir ao servidor', async () => {
  const fetchFalso = api({
    'GET /api/pacientes': (_corpo, caminho) => (
      caminho.endsWith('q=ana')
        ? { ...LISTAS, em_atendimento: [], historico: [], fila: [LISTAS.fila[0]] }
        : LISTAS
    ),
  })
  desenhar()

  await userEvent.type(await screen.findByPlaceholderText('Buscar por nome ou CPF'), 'ana')

  expect(await screen.findByText(/1 encontrado\(s\) para/)).toBeInTheDocument()
  const buscas = pedidosDe(fetchFalso, 'GET', '/api/pacientes').map((p) => p.caminho)
  // Uma busca só, com a palavra inteira: nada de "a", "an", "ana"
  expect(buscas).toEqual(['/api/pacientes?q=', '/api/pacientes?q=ana'])
})

it('"Limpar busca" volta para a lista completa', async () => {
  api()
  desenhar()

  const campo = await screen.findByPlaceholderText('Buscar por nome ou CPF')
  await userEvent.type(campo, 'ana')
  await userEvent.click(await screen.findByRole('button', { name: 'Limpar busca' }))

  expect(campo).toHaveValue('')
  await waitFor(() => expect(screen.queryByText(/encontrado\(s\)/)).not.toBeInTheDocument())
})

// ---------- Mensagem vinda de outra tela ----------

it('mostra a mensagem que veio do cadastro (state da navegação)', async () => {
  api()
  desenhar({ mensagem: 'Paciente Joana Lima cadastrado com sucesso!' })

  expect(await screen.findByRole('status')).toHaveTextContent('Paciente Joana Lima cadastrado com sucesso!')

  await userEvent.click(screen.getByRole('button', { name: 'Fechar mensagem' }))
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
})

// ---------- Sessão ----------

it('sessão vencida (401): pergunta de novo quem está logado', async () => {
  const fetchFalso = api({ 'GET /api/pacientes': [401, { erro: 'Faça login para continuar.' }] })
  desenhar()

  // A tela pede /api/sessao ao abrir e DE NOVO quando a lista dá 401;
  // é assim que a AreaLogada descobre que precisa mostrar o login
  await waitFor(() => expect(pedidosDe(fetchFalso, 'GET', '/api/sessao')).toHaveLength(2))
})
