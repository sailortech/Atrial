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
  const [erroAoExcluir, setErroAoExcluir] = useState(null)

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

  async function excluir() {
    // confirm() pausa tudo até a pessoa responder: OK = true, Cancelar = false
    const certeza = window.confirm(
      `Excluir ${paciente.nome}?

O paciente some da fila, do histórico e do relatório. Não dá para desfazer.`,
    )
    if (!certeza) return

    try {
      const resposta = await api.delete(`/api/pacientes/${id}`)
      // replace: true = esta página sai do histórico do navegador. Sem
      // isso, o botão "Voltar" traria de volta um paciente que não existe.
      navigate('/pacientes', { replace: true, state: { mensagem: resposta.mensagem } })
    } catch (e) {
      setErroAoExcluir(e.message)
    }
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
      <p className="dica">
        Situação: {paciente.status}.
        {/* && = "só mostra se": a frase só faz sentido para quem está na fila */}
        {paciente.status === 'Aguardando' && ' Editar os dados não muda o lugar na fila.'}
      </p>
      {/* key={paciente.id}: se trocar de paciente, o formulário recomeça do zero */}
      <FormularioPaciente
        key={paciente.id}
        inicial={paciente}
        aoSalvar={salvar}
        textoDoBotao="Salvar alterações"
      />

      {/* Separado do formulário e com outra cor: é a única ação sem volta */}
      <section className="zona-perigo">
        <h3>Excluir paciente</h3>
        <p>
          Use só para cadastros feitos por engano. Para quem foi embora sem ser
          atendido, prefira <strong>Não compareceu</strong>: assim o atendimento
          continua contando no relatório.
        </p>
        {erroAoExcluir && <p className="mensagem erro">{erroAoExcluir}</p>}
        <button type="button" className="perigo" onClick={excluir}>
          Excluir {paciente.nome}
        </button>
      </section>
    </>
  )
}
