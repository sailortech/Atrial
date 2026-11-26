import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import ErroDoCampo from '../componentes/ErroDoCampo.jsx'
import { marcarErro } from '../formularios.js'
import { useSessao } from '../sessao.jsx'

const EM_BRANCO = { atual: '', nova: '', confirmacao: '' }

/**
 * Trocar a PRÓPRIA senha. Também é a tela de quem entrou com senha
 * provisória (a AreaLogada mostra esta página no lugar de todas as outras).
 */
export default function MinhaSenha() {
  const { usuario, trocarSenha } = useSessao()
  const navigate = useNavigate()

  const [campos, setCampos] = useState(EM_BRANCO)
  const [erros, setErros] = useState({})
  const [erroGeral, setErroGeral] = useState(null)
  const [enviando, setEnviando] = useState(false)

  const provisoria = usuario.trocar_senha

  function aoMudar(evento) {
    const { name, value } = evento.target
    setCampos((anteriores) => ({ ...anteriores, [name]: value }))
    if (erros[name]) setErros((anteriores) => ({ ...anteriores, [name]: undefined }))
  }

  async function aoEnviar(evento) {
    evento.preventDefault()
    setEnviando(true)
    setErroGeral(null)
    try {
      const mensagem = await trocarSenha(campos)
      // Com senha provisória, a AreaLogada já troca de tela sozinha
      // (usuario.trocar_senha virou false); o navigate leva para a lista.
      navigate('/pacientes', { replace: true, state: { mensagem } })
    } catch (e) {
      setErros(e.status === 422 ? e.dados.erros : {})
      setErroGeral(e.message)
      // Senha atual errada: apaga só ela. Não faz a pessoa redigitar tudo.
      if (e.dados?.erros?.atual) setCampos((c) => ({ ...c, atual: '' }))
      setEnviando(false)
    }
  }

  // Mesmo padrão do FormularioPaciente: as props comuns de cada campo
  const propsDoCampo = (nome) => ({
    id: nome,
    name: nome,
    type: 'password',
    value: campos[nome],
    onChange: aoMudar,
    ...marcarErro(nome, erros),
  })

  return (
    <div className="formulario-estreito">
      <h2>{provisoria ? 'Crie uma senha sua' : 'Minha senha'}</h2>

      {provisoria && (
        <p className="dica">
          Você entrou com uma senha provisória, definida pela administração.
          Crie uma senha que só você conheça para continuar.
        </p>
      )}

      {erroGeral && <p className="mensagem erro">{erroGeral}</p>}

      <form onSubmit={aoEnviar} className="formulario" noValidate>
        <label htmlFor="atual">
          {provisoria ? 'Senha provisória (a que você recebeu)' : 'Senha atual'}
        </label>
        <input {...propsDoCampo('atual')} autoComplete="current-password" autoFocus />
        <ErroDoCampo campo="atual" erros={erros} />

        <label htmlFor="nova">Nova senha <small>(mínimo 8 caracteres)</small></label>
        <input {...propsDoCampo('nova')} autoComplete="new-password" />
        <ErroDoCampo campo="nova" erros={erros} />

        <label htmlFor="confirmacao">Repita a nova senha</label>
        <input {...propsDoCampo('confirmacao')} autoComplete="new-password" />
        <ErroDoCampo campo="confirmacao" erros={erros} />

        <button type="submit" className="principal" disabled={enviando}>
          {enviando ? 'Trocando...' : 'Trocar senha'}
        </button>
      </form>
    </div>
  )
}
