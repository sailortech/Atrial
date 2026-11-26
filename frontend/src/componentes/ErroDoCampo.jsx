/**
 * Mensagem de erro embaixo de um campo (some quando não há erro).
 *
 * erros = o dicionário que o Flask manda no 422: { cpf: "CPF inválido..." }.
 * O id liga a mensagem ao campo (aria-describedby), para o leitor de
 * tela ler o erro junto com o campo.
 */
export default function ErroDoCampo({ campo, erros }) {
  if (!erros[campo]) return null
  return <span id={`erro-${campo}`} className="erro-campo">{erros[campo]}</span>
}

