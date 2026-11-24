// Ponto de partida: pega a <div id="root"> do index.html e
// manda o React desenhar o componente <App /> dentro dela.
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './app.css'
import './painel.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  // StrictMode: só no desenvolvimento, faz verificações extras para
  // avisar de erros comuns (por isso alguns efeitos rodam duas vezes)
  <StrictMode>
    <App />
  </StrictMode>,
)
