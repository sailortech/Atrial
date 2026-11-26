import { Link } from 'react-router-dom'

import Prioridade from './Prioridade.jsx'

export default function TabelaFila({ pacientes }) {
  return (
    <section>
      <h3>Fila de espera ({pacientes.length})</h3>

      {pacientes.length === 0 ? (
        <p className="vazio">A fila está vazia.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Posição</th>
              <th>Nome</th>
              <th>Prioridade</th>
              <th>Chegada</th>
              <th>Esperando há</th>
              <th>CPF</th>
              <th>Telefone</th>
            </tr>
          </thead>
          <tbody>
            {pacientes.map((p) => (
              <tr key={p.id}>
                <td>{p.posicao}º</td>
                <td>
                  {p.nome}
                  <Link to={`/pacientes/${p.id}/editar`} className="editar">editar</Link>
                </td>
                <td><Prioridade valor={p.prioridade} /></td>
                <td>{p.chegada}</td>
                <td>{p.esperando_ha}</td>
                <td>{p.cpf}</td>
                <td>{p.telefone || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )
}
