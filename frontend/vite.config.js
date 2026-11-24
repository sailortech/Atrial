import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Endereço do Flask. ATRIAL_BACKEND troca, se precisar
// (ex.: um Flask de teste em outra porta). O padrão é :5000.
const backend = process.env.ATRIAL_BACKEND ?? 'http://127.0.0.1:5000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  server: {
    // Proxy: o React roda em http://localhost:5173 e o Flask em :5000.
    // Quando o React pede "/api/..." ou "/painel/dados", o Vite repassa
    // o pedido para o Flask. Para o navegador, parece tudo um site só:
    // por isso o cookie de login do Flask funciona aqui também.
    proxy: {
      '/api': backend,
      '/painel/dados': backend,
    },
  },
})
