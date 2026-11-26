/**
 * Faixa de retorno de uma ação ("Local adicionado.", "Fila vazia"...),
 * com o × para fechar. É o flash() do Flask, versão React.
 *
 * mensagem = { tipo: 'sucesso' | 'erro', texto } ou null (não mostra nada)
 */
export default function Mensagem({ mensagem, aoFechar }) {
  if (!mensagem) return null

  return (
    // role="status": o leitor de tela anuncia a mensagem quando ela aparece
    <p className={`mensagem ${mensagem.tipo}`} role="status">
      {mensagem.texto}
      <button type="button" className="fechar" onClick={aoFechar} aria-label="Fechar mensagem">
        ×
      </button>
    </p>
  )
}
