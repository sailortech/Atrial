import { Fragment, useCallback, useEffect, useState } from 'react'

import { api } from '../api.js'
import Mensagem from '../componentes/Mensagem.jsx'
import NovoUsuario from '../componentes/usuarios/NovoUsuario.jsx'
import RedefinirSenha from '../componentes/usuarios/RedefinirSenha.jsx'

/**
 * Usuários (só administração): criar, mudar o papel, desativar e
 * redefinir a senha de quem esqueceu.
 */
export default function Usuarios() {
  const [usuarios, setUsuarios] = useState(null)
  const [erroAoCarregar, setErroAoCarregar] = useState(null)
  const [mensagem, setMensagem] = useState(null)
  // De quem está aberto o "Redefinir senha" (id), ou null
  const [redefinindo, setRedefinindo] = useState(null)

  const carregar = useCallback(async () => {
    try {
      const dados = await api.get('/api/usuarios')
      setUsuarios(dados.usuarios)
      setErroAoCarregar(null)
    } catch (e) {
      setErroAoCarregar(e.message)
    }
  }, [])

  useEffect(() => {
    carregar()
  }, [carregar])

  // Os filhos (formulários) avisam que deu certo por aqui
  function sucesso(texto) {
    setMensagem({ tipo: 'sucesso', texto })
    setRedefinindo(null)
    carregar()
  }

  async function alterar(usuario, acao) {
    if (acao === 'ativo' && usuario.ativo &&
        !window.confirm(`Desativar ${usuario.nome}? A pessoa perde o acesso na hora.`)) {
      return
    }
    try {
      const resposta = await api.post(`/api/usuarios/${usuario.id}/${acao}`)
      sucesso(resposta.mensagem)
    } catch (e) {
      setMensagem({ tipo: 'erro', texto: e.message })
    }
  }

  if (!usuarios) {
    return <p className="carregando">{erroAoCarregar ?? 'Carregando...'}</p>
  }

  return (
    <>
      <h2>Usuários</h2>
      <p className="dica">
        <strong>Recepção</strong> atende a fila e vê o relatório.{' '}
        <strong>Administração</strong> também cadastra locais e usuários.
        Quem sair da clínica deve ser <em>desativado</em>: perde o acesso na hora,
        mas o cadastro continua registrado.
      </p>

      <Mensagem mensagem={mensagem} aoFechar={() => setMensagem(null)} />

      <section>
        <h3>Novo usuário</h3>
        <NovoUsuario aoCriar={sucesso} />
      </section>

      <section>
        <h3>Cadastrados ({usuarios.length})</h3>
        <table>
          <thead>
            <tr><th>Nome</th><th>Usuário</th><th>Papel</th><th>Situação</th><th>Ações</th></tr>
          </thead>
          <tbody>
            {usuarios.map((u) => (
              // Fragment: cada usuário vira ATÉ DUAS linhas (a sua e, se
              // aberta, a do formulário). A key vai no Fragment, que é
              // o elemento de fora da lista.
              <Fragment key={u.id}>
                <tr className={u.ativo ? undefined : 'inativo'}>
                  <td>{u.nome} {u.voce && <small>(você)</small>}</td>
                  <td>{u.login}</td>
                  <td>{u.papel}</td>
                  <td>
                    {u.ativo ? 'Ativo' : 'Desativado'}
                    {u.trocar_senha && <small className="bloco">senha provisória</small>}
                  </td>
                  <td className="acoes">
                    {/* Ninguém mexe no próprio acesso (o servidor também confere) */}
                    {u.voce ? '-' : (
                      <>
                        <button type="button" onClick={() => setRedefinindo(u.id)}
                                disabled={redefinindo === u.id}>
                          Redefinir senha
                        </button>
                        <button type="button" onClick={() => alterar(u, 'admin')}>
                          {u.admin ? 'Tornar recepção' : 'Tornar administração'}
                        </button>
                        <button type="button" onClick={() => alterar(u, 'ativo')}>
                          {u.ativo ? 'Desativar' : 'Reativar'}
                        </button>
                      </>
                    )}
                  </td>
                </tr>

                {redefinindo === u.id && (
                  <tr className="linha-extra">
                    <td colSpan={5}>
                      <RedefinirSenha
                        usuario={u}
                        aoConcluir={sucesso}
                        aoCancelar={() => setRedefinindo(null)}
                      />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </section>
    </>
  )
}
