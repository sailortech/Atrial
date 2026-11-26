import { useState } from 'react'

import { api } from '../../api.js'
import { marcarErro } from '../../formularios.js'
import ErroDoCampo from '../ErroDoCampo.jsx'

const EM_BRANCO = { nome: '', login: '', senha: '', admin: false }

/**
 * Formulário "Novo usuário". Quando dá certo, avisa a página com
 * aoCriar(mensagem); a página mostra a mensagem e recarrega a lista.
 */
export default function NovoUsuario({ aoCriar }) {
  const [campos, setCampos] = useState(EM_BRANCO)
  const [erros, setErros] = useState({})
  const [erroGeral, setErroGeral] = useState(null)
  const [enviando, setEnviando] = useState(false)

  function aoMudar(evento) {
    const { name, value, type, checked } = evento.target
    // Caixa de seleção guarda checked (true/false), não value.
    // Por isso ela é "controlada" com checked={...} lá embaixo.
    const valor = type === 'checkbox' ? checked : value
    setCampos((anteriores) => ({ ...anteriores, [name]: valor }))
    if (erros[name]) setErros((anteriores) => ({ ...anteriores, [name]: undefined }))
  }

  async function aoEnviar(evento) {
    evento.preventDefault()
    setEnviando(true)
    setErroGeral(null)
    try {
      const resposta = await api.post('/api/usuarios', campos)
      setCampos(EM_BRANCO) // pronto para o próximo cadastro
      setErros({})
      aoCriar(resposta.mensagem)
    } catch (e) {
      setErros(e.status === 422 ? e.dados.erros : {})
      setErroGeral(e.message)
    } finally {
      setEnviando(false)
    }
  }

  const propsDoCampo = (nome) => ({
    id: nome,
    name: nome,
    value: campos[nome],
    onChange: aoMudar,
    ...marcarErro(nome, erros),
  })

  return (
    <form onSubmit={aoEnviar} className="formulario formulario-estreito" noValidate>
      {erroGeral && <p className="mensagem erro">{erroGeral}</p>}

      <label htmlFor="nome">Nome</label>
      <input {...propsDoCampo('nome')} />
      <ErroDoCampo campo="nome" erros={erros} />

      <label htmlFor="login">Usuário <small>(para entrar no sistema)</small></label>
      <input {...propsDoCampo('login')} autoComplete="off" placeholder="ex.: maria.souza" />
      <ErroDoCampo campo="login" erros={erros} />

      <label htmlFor="senha">Senha inicial <small>(mínimo 8 caracteres)</small></label>
      {/* new-password: o navegador não preenche com a SUA senha */}
      <input {...propsDoCampo('senha')} type="password" autoComplete="new-password" />
      <ErroDoCampo campo="senha" erros={erros} />

      <label className="caixa">
        <input type="checkbox" name="admin" checked={campos.admin} onChange={aoMudar} />
        Administração <small>(pode cadastrar locais e usuários)</small>
      </label>

      <button type="submit" className="principal" disabled={enviando}>
        {enviando ? 'Criando...' : 'Criar usuário'}
      </button>
    </form>
  )
}
