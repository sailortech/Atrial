import { useState } from 'react'

import { caminhoBarra, chegadas, doisDigitos, escalaDoEixo } from './escala.js'

// Medidas do desenho (em "unidades do SVG"; o navegador estica tudo
// para a largura da tela, mantendo a proporção)
const LARGURA = 720
const ALTURA = 240
const MARGEM = { esquerda: 36, direita: 8, topo: 12, base: 28 }
const AREA_L = LARGURA - MARGEM.esquerda - MARGEM.direita
const AREA_A = ALTURA - MARGEM.topo - MARGEM.base
const CHAO = MARGEM.topo + AREA_A // o "y" do zero

/**
 * Gráfico de barras: chegadas por hora.
 *
 * No Flask, o servidor calculava cada barra e o template só colava.
 * Aqui o servidor manda só [{hora, total}] e o React CALCULA o
 * desenho: é JavaScript comum (map, contas) gerando elementos <svg>.
 */
export default function GraficoPorHora({ porHora }) {
  // Qual coluna está com o mouse em cima (ou com foco do teclado)
  const [ativa, setAtiva] = useState(null)

  if (porHora.length === 0) {
    return <p className="vazio">Nenhuma chegada registrada neste dia.</p>
  }

  const { topo, marcas } = escalaDoEixo(Math.max(...porHora.map((l) => l.total)))
  const y = (valor) => MARGEM.topo + AREA_A - (valor / topo) * AREA_A

  const coluna = AREA_L / porHora.length
  const larguraBarra = Math.min(coluna * 0.6, 32) // barras finas

  // Uma "descrição" de cada coluna, calculada uma vez
  const colunas = porHora.map((linha, i) => {
    const inicio = MARGEM.esquerda + i * coluna
    return { ...linha, inicio, centro: inicio + coluna / 2 }
  })

  const destaque = ativa === null ? null : colunas[ativa]

  return (
    <>
      <div className="grafico-area">
        <svg
          viewBox={`0 0 ${LARGURA} ${ALTURA}`}
          role="img"
          aria-label="Gráfico de barras: chegadas de pacientes por hora"
        >
          {/* Grade bem clara, com os números do eixo */}
          {marcas.map((valor) => (
            <g key={valor}>
              <line className="grade" x1={MARGEM.esquerda} x2={LARGURA - MARGEM.direita}
                    y1={y(valor)} y2={y(valor)} />
              <text className="eixo" x={MARGEM.esquerda - 8} y={y(valor)}
                    textAnchor="end" dominantBaseline="middle">{valor}</text>
            </g>
          ))}

          {colunas.map((c, i) => (
            <g
              key={c.hora}
              className="coluna"
              tabIndex={0}
              aria-label={`${doisDigitos(c.hora)}: ${chegadas(c.total)}`}
              onMouseEnter={() => setAtiva(i)}
              onMouseLeave={() => setAtiva(null)}
              onFocus={() => setAtiva(i)}
              onBlur={() => setAtiva(null)}
            >
              {/* Área invisível do tamanho da coluna: fácil de acertar com o mouse */}
              <rect className="alvo" x={c.inicio} y={MARGEM.topo} width={coluna} height={AREA_A} />
              {c.total > 0 && (
                <path className="barra" d={caminhoBarra(c.centro - larguraBarra / 2, y(c.total), larguraBarra, CHAO)} />
              )}
              <text className="eixo" x={c.centro} y={CHAO + 18} textAnchor="middle">{c.hora}h</text>
            </g>
          ))}

          <line className="chao" x1={MARGEM.esquerda} x2={LARGURA - MARGEM.direita} y1={CHAO} y2={CHAO} />
        </svg>

        {/* A dica é posicionada em PORCENTAGEM do desenho: como o SVG
            estica junto com a tela, a conta vale em qualquer largura */}
        {destaque && (
          <div
            className="grafico-dica"
            style={{
              left: `${(destaque.centro / LARGURA) * 100}%`,
              top: `${(y(destaque.total) / ALTURA) * 100}%`,
            }}
          >
            <strong>{chegadas(destaque.total)}</strong> às {doisDigitos(destaque.hora)}
          </div>
        )}
      </div>

      {/* Os mesmos números em tabela: para leitor de tela, ou para
          quem só quer o valor exato */}
      <details>
        <summary>Ver como tabela</summary>
        <table>
          <thead><tr><th>Hora</th><th>Chegadas</th></tr></thead>
          <tbody>
            {porHora.filter((l) => l.total > 0).map((l) => (
              <tr key={l.hora}><td>{doisDigitos(l.hora)}</td><td>{l.total}</td></tr>
            ))}
          </tbody>
        </table>
      </details>
    </>
  )
}
