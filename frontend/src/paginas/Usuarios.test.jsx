// Tela de Usuários (administração): criar, mudar papel, desativar,
// redefinir senha. Com a API simulada.
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

import { simularApi } from '../testes/simularApi.js'
import Usuarios from './Usuarios.jsx'

function usuario(id, nome, login, extra = {}) {
  return {
    id, nome, login, admin: false, ativo: true, trocar_senha: false,
    papel: 'Recepção', voce: false, ...extra,
  }
}

const LISTA = {
  usuarios: [
    usuario(1, 'Bia Admin', 'bia', { admin: true, papel: 'Administração', voce: true }),
    usuario(2, 'Ana Recepção', 'ana'),
    usuario(3, 'Caio Antigo', 'caio', { ativo: false }),
  ],
}

function api(rotas = {}) {
  return simularApi({ 'GET /api/usuarios': LISTA, ...rotas })
}

const linhaDe = (login) => screen.getByRole('cell', { name: login }).closest('tr')
const posts = (fetchFalso) => fetchFalso.pedidos.filter((p) => p.metodo === 'POST')

// ---------- Lista ----------

it('na própria linha: "(você)" e nenhum botão', async () => {
  api()
  render(<Usuarios />)

  await screen.findByRole('cell', { name: 'bia' })
  const minha = linhaDe('bia')

  expect(minha).toHaveTextContent('(você)')
  expect(within(minha).queryAllByRole('button')).toHaveLength(0)
  expect(within(linhaDe('ana')).getAllByRole('button')).toHaveLength(3)
})

it('desativado aparece apagado, com "Reativar"', async () => {
  api()
  render(<Usuarios />)

  await screen.findByRole('cell', { name: 'caio' })

  expect(linhaDe('caio')).toHaveClass('inativo')
  expect(within(linhaDe('caio')).getByRole('button', { name: 'Reativar' })).toBeInTheDocument()
})

// ---------- Criar ----------

it('criar: manda os campos (com a caixa de administração) e limpa o formulário', async () => {
  const fetchFalso = api({
    'POST /api/usuarios': (corpo) => [201, { mensagem: `Usuário '${corpo.login}' criado (Administração).` }],
  })
  render(<Usuarios />)

  await userEvent.type(await screen.findByLabelText('Nome'), 'Carla Dias')
  await userEvent.type(screen.getByLabelText(/^Usuário/), 'carla')
  await userEvent.type(screen.getByLabelText(/^Senha inicial/), 'senha-boa-123')
  await userEvent.click(screen.getByRole('checkbox', { name: /Administração/ }))
  await userEvent.click(screen.getByRole('button', { name: 'Criar usuário' }))

  expect(await screen.findByRole('status')).toHaveTextContent("Usuário 'carla' criado")
  expect(posts(fetchFalso)[0].corpo).toEqual({
    nome: 'Carla Dias', login: 'carla', senha: 'senha-boa-123', admin: true,
  })
  // Pronto para o próximo cadastro
  expect(screen.getByLabelText('Nome')).toHaveValue('')
  expect(screen.getByRole('checkbox', { name: /Administração/ })).not.toBeChecked()
})

it('criar com erros: cada mensagem embaixo do seu campo, e o que foi digitado fica', async () => {
  api({
    'POST /api/usuarios': [422, {
      erro: 'Confira os campos destacados.',
      erros: { login: "Já existe o usuário 'ana'.", senha: 'A senha precisa ter pelo menos 8 caracteres.' },
    }],
  })
  render(<Usuarios />)

  await userEvent.type(await screen.findByLabelText('Nome'), 'Outra Ana')
  await userEvent.type(screen.getByLabelText(/^Usuário/), 'ana')
  await userEvent.click(screen.getByRole('button', { name: 'Criar usuário' }))

  const login = screen.getByLabelText(/^Usuário/)
  expect(await screen.findByText("Já existe o usuário 'ana'.")).toBeInTheDocument()
  expect(login).toBeInvalid()
  expect(login).toHaveValue('ana')
  expect(screen.getByLabelText(/^Senha inicial/)).toBeInvalid()
  expect(screen.getByLabelText('Nome')).toBeValid()
})

// ---------- Papel e situação ----------

