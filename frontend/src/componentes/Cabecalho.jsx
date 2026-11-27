import { Link, NavLink } from 'react-router-dom'

import { useSessao } from '../sessao.jsx'
import SeletorDeTema from './SeletorDeTema.jsx'

// Barra do topo das telas da recepção
export default function Cabecalho() {
  const { usuario, sair } = useSessao()

  return (
    <header className="cabecalho">
      <span className="marca">Atrial</span>

      <nav>
        {/* NavLink = link que sabe se está na página atual
            (ganha a classe "active" sozinho) */}
        {/* end: só fica "ativo" em /pacientes exato, não em /pacientes/novo */}
        <NavLink to="/pacientes" end>Pacientes</NavLink>
        <NavLink to="/pacientes/novo">Cadastrar</NavLink>
        <NavLink to="/relatorio">Relatório</NavLink>
        {/* && = só aparece para quem é da administração */}
        {usuario.admin && (
          // <> </> agrupa os dois links sem criar um elemento a mais
          <>
            <NavLink to="/locais">Locais</NavLink>
            <NavLink to="/usuarios">Usuários</NavLink>
          </>
        )}
        {/* target="_blank": abre a TV em outra aba. Link (e não <a href>)
            para o endereço ganhar o /app/ do começo sozinho */}
        <Link to="/painel" target="_blank" rel="noreferrer">Painel da TV</Link>
      </nav>

      <div className="usuario">
        <SeletorDeTema />
        {/* Clicar no próprio nome leva para "Minha senha" (igual ao Flask) */}
        <NavLink to="/minha-senha" title="Trocar minha senha">{usuario.nome}</NavLink>
        <button type="button" onClick={sair}>Sair</button>
      </div>
    </header>
  )
}
