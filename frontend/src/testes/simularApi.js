import { vi } from 'vitest'

/**
 * Troca o fetch do navegador por um FALSO, que responde como o Flask
 * responderia, sem servidor nenhum. Assim o teste controla exatamente
 * o que "o servidor" diz (inclusive erros difíceis de provocar).
 *
 *   const api = simularApi({
 *     'GET /api/locais': { locais: [...] },               // 200 + este JSON
 *     'POST /api/locais': [422, { erro: '...', erros: {...} }],  // código + JSON
 *     'POST /api/x': (corpo) => [201, { mensagem: corpo.nome }], // calculado
 *   })
 *
 * Devolve o fetch falso: api.pedidos lista o que o React pediu
 * ([{ metodo, caminho, corpo }]), para o teste conferir.
 */
export function simularApi(rotas) {
  const pedidos = []

  const fetchFalso = vi.fn(async (caminho, opcoes = {}) => {
    const metodo = opcoes.method ?? 'GET'
    const corpo = opcoes.body ? JSON.parse(opcoes.body) : undefined
    pedidos.push({ metodo, caminho, corpo })

    // A chave ignora o "?..." do endereço
    const chave = `${metodo} ${caminho.split('?')[0]}`
    if (!(chave in rotas)) {
      throw new Error(`simularApi: ninguém respondeu "${chave}"`)
    }

    let resposta = rotas[chave]
    if (typeof resposta === 'function') resposta = resposta(corpo)
    const [status, dados] = Array.isArray(resposta) ? resposta : [200, resposta]

    // Só o que o api.js usa de uma resposta de verdade
    return { ok: status < 400, status, json: async () => dados }
  })

  fetchFalso.pedidos = pedidos
  vi.stubGlobal('fetch', fetchFalso)
  return fetchFalso
}
