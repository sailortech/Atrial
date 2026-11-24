import { Outlet } from 'react-router-dom'

import { useSessao } from '../sessao.jsx'
import Cabecalho from './Cabecalho.jsx'
import Login from './Login.jsx'

/**
 * "Portaria" das telas da recepção: é a mesma ideia do before_request
 * do Flask. Ninguém logado -> tela de login; logado -> a tela pedida.
 *
 * (Isto é só para a experiência de uso. Quem PROTEGE os dados de
 * verdade é o Flask, que recusa a API sem login. Esconder no React
 * sozinho não protegeria nada, igual ao menu do Flask.)
 */
export default function AreaLogada() {
  const { usuario } = useSessao()

  if (usuario === undefined) {
    return <p className="carregando">Carregando...</p>
  }

  if (usuario === null) {
    return <Login />
  }

  if (usuario.trocar_senha) {
    return (
      <div className="pagina estreita">
        <h2>Crie uma senha sua</h2>
        <p>
          Você entrou com uma senha provisória. Troque-a na página
          <strong> Minha senha</strong> do sistema (versão Flask) e depois volte aqui.
        </p>
      </div>
    )
  }

  return (
    <>
      <Cabecalho />
      <main className="pagina">
        {/* <Outlet /> = "aqui entra a tela da rota escolhida" */}
        <Outlet />
      </main>
    </>
  )
}
