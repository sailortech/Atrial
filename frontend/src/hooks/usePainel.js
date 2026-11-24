import { useEffect, useState } from 'react'

const INTERVALO = 3000 // milissegundos

/**
 * Busca os dados do painel no Flask (/painel/dados) a cada 3 segundos.
 *
 * Um "hook" é uma função que usa recursos do React (como useState e
 * useEffect). Por convenção o nome começa com "use". Qualquer componente
 * pode chamar usePainel() e receber os dados sempre atualizados.
 *
 * Devolve { dados, semConexao }:
 *   dados      -> o JSON do Flask (null até a primeira resposta)
 *   semConexao -> true se a última busca falhou
 */
export default function usePainel() {
  // useState guarda um valor que, quando muda, faz o React
  // redesenhar a tela. setDados(...) é o jeito de mudar o valor.
  const [dados, setDados] = useState(null)
  const [semConexao, setSemConexao] = useState(false)

  // useEffect roda código "de fora" do React (buscar dados, timers...)
  // DEPOIS que o componente aparece na tela.
  useEffect(() => {
    async function buscar() {
      try {
        const resposta = await fetch('/painel/dados')
        if (!resposta.ok) throw new Error(`HTTP ${resposta.status}`)
        setDados(await resposta.json())
        setSemConexao(false)
      } catch {
        // Servidor fora do ar: mantém o que já estava na tela
        setSemConexao(true)
      }
    }

    buscar() // a primeira vez, sem esperar 3 segundos
    const timer = setInterval(buscar, INTERVALO)

    // A função devolvida é a "limpeza": roda quando o componente sai da
    // tela. Sem ela, o timer continuaria rodando para sempre.
    return () => clearInterval(timer)
  }, []) // [] = rodar uma vez só, quando o componente aparece

  return { dados, semConexao }
}
