import { Outlet } from 'react-router-dom'

import { useSessao } from '../sessao.jsx'
import Cabecalho from './Cabecalho.jsx'
import Login from './Login.jsx'
import MinhaSenha from '../paginas/MinhaSenha.jsx'

/**
 * "Portaria" das telas da recepção: é a mesma ideia do before_request
 * do Flask. Ninguém logado -> tela de login; logado -> a tela pedida.
 *
 * (Isto é só para a experiência de uso. Quem PROTEGE os dados de
 * verdade é o Flask, que recusa a API sem login. Esconder no React
 * sozinho não protegeria nada, igual ao menu do Flask.)
 */
export default function AreaLogada() {
  const { usuario, sair } = useSessao()

  if (usuario === undefined) {
    return <p className="carregando">Carregando...</p>
  }

  if (usuario === null) {
    return <Login />
  }

  // Senha provisória: qualquer endereço mostra só a troca de senha
  // (o Flask também recusa o resto da API com 403 até ela ser trocada)
  if (usuario.trocar_senha) {
    return (
      <main className="pagina estreita">
        <MinhaSenha />
        <p className="dica">
          Não é você? <button type="button" className="link" onClick={sair}>Sair</button>
        </p>
      </main>
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
