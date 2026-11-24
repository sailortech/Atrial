import { useState } from 'react'

/**
 * [Chamar para... ▾] [Chamar próximo]
 *
 * O local escolhido começa como o último usado (vem do servidor).
 */
export default function BarraDeChamada({ locais, ultimoLocal, totalNaFila, aoChamar }) {
  // null = a pessoa ainda não mexeu no seletor
  const [escolhido, setEscolhido] = useState(null)

  // "Estado derivado": em vez de copiar ultimoLocal para o estado com
  // um useEffect, calculamos na hora. Se a pessoa não escolheu nada,
  // vale o último local usado (se ele ainda estiver ativo).
  const local = escolhido ?? (locais.includes(ultimoLocal) ? ultimoLocal : '')

  return (
    <div className="barra-chamada">
      <select
        value={local}
        onChange={(e) => setEscolhido(e.target.value)}
        aria-label="Chamar para"
      >
        <option value="" disabled>Chamar para...</option>
        {locais.map((nome) => (
          <option key={nome} value={nome}>{nome}</option>
        ))}
      </select>

      <button
        type="button"
        className="principal"
        disabled={!local || totalNaFila === 0}
        onClick={() => aoChamar(local)}
      >
        Chamar próximo
      </button>

      <span className="dica">{totalNaFila} na fila</span>
    </div>
  )
}
