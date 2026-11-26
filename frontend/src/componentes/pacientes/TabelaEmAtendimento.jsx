import { Link } from 'react-router-dom'

import Prioridade from './Prioridade.jsx'

export default function TabelaEmAtendimento({ pacientes, acoes }) {
  return (
    <section>
      <h3>Em atendimento ({pacientes.length})</h3>

      {pacientes.length === 0 ? (
        <p className="vazio">Ninguém sendo atendido no momento.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Nome</th>
              <th>Local</th>
              <th>Prioridade</th>
              <th>Chamado às</th>
              <th>Esperou</th>
              <th>Observações</th>
              <th>Ações</th>
            </tr>
          </thead>
          <tbody>
            {pacientes.map((p) => (
              <tr key={p.id} className="em-atendimento">
                <td>
                  {p.nome}
                  <Link to={`/pacientes/${p.id}/editar`} className="editar">editar</Link>
                </td>
                <td>{p.local ?? '-'}</td>
                <td><Prioridade valor={p.prioridade} /></td>
                <td>{p.chamado_em}</td>
                <td>{p.esperou}</td>
                <td>{p.observacoes || '-'}</td>
                <td className="acoes">
                  {/* () => ...: a função só roda no CLIQUE, com o id certo */}
                  <button type="button" className="principal" onClick={() => acoes.concluir(p.id)}>
                    Concluir
                  </button>
                  <button type="button" onClick={() => acoes.chamarDeNovo(p.id)}>
                    Chamar de novo
                  </button>
                  {p.foi_rechamado && (
                    <small className="rechamado">chamado de novo às {p.ultima_chamada}</small>
                  )}
                  <button type="button" className="link perigo" onClick={() => acoes.naoCompareceu(p.id)}>
                    Não compareceu
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
