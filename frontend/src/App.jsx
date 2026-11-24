import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import AreaLogada from './componentes/AreaLogada.jsx'
import Painel from './componentes/Painel.jsx'
import Pacientes from './paginas/Pacientes.jsx'
import { SessaoProvider } from './sessao.jsx'

/**
 * As "rotas" do React: qual tela aparece para cada endereço.
 *
 * Diferente do Flask, trocar de tela aqui NÃO recarrega a página:
 * o React Router só troca o componente desenhado (por isso é rápido).
 */
export default function App() {
  return (
    <SessaoProvider>
      <BrowserRouter>
        <Routes>
          {/* A TV não pede login (igual ao /painel do Flask) */}
          <Route path="/painel" element={<Painel />} />

          {/* Tudo aqui dentro só aparece para quem está logado */}
          <Route element={<AreaLogada />}>
            <Route path="/pacientes" element={<Pacientes />} />
          </Route>

          {/* Qualquer outro endereço vai para a lista de pacientes */}
          <Route path="*" element={<Navigate to="/pacientes" replace />} />
        </Routes>
      </BrowserRouter>
    </SessaoProvider>
  )
}
