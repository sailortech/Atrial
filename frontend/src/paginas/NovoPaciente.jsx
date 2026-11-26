import { useNavigate } from 'react-router-dom'

import { api } from '../api.js'
import FormularioPaciente from '../componentes/pacientes/FormularioPaciente.jsx'

// Campos vazios, para o cadastro de um paciente novo
const PACIENTE_EM_BRANCO = {
  nome: '',
  nascimento: '',
  cpf: '',
  prioridade: 'Normal',
  telefone: '',
  email: '',
  observacoes: '',
}

export default function NovoPaciente() {
  // useNavigate = o "redirect" do React: troca de tela por código
  const navigate = useNavigate()

  async function salvar(campos) {
    const resposta = await api.post('/api/pacientes', campos)
    // "state" viaja junto com a navegação: a tela de pacientes lê a
    // mensagem e mostra (é o flash() do Flask, versão React)
    navigate('/pacientes', { state: { mensagem: resposta.mensagem } })
  }

  return (
    <>
      <h2>Cadastrar paciente</h2>
      <FormularioPaciente
        inicial={PACIENTE_EM_BRANCO}
        aoSalvar={salvar}
        textoDoBotao="Cadastrar e pôr na fila"
      />
    </>
  )
}