it('"Tornar administração" manda o pedido e recarrega a lista', async () => {
  const fetchFalso = api({
    'POST /api/usuarios/2/admin': { mensagem: "Usuário 'ana' agora é da administração." },
  })
  render(<Usuarios />)

  await screen.findByRole('cell', { name: 'ana' })
  await userEvent.click(within(linhaDe('ana')).getByRole('button', { name: 'Tornar administração' }))

  expect(await screen.findByRole('status')).toHaveTextContent('agora é da administração')
  await waitFor(() =>
    expect(fetchFalso.pedidos.filter((p) => p.metodo === 'GET')).toHaveLength(2))
})

it('desativar pergunta antes (com o nome); reativar não pergunta', async () => {
  const fetchFalso = api({
    'POST /api/usuarios/2/ativo': { mensagem: "Usuário 'ana' desativado." },
    'POST /api/usuarios/3/ativo': { mensagem: "Usuário 'caio' reativado." },
  })
  const confirmar = vi.spyOn(window, 'confirm').mockReturnValue(false)
  render(<Usuarios />)

  await screen.findByRole('cell', { name: 'ana' })
  await userEvent.click(within(linhaDe('ana')).getByRole('button', { name: 'Desativar' }))

  expect(confirmar).toHaveBeenCalledWith(expect.stringContaining('Desativar Ana Recepção?'))
  expect(posts(fetchFalso)).toHaveLength(0) // cancelou: nada foi mandado

  await userEvent.click(within(linhaDe('caio')).getByRole('button', { name: 'Reativar' }))

  expect(confirmar).toHaveBeenCalledOnce() // reativar não perguntou
  expect(await screen.findByRole('status')).toHaveTextContent("'caio' reativado")
})

// ---------- Redefinir senha ----------

it('redefinir senha abre um formulário embaixo da pessoa, um de cada vez', async () => {
  api()
  render(<Usuarios />)

  await screen.findByRole('cell', { name: 'ana' })
  await userEvent.click(within(linhaDe('ana')).getByRole('button', { name: 'Redefinir senha' }))

  expect(screen.getByText(/Senha provisória para/)).toHaveTextContent('ana')
  // A linha do formulário vem logo depois da linha da Ana
  expect(linhaDe('ana').nextElementSibling).toHaveClass('linha-extra')

  await userEvent.click(within(linhaDe('caio')).getByRole('button', { name: 'Redefinir senha' }))

  expect(screen.getAllByText(/Senha provisória para/)).toHaveLength(1)
  expect(screen.getByText(/Senha provisória para/)).toHaveTextContent('caio')
})

it('redefinir: senha curta mostra o erro; senha boa fecha o formulário', async () => {
  let tentativa = 0
  const fetchFalso = api({
    'POST /api/usuarios/2/senha': () => (++tentativa === 1
      ? [422, { erro: 'Confira os campos destacados.', erros: { nova: 'A senha precisa ter pelo menos 8 caracteres.' } }]
      : { mensagem: "Senha provisória definida para 'ana'." }),
  })
  render(<Usuarios />)

  await screen.findByRole('cell', { name: 'ana' })
  await userEvent.click(within(linhaDe('ana')).getByRole('button', { name: 'Redefinir senha' }))
  const campo = screen.getByLabelText(/Senha provisória para/)

  await userEvent.type(campo, 'curta')
  await userEvent.click(screen.getByRole('button', { name: 'Definir' }))
  expect(await screen.findByText('A senha precisa ter pelo menos 8 caracteres.')).toBeInTheDocument()
  expect(campo).toBeInvalid()

  await userEvent.clear(campo)
  await userEvent.type(campo, 'provisoria-1')
  await userEvent.click(screen.getByRole('button', { name: 'Definir' }))

  expect(await screen.findByRole('status')).toHaveTextContent("Senha provisória definida para 'ana'.")
  expect(screen.queryByText(/Senha provisória para/)).not.toBeInTheDocument()
  expect(posts(fetchFalso).map((p) => p.corpo)).toEqual([{ nova: 'curta' }, { nova: 'provisoria-1' }])
})

it('redefinir: "Cancelar" fecha sem mandar nada', async () => {
  const fetchFalso = api()
  render(<Usuarios />)

  await screen.findByRole('cell', { name: 'ana' })
  await userEvent.click(within(linhaDe('ana')).getByRole('button', { name: 'Redefinir senha' }))
  await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

  expect(screen.queryByText(/Senha provisória para/)).not.toBeInTheDocument()
  expect(posts(fetchFalso)).toHaveLength(0)
})
