import { useCallback, useEffect, useState } from 'react'

import { api } from '../api.js'
import ErroDoCampo from '../componentes/ErroDoCampo.jsx'
import Mensagem from '../componentes/Mensagem.jsx'
import RenomearLocal from '../componentes/locais/RenomearLocal.jsx'
import { marcarErro } from '../formularios.js'

/**
 * Locais de atendimento (só administração): adicionar, renomear,
 * desativar e reativar. Local desativado sai do "Chamar para...", mas
 * continua no histórico e no relatório (por isso não existe "excluir").
 */
export default function Locais() {
  const [locais, setLocais] = useState(null)
  const [erroAoCarregar, setErroAoCarregar] = useState(null)
  const [mensagem, setMensagem] = useState(null)
  // Qual local está com o nome em edição (id), ou null
  const [editando, setEditando] = useState(null)

  // Formulário de novo local (um campo só)
  const [novoNome, setNovoNome] = useState('')
  const [erros, setErros] = useState({})
  const [enviando, setEnviando] = useState(false)

  // Buscar a lista é usado em dois lugares (ao abrir e depois de cada
  // ação), então vira uma função. useCallback mantém a MESMA função
  // entre desenhos, para o useEffect abaixo não rodar à toa.
  const carregar = useCallback(async () => {
    try {
      const dados = await api.get('/api/locais')
      setLocais(dados.locais)
      setErroAoCarregar(null)
    } catch (e) {
      setErroAoCarregar(e.message)
    }
  }, [])

  useEffect(() => {
    carregar()
  }, [carregar])

  async function adicionar(evento) {
    evento.preventDefault()
    setEnviando(true)
    try {
      const resposta = await api.post('/api/locais', { nome: novoNome })
      setMensagem({ tipo: 'sucesso', texto: resposta.mensagem })
      setNovoNome('') // pronto para digitar o próximo
      setErros({})
      await carregar()
    } catch (e) {
      if (e.status === 422) setErros(e.dados.erros)
      else setMensagem({ tipo: 'erro', texto: e.message })
    } finally {
      setEnviando(false)
    }
  }

  // O RenomearLocal avisa aqui quando salvou
  async function renomeado(texto) {
    setMensagem({ tipo: 'sucesso', texto })
    setEditando(null)
    await carregar()
  }

  async function alternar(local) {
    try {
      const resposta = await api.post(`/api/locais/${local.id}/alternar`)
      setMensagem({ tipo: 'sucesso', texto: resposta.mensagem })
    } catch (e) {
      // ex.: 409 "É preciso ter pelo menos um local ativo."
      setMensagem({ tipo: 'erro', texto: e.message })
    }
    await carregar()
  }

  if (!locais) {
    return <p className="carregando">{erroAoCarregar ?? 'Carregando...'}</p>
  }

  // Quantos ativos: o último não pode ser desativado (o servidor também
  // confere; aqui é só para o botão já aparecer desligado, com o motivo)
  const ativos = locais.filter((l) => l.ativo).length

  return (
    <>
      <h2>Locais de atendimento</h2>
      <p className="dica">
        Para onde os pacientes podem ser chamados (aparecem em "Chamar para..." e no
        painel da TV). Um local desativado sai da lista de chamada, mas continua no
        histórico e nos relatórios. Ao renomear, quem já foi chamado continua
        registrado com o nome antigo; o novo nome vale para as próximas chamadas.
      </p>

      <Mensagem mensagem={mensagem} aoFechar={() => setMensagem(null)} />

      <form onSubmit={adicionar} className="linha-de-cadastro" noValidate>
        <div>
          <input
            id="nome"
            value={novoNome}
            onChange={(e) => {
              setNovoNome(e.target.value)
              setErros({})
            }}
            maxLength={50}
            placeholder="Nome do novo local (ex.: Consultório 4)"
            aria-label="Nome do novo local"
            {...marcarErro('nome', erros)}
          />
          <ErroDoCampo campo="nome" erros={erros} />
        </div>
        <button type="submit" className="principal" disabled={enviando}>
          Adicionar
        </button>
      </form>

      <table className="tabela-estreita">
        <thead>
          <tr><th>Local</th><th>Situação</th><th>Ações</th></tr>
        </thead>
        <tbody>
          {locais.map((local) => {
            const ultimoAtivo = local.ativo && ativos === 1
            return (
              <tr key={local.id} className={local.ativo ? undefined : 'inativo'}>
                <td>
                  {/* A mesma célula mostra o nome OU o campo de edição */}
                  {editando === local.id ? (
                    <RenomearLocal
                      local={local}
                      aoConcluir={renomeado}
                      aoCancelar={() => setEditando(null)}
                    />
                  ) : (
                    local.nome
                  )}
                </td>
                <td>{local.ativo ? 'Ativo' : 'Desativado'}</td>
                <td className="acoes">
                  {editando !== local.id && (
                    <button type="button" onClick={() => setEditando(local.id)}>
                      Renomear
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => alternar(local)}
                    disabled={ultimoAtivo}
                    title={ultimoAtivo ? 'É preciso ter pelo menos um local ativo.' : undefined}
                  >
                    {local.ativo ? 'Desativar' : 'Reativar'}
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </>
  )
}
