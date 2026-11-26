/**
 * Contas do gráfico de barras. Funções "puras": recebem números e
 * devolvem números (ou texto), sem tela nenhuma. Por isso moram fora
 * do componente: são fáceis de testar (veja escala.test.js).
 */

/**
 * Topo do eixo: um número "redondo" com no máximo ~5 marcas.
 * Ex.: maior = 7 -> passo 2, topo 8 (marcas 0, 2, 4, 6, 8).
 */
export function escalaDoEixo(maior) {
  const passo = [1, 2, 5, 10, 20, 50, 100].find((p) => maior / p <= 5) ?? 100
  const topo = Math.ceil(maior / passo) * passo
  const marcas = []
  for (let v = 0; v <= topo; v += passo) marcas.push(v)
  return { topo, marcas }
}

/**
 * Contorno de uma barra com só os cantos de CIMA arredondados
 * (a base fica reta, "apoiada" no chão do gráfico, no y = chao).
 */
export function caminhoBarra(x, yTopo, largura, chao) {
  const r = Math.min(4, largura / 2, chao - yTopo)
  return [
    `M${x},${chao}`,
    `V${yTopo + r}`,
    `Q${x},${yTopo} ${x + r},${yTopo}`,
    `H${x + largura - r}`,
    `Q${x + largura},${yTopo} ${x + largura},${yTopo + r}`,
    `V${chao} Z`,
  ].join(' ')
}

export const doisDigitos = (hora) => `${String(hora).padStart(2, '0')}h`

export const chegadas = (n) => `${n} ${n === 1 ? 'chegada' : 'chegadas'}`
