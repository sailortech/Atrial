// Lista das chamadas anteriores (rodapé, à esquerda)
export default function UltimasChamadas({ chamadas }) {
  return (
    <div>
      <p className="rotulo">Últimas chamadas</p>
      <ul className="anteriores">
        {/* .map transforma cada chamada em um <li>.
            "key" ajuda o React a saber qual item é qual quando a
            lista muda (precisa ser única: usamos a chave da chamada). */}
        {chamadas.map((chamada) => (
          <li key={chamada.chave}>
            {chamada.nome}
            {chamada.local && ` → ${chamada.local}`}
            <span className="hora">{chamada.hora}</span>
          </li>
        ))}
      </ul>
    </div>
  )
}
