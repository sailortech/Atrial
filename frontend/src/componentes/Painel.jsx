import { useEffect, useRef } from 'react'

import usePainel from '../hooks/usePainel.js'
import useSom from '../hooks/useSom.js'
import ChamadaAtual from './ChamadaAtual.jsx'
import Relogio from './Relogio.jsx'
import UltimasChamadas from './UltimasChamadas.jsx'

/**
 * A tela inteira da TV. Junta os pedaços (componentes) e decide
 * quando tocar o som. Os dados vêm do hook usePainel().
 */
export default function Painel() {
  const { dados, semConexao } = usePainel()
  // Desmontando o objeto: { ativo, ativar, tocar } viram variáveis soltas
  const { ativo: somAtivo, ativar: ativarSom, tocar } = useSom()

  const chave = dados?.atual?.chave ?? null // ?. = "se existir"

  // Toca o som quando a chave da chamada MUDA (alguém foi chamado).
  // Na primeira carga não toca: a TV acabou de ligar, ninguém foi
  // chamado "agora". useRef lembra a chave anterior entre desenhos.
  const chaveAnterior = useRef(undefined)
  useEffect(() => {
    if (dados === null) return // ainda carregando

    const primeiraCarga = chaveAnterior.current === undefined
    if (!primeiraCarga && chave && chave !== chaveAnterior.current) {
      tocar()
    }
    chaveAnterior.current = chave
    // Lista de dependências: o efeito roda de novo quando algum destes
    // valores muda. tocar é sempre a mesma função (useCallback no useSom).
  }, [dados, chave, tocar])

  return (
    <div className="painel">
      <header className="topo">
        <span>Atrial</span>

        {/* Mostra o botão só enquanto o som não foi ativado */}
        {!somAtivo && (
          <button type="button" className="botao-som" onClick={ativarSom}>
            🔇 Ativar som
          </button>
        )}

        {semConexao && <span className="sem-conexao">⚠ sem conexão</span>}

        <Relogio />
      </header>

      {dados === null ? (
        <div className="atual">
          <p className="rotulo">Carregando...</p>
        </div>
      ) : (
        // key={chave}: chamada nova = componente novo = pisca de novo
        <ChamadaAtual key={chave} chamada={dados.atual} />
      )}

      <footer className="rodape">
        <UltimasChamadas chamadas={dados?.anteriores ?? []} />

        <div className="contador">
          <p className="rotulo">Na fila</p>
          <p className="numero">{dados?.aguardando ?? '-'}</p>
        </div>
      </footer>
    </div>
  )
}
