import { Link, useSearchParams } from 'react-router-dom'

import Prioridade from '../componentes/pacientes/Prioridade.jsx'
import GraficoPorHora from '../componentes/relatorio/GraficoPorHora.jsx'
import Indicadores from '../componentes/relatorio/Indicadores.jsx'
import useRelatorio from '../hooks/useRelatorio.js'

/**
 * Relatório do dia.
 *
 * O dia escolhido fica no ENDEREÇO (/relatorio?dia=2026-11-18), e não
 * num useState. Vantagens: dá para mandar o link para alguém, o F5
 * mantém o dia, e o "Voltar" do navegador volta para o dia anterior.
 * useSearchParams é o useState do "?..." do endereço.
 */
export default function Relatorio() {
  const [parametros, setParametros] = useSearchParams()
  const dia = parametros.get('dia') ?? '' // vazio = hoje

  const { dados, erro, carregando } = useRelatorio(dia)

  if (!dados) {
    return <p className="carregando">{erro ?? 'Carregando...'}</p>
  }

  // Datas "AAAA-MM-DD" podem ser comparadas como texto
  const eHoje = dados.dia >= dados.hoje

  return (
    <>
      <h2>Relatório do dia</h2>

      {erro && <p className="mensagem erro">{erro}</p>}

      <div className="relatorio-dia">
        <Link to={`?dia=${dados.anterior}`}>← Anterior</Link>
        <input
          type="date"
          aria-label="Dia do relatório"
          value={dados.dia}
          max={dados.hoje}
          // Escolheu uma data? Muda o endereço, e o hook busca o dia novo
          onChange={(e) => e.target.value && setParametros({ dia: e.target.value })}
        />
        {!eHoje && <Link to={`?dia=${dados.seguinte}`}>Seguinte →</Link>}
        {!eHoje && <Link to="/relatorio">Hoje</Link>}
        {carregando && <span className="dica">Carregando...</span>}
      </div>

      {/* Enquanto carrega outro dia, os números antigos ficam apagados */}
      <div className={carregando ? 'desatualizado' : undefined}>
        <Indicadores dados={dados} />

        <section className="grafico">
          <h3>Chegadas por hora</h3>
          <GraficoPorHora porHora={dados.por_hora} />
        </section>

        <section>
          <h3>Por prioridade</h3>
          <table>
            <thead>
              <tr><th>Prioridade</th><th>Chegaram</th><th>Chamados</th><th>Espera média</th></tr>
            </thead>
            <tbody>
              {dados.por_prioridade.map((l) => (
                <tr key={l.prioridade}>
                  <td><Prioridade valor={l.prioridade} /></td>
                  <td>{l.chegaram}</td>
                  <td>{l.chamados}</td>
                  <td>{l.espera_media}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section>
          <h3>Por local</h3>
          <table>
            <thead>
              <tr><th>Local</th><th>Atendimentos concluídos</th><th>Duração média</th></tr>
            </thead>
            <tbody>
              {dados.por_local.map((l) => (
                <tr key={l.local}>
                  <td>{l.local}</td>
                  <td>{l.atendidos}</td>
                  <td>{l.duracao_media}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </>
  )
}
