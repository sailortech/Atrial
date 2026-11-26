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
