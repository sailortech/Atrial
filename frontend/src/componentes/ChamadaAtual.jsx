/**
 * O destaque do meio da tela: quem está sendo chamado e para onde.
 *
 * "Props" são os dados que o componente recebe de quem o usa, como
 * os atributos de uma tag HTML:  <ChamadaAtual chamada={...} />
 */
export default function ChamadaAtual({ chamada }) {
  // Ninguém chamado ainda: mostra só a mensagem de espera
  if (!chamada) {
    return (
      <div className="atual">
        <p className="rotulo">Aguarde ser chamado</p>
      </div>
    )
  }

  // O texto vai entre chaves { }. O React sempre trata como TEXTO:
  // um nome com "<b>" aparece escrito, nunca vira HTML (seguro).
  return (
    // "piscando": a animação do CSS roda quando o elemento aparece.
    // O Painel troca a "key" deste componente a cada chamada nova,
    // então o React cria um elemento novo e a animação roda de novo.
    <div className="atual piscando">
      <p className="rotulo">{chamada.de_novo ? 'Chamando novamente' : 'Chamando agora'}</p>
      <p className="nome">{chamada.nome}</p>

      {/* && : só mostra a linha se houver local (chamadas antigas não têm) */}
      {chamada.local && <p className="local">→ {chamada.local}</p>}

      <p className="detalhe">
        {chamada.prioridade} · chamado às {chamada.hora}
      </p>
    </div>
  )
}
