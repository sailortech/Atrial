import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { api } from '../api.js'
import FormularioPaciente from '../componentes/pacientes/FormularioPaciente.jsx'

export default function EditarPaciente() {
  // useParams lê o pedaço variável do endereço: /pacientes/:id/editar
  const { id } = useParams()
  const navigate = useNavigate()

  const [paciente, setPaciente] = useState(null)
  const [erro, setErro] = useState(null)

  // Busca os dados atuais do paciente para preencher o formulário
  useEffect(() => {
    let ignorar = false // mesma ideia do usePacientes (resposta velha)
    api.get(`/api/pacientes/${id}`)
      .then((dados) => { if (!ignorar) setPaciente(dados.paciente) })
      .catch((e) => { if (!ignorar) setErro(e.message) })
    return () => { ignorar = true }
  }, [id])

  async function salvar(campos) {
    const resposta = await api.put(`/api/pacientes/${id}`, campos)
    navigate('/pacientes', { state: { mensagem: resposta.mensagem } })
  }

  if (erro) {
    return (
      <>
        <p className="mensagem erro">{erro}</p>
        <Link to="/pacientes">Voltar para a lista</Link>
      </>
    )
  }

  if (!paciente) {
    return <p className="carregando">Carregando...</p>
  }

  return (
    <>
      <h2>Editar paciente</h2>
      <p className="dica">Situação: {paciente.status}. Editar os dados não muda o lugar na fila.</p>
      {/* key={paciente.id}: se trocar de paciente, o formulário recomeça do zero */}
      <FormularioPaciente
        key={paciente.id}
        inicial={paciente}
        aoSalvar={salvar}
        textoDoBotao="Salvar alterações"
      />
    </>
  )
}
