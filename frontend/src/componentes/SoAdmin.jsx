import { Navigate, Outlet } from 'react-router-dom'

import { useSessao } from '../sessao.jsx'

/**
 * Segunda "portaria", dentro da AreaLogada: só deixa passar quem é
 * da administração. Igual ao @admin_obrigatorio do Flask.
 *
 * De novo: isto só evita mostrar uma tela que não funcionaria. Quem
 * PROTEGE de verdade é o Flask, que responde 403 para a recepção.
 */
export default function SoAdmin() {
  const { usuario } = useSessao()

  if (!usuario.admin) {
    // <Navigate> = redirecionar enquanto desenha (replace: sem deixar
    // a página proibida no histórico do "Voltar")
    return <Navigate to="/pacientes" replace />
  }

  return <Outlet />
}
