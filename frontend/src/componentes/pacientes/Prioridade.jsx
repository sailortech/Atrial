// Etiqueta colorida da prioridade. Um componente bem pequeno, mas
// usado em várias tabelas: muda aqui, muda em todas.
export default function Prioridade({ valor }) {
  return <span className={`prioridade ${valor.toLowerCase()}`}>{valor}</span>
}
