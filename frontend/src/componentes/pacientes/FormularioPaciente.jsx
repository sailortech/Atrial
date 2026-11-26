import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../../api.js'
import { marcarErro, mascaraCpf } from '../../formularios.js'
import ErroDoCampo from '../ErroDoCampo.jsx'

/**
 * Formulário de paciente, usado no CADASTRO e na EDIÇÃO (igual ao
 * _campos_paciente.html do Flask). Quem usa só diz:
 *   - inicial: os valores de partida (em branco ou os do banco)
 *   - aoSalvar(campos): o que fazer com os dados (POST ou PUT)
 *   - textoDoBotao
 *
 * Quem VALIDA de verdade é o Flask. Se ele recusar (422), mostramos
 * cada erro embaixo do campo correspondente.
 */
export default function FormularioPaciente({ inicial, aoSalvar, textoDoBotao }) {
  // UM objeto de estado para todos os campos, em vez de um useState
  // para cada (seriam 7!). Cada campo lê campos.nome, campos.cpf...
  const [campos, setCampos] = useState(inicial)
  const [erros, setErros] = useState({}) // ex.: { cpf: "CPF inválido..." }
  const [erroGeral, setErroGeral] = useState(null)
  const [enviando, setEnviando] = useState(false)
  const [prioridades, setPrioridades] = useState([inicial.prioridade])

  // A lista de prioridades vem do servidor (ele é quem decide o que vale)
  useEffect(() => {
    api.get('/api/pacientes/prioridades')
      .then((dados) => setPrioridades(dados.prioridades))
      .catch(() => {}) // sem a lista, fica só a opção atual
  }, [])

  /**
   * Um único "onChange" para todos os campos: usa o atributo name
   * do campo para saber qual chave do objeto mudar.
   */
  function aoMudar(evento) {
    const { name, value } = evento.target
    const valor = name === 'cpf' ? mascaraCpf(value) : value

    // { ...anteriores } copia o objeto; [name]: valor troca só aquela
    // chave. (Nunca altere o estado direto, ex.: campos.nome = 'x': o
    // React não perceberia a mudança e a tela não atualizaria.)
    setCampos((anteriores) => ({ ...anteriores, [name]: valor }))

    // Mexeu no campo? O erro dele some (a pessoa está corrigindo)
    if (erros[name]) {
      setErros((anteriores) => ({ ...anteriores, [name]: undefined }))
    }
  }

  async function aoEnviar(evento) {
    evento.preventDefault()
    setEnviando(true)
    setErroGeral(null)
    try {
      await aoSalvar(campos)
      // Deu certo: quem chamou já mudou de tela
    } catch (e) {
      setErros(e.status === 422 ? e.dados.erros : {})
      setErroGeral(e.message)
      setEnviando(false)
    }
  }

  // As "props" comuns de cada campo: name, value, onChange e, se houver
  // erro, a marcação de acessibilidade (o leitor de tela lê a mensagem)
  function propsDoCampo(nome) {
    return {
      id: nome,
      name: nome,
      value: campos[nome],
      onChange: aoMudar,
      ...marcarErro(nome, erros),
    }
  }

  return (
    <form onSubmit={aoEnviar} className="formulario formulario-paciente" noValidate>
      {erroGeral && <p className="mensagem erro">{erroGeral}</p>}

      <label htmlFor="nome">Nome completo</label>
      <input {...propsDoCampo('nome')} autoFocus />
      <ErroDoCampo campo="nome" erros={erros} />

      <div className="lado-a-lado">
        <div>
          <label htmlFor="nascimento">Data de nascimento</label>
          <input {...propsDoCampo('nascimento')} type="date" />
          <ErroDoCampo campo="nascimento" erros={erros} />
        </div>
        <div>
          <label htmlFor="cpf">CPF</label>
          <input {...propsDoCampo('cpf')} inputMode="numeric" placeholder="000.000.000-00" />
          <ErroDoCampo campo="cpf" erros={erros} />
        </div>
      </div>

      <label htmlFor="prioridade">Prioridade</label>
      <select {...propsDoCampo('prioridade')}>
        {prioridades.map((p) => <option key={p} value={p}>{p}</option>)}
      </select>
      <ErroDoCampo campo="prioridade" erros={erros} />

      <div className="lado-a-lado">
        <div>
          <label htmlFor="telefone">Telefone <small>(opcional)</small></label>
          <input {...propsDoCampo('telefone')} type="tel" />
        </div>
        <div>
          <label htmlFor="email">E-mail <small>(opcional)</small></label>
          <input {...propsDoCampo('email')} type="email" />
        </div>
      </div>

      <label htmlFor="observacoes">Observações <small>(opcional)</small></label>
      <textarea {...propsDoCampo('observacoes')} rows={3} />

      <div className="botoes">
        <button type="submit" className="principal" disabled={enviando}>
          {enviando ? 'Salvando...' : textoDoBotao}
        </button>
        <Link to="/pacientes">Cancelar</Link>
      </div>
    </form>
  )
}
