/**
 * Conversa com a API do Flask (/api/...).
 *
 * Tudo que fala com o servidor passa por aqui, então detalhes como o
 * código CSRF e o tratamento de erros ficam num lugar só, e os
 * componentes só fazem: await api.get('/api/pacientes').
 */

// Código CSRF que o Flask mandou em /api/sessao. Todo POST precisa
// devolvê-lo no cabeçalho X-CSRFToken (senão o Flask recusa).
let codigoCsrf = null

export function guardarCsrf(codigo) {
  codigoCsrf = codigo
}

// Erro com o código HTTP junto (401 = não logado, 409 = não deu...),
// para quem chamou poder decidir o que fazer.
export class ErroDaApi extends Error {
  constructor(status, mensagem, dados) {
    super(mensagem)
    this.status = status
    this.dados = dados
  }
}

async function pedir(metodo, caminho, corpo) {
  const opcoes = { method: metodo, headers: {} }

  if (corpo !== undefined) {
    opcoes.headers['Content-Type'] = 'application/json'
    opcoes.body = JSON.stringify(corpo)
  }
  if (metodo !== 'GET' && codigoCsrf) {
    opcoes.headers['X-CSRFToken'] = codigoCsrf
  }

  let resposta
  try {
    resposta = await fetch(caminho, opcoes)
  } catch {
    // fetch só "falha" quando nem chegou ao servidor (rede, servidor fora)
    throw new ErroDaApi(0, 'Sem conexão com o servidor.')
  }

  // .catch: se a resposta não for JSON (ex.: erro 500 em HTML), não quebra
  const dados = await resposta.json().catch(() => ({}))

  if (!resposta.ok) {
    throw new ErroDaApi(resposta.status, dados.erro ?? `Erro ${resposta.status}`, dados)
  }
  return dados
}

export const api = {
  get: (caminho) => pedir('GET', caminho),
  post: (caminho, corpo) => pedir('POST', caminho, corpo),
  put: (caminho, corpo) => pedir('PUT', caminho, corpo),
}
