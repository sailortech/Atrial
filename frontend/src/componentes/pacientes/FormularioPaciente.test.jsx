import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'

import { ErroDaApi } from '../../api.js'
import { simularApi } from '../../testes/simularApi.js'
import FormularioPaciente from './FormularioPaciente.jsx'

const EM_BRANCO = {
  nome: '', nascimento: '', cpf: '', prioridade: 'Normal',
  telefone: '', email: '', observacoes: '',
}

beforeEach(() => {
  // O formulário pede a lista de prioridades ao abrir
  simularApi({ 'GET /api/pacientes/prioridades': { prioridades: ['Normal', 'Preferencial', 'Urgente'] } })
})

function desenhar(aoSalvar = vi.fn()) {
  // MemoryRouter: o formulário tem um <Link>, que precisa de um roteador
  render(
    <MemoryRouter>
      <FormularioPaciente inicial={EM_BRANCO} aoSalvar={aoSalvar} textoDoBotao="Cadastrar" />
    </MemoryRouter>,
  )
  return aoSalvar
}

it('as prioridades vêm do servidor', async () => {
  desenhar()

  // findBy... ESPERA aparecer (a resposta do "servidor" chega depois)
  expect(await screen.findByRole('option', { name: 'Urgente' })).toBeInTheDocument()
  expect(screen.getAllByRole('option')).toHaveLength(3)
})

it('põe a máscara no CPF enquanto digita', async () => {
  desenhar()

  const cpf = screen.getByLabelText('CPF')
  await userEvent.type(cpf, '52998224725')

  expect(cpf).toHaveValue('529.982.247-25')
})

it('manda o que foi digitado para aoSalvar', async () => {
  const aoSalvar = desenhar()

  await userEvent.type(screen.getByLabelText('Nome completo'), 'Joana Lima')
  await userEvent.type(screen.getByLabelText('CPF'), '39053344705')
  await userEvent.selectOptions(await screen.findByLabelText('Prioridade'), 'Urgente')
  await userEvent.click(screen.getByRole('button', { name: 'Cadastrar' }))

  expect(aoSalvar).toHaveBeenCalledWith(expect.objectContaining({
    nome: 'Joana Lima', cpf: '390.533.447-05', prioridade: 'Urgente',
  }))
})

it('erro 422: cada mensagem embaixo do seu campo, e some ao corrigir', async () => {
  const aoSalvar = vi.fn().mockRejectedValue(
    new ErroDaApi(422, 'Confira os campos destacados.', {
      erros: { cpf: 'CPF inválido. Confira os números digitados.' },
    }),
  )
  desenhar(aoSalvar)

  await userEvent.click(screen.getByRole('button', { name: 'Cadastrar' }))

  const cpf = screen.getByLabelText('CPF')
  expect(await screen.findByText('Confira os campos destacados.')).toBeInTheDocument()
  expect(cpf).toBeInvalid() // aria-invalid
  expect(cpf).toHaveAccessibleDescription('CPF inválido. Confira os números digitados.')
  expect(screen.getByLabelText('Nome completo')).toBeValid() // só o CPF foi recusado

  await userEvent.type(cpf, '5')

  expect(cpf).toBeValid()
  expect(screen.queryByText(/CPF inválido/)).not.toBeInTheDocument()
})

it('enquanto salva, o botão fica desligado (sem clique duplo)', async () => {
  // Uma promessa que nunca termina: o "servidor" ainda está pensando
  desenhar(() => new Promise(() => {}))

  await userEvent.click(screen.getByRole('button', { name: 'Cadastrar' }))

  expect(screen.getByRole('button', { name: 'Salvando...' })).toBeDisabled()
})
