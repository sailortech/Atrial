import { useEffect, useRef, useState } from 'react'

import { api } from '../../api.js'
import { marcarErro } from '../../formularios.js'
import ErroDoCampo from '../ErroDoCampo.jsx'

/**
 * Edição do nome ali mesmo, na célula da tabela.
 * Enter salva; Esc (ou Cancelar) desiste.
 */
export default function RenomearLocal({ local, aoConcluir, aoCancelar }) {
  const [nome, setNome] = useState(local.nome)
  // A chave do erro é "novo-nome" (e não "nome"): o formulário de
  // adicionar, na mesma página, já usa o id "erro-nome"
  const [erros, setErros] = useState({})
  const [enviando, setEnviando] = useState(false)

  // useRef = uma "alça" para o <input> de verdade da página, para
  // chamar coisas do próprio navegador nele (focus, select)
  const campo = useRef(null)

  // Ao abrir: foco no campo e o texto todo selecionado, então digitar
  // SUBSTITUI o nome. ([] = só uma vez, quando o campo aparece)
  useEffect(() => {
    campo.current.focus()
    campo.current.select()
  }, [])

  async function aoEnviar(evento) {
    evento.preventDefault()
    setEnviando(true)
    try {
      const resposta = await api.put(`/api/locais/${local.id}`, { nome })
      aoConcluir(resposta.mensagem)
    } catch (e) {
      setErros({ 'novo-nome': e.dados?.erros?.nome ?? e.message })
      setEnviando(false)
    }
  }

  return (
    <form onSubmit={aoEnviar} className="renomear" noValidate>
      <div className="linha-de-cadastro">
        <div>
          <input
            ref={campo}
            value={nome}
            onChange={(e) => { setNome(e.target.value); setErros({}) }}
            // Esc desiste, como em quase todo programa
            onKeyDown={(e) => e.key === 'Escape' && aoCancelar()}
            maxLength={50}
            aria-label={`Novo nome para ${local.nome}`}
            {...marcarErro('novo-nome', erros)}
          />
          <ErroDoCampo campo="novo-nome" erros={erros} />
        </div>
        <button type="submit" className="principal" disabled={enviando}>Salvar</button>
        <button type="button" onClick={aoCancelar}>Cancelar</button>
      </div>
    </form>
  )
}
