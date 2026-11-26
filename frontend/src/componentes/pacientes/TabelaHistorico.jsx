import { Link } from 'react-router-dom'

export default function TabelaHistorico({ pacientes }) {
  return (
    <section>
      <h3>Histórico de atendimentos ({pacientes.length})</h3>

      {pacientes.length === 0 ? (
        <p className="vazio">Nenhum atendimento encerrado ainda.</p>
      ) : (
        <table className="historico">
          <thead>
            <tr>
              <th>Nome</th>
              <th>Local</th>
              <th>Prioridade</th>
              <th>Encerrado em</th>
              <th>Esperou</th>
              <th>Duração</th>
            </tr>
          </thead>
          <tbody>
            {pacientes.map((p) => {
              const ausente = p.status === 'Não compareceu'
              return (
                <tr key={p.id} className={ausente ? 'ausente' : undefined}>
                  <td>
                    {p.nome}
                    <Link to={`/pacientes/${p.id}/editar`} className="editar">editar</Link>
                  </td>
                  <td>{p.local ?? '-'}</td>
                  <td>{p.prioridade}</td>
                  <td>{p.encerrado_em ?? '-'}</td>
                  <td>{p.esperou}</td>
                  {/* Quem não veio não teve atendimento: não há duração */}
                  <td>{ausente ? <strong>Não compareceu</strong> : p.duracao}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </section>
  )
}
