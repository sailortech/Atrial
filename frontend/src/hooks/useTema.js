import { useEffect, useState } from 'react'

/**
 * Tema da tela: 'auto' (segue o sistema), 'claro' ou 'escuro'.
 *
 * A escolha fica guardada no NAVEGADOR (localStorage), e não no
 * servidor: é um gosto de cada computador. A TV, o computador da
 * recepção e o celular podem ter temas diferentes, com o mesmo login.
 *
 * Quem pinta a tela é o CSS (app.css), olhando o atributo data-tema
 * do <html>. Este hook só põe e tira esse atributo.
 */
export const TEMAS = ['auto', 'claro', 'escuro']

// O mesmo nome é lido pelo script do index.html (antes do React carregar)
const CHAVE = 'atrial-tema'

export function lerTemaSalvo() {
  try {
    const salvo = localStorage.getItem(CHAVE)
    return TEMAS.includes(salvo) ? salvo : 'auto'
  } catch {
    return 'auto' // navegador que bloqueia o localStorage (modo privado antigo)
  }
}

export function aplicarTema(tema) {
  const raiz = document.documentElement // o <html>
  if (tema === 'auto') {
    delete raiz.dataset.tema // sem atributo: o CSS segue o sistema
  } else {
    raiz.dataset.tema = tema // vira <html data-tema="escuro">
  }
}

export default function useTema() {
  // useState(função): a função só roda no PRIMEIRO desenho, para
  // ler o valor inicial (e não a cada desenho)
  const [tema, setTema] = useState(lerTemaSalvo)

  // Toda vez que o tema muda: aplica na página e guarda a escolha.
  // Isto é um "efeito colateral" (mexe em coisas FORA do React: o
  // <html> e o localStorage), por isso fica num useEffect.
  useEffect(() => {
    aplicarTema(tema)
    try {
      if (tema === 'auto') localStorage.removeItem(CHAVE)
      else localStorage.setItem(CHAVE, tema)
    } catch {
      // sem localStorage: o tema vale só até fechar a aba
    }
  }, [tema])

  return [tema, setTema]
}
