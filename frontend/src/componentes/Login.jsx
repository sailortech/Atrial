import { useState } from 'react'

import { useSessao } from '../sessao.jsx'

/**
 * Formulário de login. Mostra o padrão de formulário em React:
 * "componente controlado" = o React guarda o que está digitado
 * (useState) e o campo sempre mostra esse valor.
 */
export default function Login() {
  const { entrar } = useSessao()

  const [login, setLogin] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState(null)
  const [enviando, setEnviando] = useState(false)

  async function aoEnviar(evento) {
    // Sem isto o navegador recarregaria a página (comportamento
    // padrão de um <form>); quem cuida do envio aqui é o React.
    evento.preventDefault()

    setEnviando(true)
    setErro(null)
    try {
      await entrar(login, senha)
      // Deu certo: a sessão muda e a AreaLogada mostra a tela pedida
    } catch (e) {
      setErro(e.message) // a mensagem vem do Flask
      setSenha('') // senha errada não fica no campo
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="pagina estreita">
      <h1 className="marca">Atrial</h1>
      <h2>Entrar</h2>

      {erro && <p className="mensagem erro">{erro}</p>}

      <form onSubmit={aoEnviar} className="formulario">
        <label htmlFor="login">Usuário</label>
        <input
          id="login"
          value={login}
          onChange={(e) => setLogin(e.target.value)}
          autoComplete="username"
          autoFocus
          required
        />

        <label htmlFor="senha">Senha</label>
        <input
          id="senha"
          type="password"
          value={senha}
          onChange={(e) => setSenha(e.target.value)}
          autoComplete="current-password"
          required
        />

        <button type="submit" className="principal" disabled={enviando}>
          {enviando ? 'Entrando...' : 'Entrar'}
        </button>
      </form>
    </div>
  )
}
