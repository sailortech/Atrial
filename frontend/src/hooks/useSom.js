import { useCallback, useRef, useState } from 'react'

/**
 * Aviso sonoro ("plim-plom") gerado pelo próprio navegador (Web Audio).
 *
 * Navegadores só deixam tocar som depois de um clique na página, por
 * isso existe ativar(): é chamado pelo botão "Ativar som".
 *
 * Devolve { ativo, ativar, tocar }.
 */
export default function useSom() {
  const [ativo, setAtivo] = useState(false)

  // useRef guarda um valor que NÃO redesenha a tela quando muda.
  // Serve para coisas "de bastidor", como o AudioContext.
  const audio = useRef(null)

  // useCallback mantém a MESMA função entre um desenho e outro;
  // assim quem usa tocar() num useEffect não roda à toa.
  const tocar = useCallback(() => {
    const contexto = audio.current
    if (!contexto) return // som ainda não ativado

    // Duas notas: Mi (659 Hz) e depois Dó (523 Hz), sumindo aos poucos
    for (const [frequencia, inicio, duracao] of [[659, 0, 0.6], [523, 0.35, 0.9]]) {
      const oscilador = contexto.createOscillator()
      const volume = contexto.createGain()
      const t = contexto.currentTime + inicio

      oscilador.type = 'sine'
      oscilador.frequency.value = frequencia
      volume.gain.setValueAtTime(0.3, t)
      volume.gain.exponentialRampToValueAtTime(0.001, t + duracao)

      oscilador.connect(volume).connect(contexto.destination)
      oscilador.start(t)
      oscilador.stop(t + duracao)
    }
  }, [])

  const ativar = useCallback(() => {
    // Este clique é a "permissão" que o navegador exige
    audio.current = new AudioContext()
    setAtivo(true)
    tocar() // toca uma vez para confirmar que funciona
  }, [tocar])

  return { ativo, ativar, tocar }
}
