import { useState } from 'react'

import { api } from '../../api.js'
import { marcarErro } from '../../formularios.js'
import ErroDoCampo from '../ErroDoCampo.jsx'

/**
 * Formulário pequeno, aberto DENTRO da tabela, logo abaixo da pessoa:
 * a administração define uma senha PROVISÓRIA para quem esqueceu a sua.
 */
export default function RedefinirSenha({ usuario, aoConcluir, aoCancelar }) {
  const [nova, setNova] = useState('')
  const [erros, setErros] = useState({})
  const [enviando, setEnviando] = useState(false)

  async function aoEnviar(evento) {
    evento.preventDefault()
    setEnviando(true)
    try {
      const resposta = await api.post(`/api/usuarios/${usuario.id}/senha`, { nova })
      aoConcluir(resposta.mensagem)
    } catch (e) {
      setErros(e.status === 422 ? e.dados.erros : { nova: e.message })
      setEnviando(false)
    }
  }

  // id com o número do usuário: se houvesse dois destes abertos,
  // os ids não se repetiriam na página
  const idCampo = `nova-senha-${usuario.id}`

  return (
    <form onSubmit={aoEnviar} className="redefinir-senha" noValidate>
      <label htmlFor={idCampo}>
        Senha provisória para <strong>{usuario.login}</strong>{' '}
        <small>(mínimo 8 caracteres; no próximo acesso a pessoa cria a dela)</small>
      </label>
      <div className="linha-de-cadastro">
        <div>
          <input
            id={idCampo}
            type="password"
            value={nova}
            onChange={(e) => { setNova(e.target.value); setErros({}) }}
            autoComplete="new-password"
            autoFocus
            {...marcarErro('nova', erros)}
          />
          <ErroDoCampo campo="nova" erros={erros} />
        </div>
        <button type="submit" className="principal" disabled={enviando}>Definir</button>
        <button type="button" onClick={aoCancelar}>Cancelar</button>
      </div>
    </form>
  )
}
