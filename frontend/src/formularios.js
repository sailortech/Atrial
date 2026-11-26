/**
 * Ajudantes dos formulários (cadastro de paciente, minha senha...).
 *
 * Fica num arquivo .js separado porque arquivos de componente devem
 * exportar SÓ componentes (é o que o lint cobra, para o "fast refresh"
 * do Vite funcionar ao salvar).
 */

/** As props de acessibilidade de um campo que pode ter erro. */
export function marcarErro(campo, erros) {
  return {
    'aria-invalid': erros[campo] ? true : undefined,
    'aria-describedby': erros[campo] ? `erro-${campo}` : undefined,
  }
}

/**
 * Põe os pontos e o traço enquanto a pessoa digita:
 * "5299822" -> "529.982.2". Só deixa números e no máximo 11.
 */
export function mascaraCpf(texto) {
  const d = texto.replace(/\D/g, '').slice(0, 11)
  return d
    .replace(/^(\d{3})(\d)/, '$1.$2')
    .replace(/^(\d{3})\.(\d{3})(\d)/, '$1.$2.$3')
    .replace(/\.(\d{3})(\d)/, '.$1-$2')
}
