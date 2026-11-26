/**
 * A linha de números de destaque do topo do relatório.
 *
 * Um número sozinho não precisa de gráfico: grande e com um rótulo
 * claro, ele se lê num relance.
 */
function Indicador({ rotulo, valor, extra }) {
  return (
    <div className="indicador">
      <span className="indicador-rotulo">{rotulo}</span>
      <span className="indicador-valor">{valor}</span>
      {extra && <span className="indicador-extra">{extra}</span>}
    </div>
  )
}

export default function Indicadores({ dados }) {
  return (
    <div className="indicadores">
      <Indicador rotulo="Chegaram" valor={dados.chegaram} />
      <Indicador
        rotulo="Atendidos"
        valor={dados.atendidos}
        extra={`não compareceram: ${dados.nao_compareceram}`}
      />
      <Indicador rotulo="Espera média" valor={dados.espera_media} extra={`maior: ${dados.maior_espera}`} />
      <Indicador rotulo="Duração média" valor={dados.duracao_media} extra="por atendimento" />
    </div>
  )
}
