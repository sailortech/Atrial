import { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { api } from '../api.js'
import BarraDeChamada from '../componentes/pacientes/BarraDeChamada.jsx'
import TabelaEmAtendimento from '../componentes/pacientes/TabelaEmAtendimento.jsx'
import TabelaFila from '../componentes/pacientes/TabelaFila.jsx'
import TabelaHistorico from '../componentes/pacientes/TabelaHistorico.jsx'
import usePacientes from '../hooks/usePacientes.js'

/**
 * Tela de pacientes: chamar, atender e acompanhar a fila.
 *
 * Esta página "orquestra": guarda a busca e a mensagem de retorno, e
 * passa dados e funções para os componentes de cada parte da tela.
 */
export default function Pacientes() {
  // O que está no campo de busca (muda a cada tecla)...
  const [digitado, setDigitado] = useState('')
  // ...e o termo que é de fato buscado (só depois de uma pausa)
  const [termo, setTermo] = useState('')

  // "Debounce": espera 300 ms sem digitar antes de buscar, para não
  // mandar um pedido ao servidor a cada letra.
  useEffect(() => {
    const espera = setTimeout(() => setTermo(digitado.trim()), 300)
    return () => clearTimeout(espera) // digitou de novo? cancela a espera
  }, [digitado])

  const { dados, erro, recarregar } = usePacientes(termo)

  // Chegou aqui vindo do cadastro/edição? A mensagem veio no "state"
  // da navegação (veja NovoPaciente). Ela vira o valor INICIAL.
  const location = useLocation()
  const navigate = useNavigate()
  const recebida = location.state?.mensagem
  const [mensagem, setMensagem] = useState(
    recebida ? { tipo: 'sucesso', texto: recebida } : null, // { tipo, texto }
  )

  // ...e depois é apagada do histórico do navegador. Sem isto, ao
  // apertar F5 o "Paciente cadastrado" apareceria de novo.
  useEffect(() => {
    if (recebida) navigate(location.pathname, { replace: true, state: null })
  }, [recebida, location.pathname, navigate])

  /**
   * Executa uma ação no servidor e mostra o resultado.
   * Todas as ações (chamar, concluir...) passam por aqui.
   */
  async function executar(caminho, corpo) {
    try {
      const resposta = await api.post(caminho, corpo)
      setMensagem({ tipo: 'sucesso', texto: resposta.mensagem })
    } catch (e) {
      setMensagem({ tipo: 'erro', texto: e.message })
    }
    recarregar()
  }

  const acoes = {
    chamarProximo: (local) => executar('/api/pacientes/chamar-proximo', { local }),
    concluir: (id) => executar(`/api/pacientes/${id}/concluir`),
    chamarDeNovo: (id) => executar(`/api/pacientes/${id}/chamar-de-novo`),
    naoCompareceu: (id) => {
      if (window.confirm('Marcar este paciente como não compareceu?')) {
        executar(`/api/pacientes/${id}/nao-compareceu`)
      }
    },
  }

  if (!dados) {
    return <p className="carregando">{erro ?? 'Carregando...'}</p>
  }

  const encontrados = dados.em_atendimento.length + dados.fila.length + dados.historico.length

  return (
    <>
      <div className="titulo-com-acao">
        <h2>Pacientes</h2>
        <Link to="/pacientes/novo" className="botao principal">+ Cadastrar paciente</Link>
      </div>

      {mensagem && (
        <p className={`mensagem ${mensagem.tipo}`}>
          {mensagem.texto}
          <button type="button" className="fechar" onClick={() => setMensagem(null)}
                  aria-label="Fechar mensagem">×</button>
        </p>
      )}
      {erro && <p className="mensagem erro">{erro}</p>}

      <BarraDeChamada
        locais={dados.locais}
        ultimoLocal={dados.ultimo_local}
        totalNaFila={dados.total_na_fila}
        aoChamar={acoes.chamarProximo}
      />

      <input
        type="search"
        className="busca"
        placeholder="Buscar por nome ou CPF"
        value={digitado}
        onChange={(e) => setDigitado(e.target.value)}
      />
      {termo && (
        <p className="busca-ativa">
          {encontrados} encontrado(s) para <strong>"{termo}"</strong>.{' '}
          <button type="button" className="link" onClick={() => setDigitado('')}>
            Limpar busca
          </button>
        </p>
      )}

      <TabelaEmAtendimento pacientes={dados.em_atendimento} acoes={acoes} />
      <TabelaFila pacientes={dados.fila} />
      <TabelaHistorico pacientes={dados.historico} />
    </>
  )
}
