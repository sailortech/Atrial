import { useEffect, useState } from 'react'

import { api } from '../api.js'
import { useSessao } from '../sessao.jsx'

/**
 * Busca os números de um dia (/api/relatorio?dia=AAAA-MM-DD).
 * dia vazio = hoje (quem decide é o servidor).
 *
 * Devolve { dados, erro, carregando }. Enquanto troca de dia, os
 * dados ANTIGOS continuam na tela (carregando = true): assim a página
 * não "pisca" vazia a cada clique em Anterior/Seguinte.
 */
export default function useRelatorio(dia) {
  const { atualizar: atualizarSessao } = useSessao()

  const [dados, setDados] = useState(null)
  const [erro, setErro] = useState(null)
  // Qual dia os dados na tela representam (para saber se está carregando)
  const [diaCarregado, setDiaCarregado] = useState(null)

  useEffect(() => {
    let ignorar = false // dia mudou antes da resposta chegar? descarta

    api.get(`/api/relatorio?dia=${encodeURIComponent(dia)}`)
      .then((resposta) => {
        if (ignorar) return
        setDados(resposta)
        setErro(null)
        setDiaCarregado(dia)
      })
      .catch((e) => {
        if (ignorar) return
        if (e.status === 401 || e.status === 403) atualizarSessao()
        else setErro(e.message)
      })

    return () => { ignorar = true }
  }, [dia, atualizarSessao])

  // "Estado derivado": não precisa de um useState só para isso
  const carregando = diaCarregado !== dia

  return { dados, erro, carregando }
}
