import { useEffect, useState } from 'react'

function horaAtual() {
  return new Date().toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' })
}

// Um componente é uma função que devolve o que deve aparecer na tela.
// Este cuida sozinho da própria hora: o resto do painel nem fica sabendo.
export default function Relogio() {
  const [hora, setHora] = useState(horaAtual)

  useEffect(() => {
    const timer = setInterval(() => setHora(horaAtual()), 1000)
    return () => clearInterval(timer)
  }, [])

  return <span className="relogio">{hora}</span>
}
