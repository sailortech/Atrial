import { useCallback, useEffect, useState } from 'react'

import { api } from '../api.js'
import { useSessao } from '../sessao.jsx'

const INTERVALO = 20000 // atualiza sozinho a cada 20 s (igual à página Flask)

/**
 * Busca as listas de pacientes (/api/pacientes?q=termo).
 *
 * Devolve { dados, erro, recarregar }. Chame recarregar() depois de
 * uma ação (chamar, concluir...) para ver o resultado na hora.
 */
export default function usePacientes(termo) {
  const { atualizar: atualizarSessao } = useSessao()

  const [dados, setDados] = useState(null)
  const [erro, setErro] = useState(null)
  // Mudar este número força uma nova busca (veja recarregar)
  const [versao, setVersao] = useState(0)

  useEffect(() => {
    // "ignorar": se o termo mudar no meio de uma busca (a pessoa
    // continuou digitando), a resposta ANTIGA chega depois e não pode
    // sobrescrever a nova. A limpeza do efeito marca a busca velha.
    let ignorar = false

    async function buscar() {
      try {
        const resposta = await api.get(`/api/pacientes?q=${encodeURIComponent(termo)}`)
        if (!ignorar) {
          setDados(resposta)
          setErro(null)
        }
      } catch (e) {
        if (ignorar) return
        if (e.status === 401 || e.status === 403) {
          // Sessão acabou (ou senha provisória): a portaria decide o que mostrar
          atualizarSessao()
        } else {
          setErro(e.message)
        }
      }
    }

    buscar()
    const timer = setInterval(buscar, INTERVALO)

    return () => {
      ignorar = true
      clearInterval(timer)
    }
  }, [termo, versao, atualizarSessao]) // roda de novo se algum destes mudar

  const recarregar = useCallback(() => setVersao((v) => v + 1), [])

  return { dados, erro, recarregar }
}
