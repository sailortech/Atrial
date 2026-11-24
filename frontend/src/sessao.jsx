/* eslint-disable react-refresh/only-export-components --
   este arquivo exporta o "provedor" e o hook que o lê, de propósito */
import { createContext, useCallback, useContext, useEffect, useState } from 'react'

import { api, guardarCsrf } from './api.js'

/**
 * Quem está logado, disponível para QUALQUER componente.
 *
 * Context resolve um problema comum: vários componentes, em lugares
 * diferentes da árvore, precisam da mesma informação (o cabeçalho
 * mostra o nome, a tela de pacientes precisa saber se está logado...).
 * Em vez de passar props de pai para filho em cada nível, o
 * <SessaoProvider> "disponibiliza" e quem precisa lê com useSessao().
 */
const SessaoContext = createContext(null)

export function SessaoProvider({ children }) {
  // undefined = ainda perguntando ao servidor; null = ninguém logado
  const [usuario, setUsuario] = useState(undefined)

  // Pergunta ao Flask quem está logado (e pega o código CSRF)
  const atualizar = useCallback(async () => {
    try {
      const dados = await api.get('/api/sessao')
      guardarCsrf(dados.csrf)
      setUsuario(dados.usuario)
    } catch {
      setUsuario(null)
    }
  }, [])

  useEffect(() => {
    atualizar()
  }, [atualizar])

  const entrar = useCallback(async (login, senha) => {
    const dados = await api.post('/api/login', { login, senha })
    setUsuario(dados.usuario)
  }, [])

  const sair = useCallback(async () => {
    await api.post('/api/logout')
    setUsuario(null)
  }, [])

  return (
    <SessaoContext.Provider value={{ usuario, entrar, sair, atualizar }}>
      {children}
    </SessaoContext.Provider>
  )
}

export function useSessao() {
  return useContext(SessaoContext)
}
