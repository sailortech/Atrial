import useTema from '../hooks/useTema.js'

const NOMES = { auto: 'Automático', claro: 'Claro', escuro: 'Escuro' }

/**
 * [Tema: Automático ▾] no cabeçalho.
 * "Automático" segue o que está escolhido no Windows (ou no celular).
 */
export default function SeletorDeTema() {
  const [tema, setTema] = useTema()

  return (
    <label className="tema" title="Claro, escuro ou igual ao sistema">
      <span className="so-leitor">Tema</span>
      <select value={tema} onChange={(e) => setTema(e.target.value)}>
        {Object.entries(NOMES).map(([valor, nome]) => (
          <option key={valor} value={valor}>
            {valor === 'auto' ? `◐ ${nome}` : valor === 'claro' ? `☀ ${nome}` : `☾ ${nome}`}
          </option>
        ))}
      </select>
    </label>
  )
}
