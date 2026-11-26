import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Endereço do Flask. ATRIAL_BACKEND troca, se precisar
// (ex.: um Flask de teste em outra porta). O padrão é :5000.
const backend = process.env.ATRIAL_BACKEND ?? 'http://127.0.0.1:5000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  // O React mora em /app/ (é onde o Flask entrega o build pronto).
  // O Vite põe esse começo nos endereços dos arquivos gerados, e o
  // App.jsx avisa o React Router (import.meta.env.BASE_URL).
  // No desenvolvimento, o endereço fica http://localhost:5173/app/
  base: '/app/',

  // Testes automáticos (npm test). O Vitest usa esta mesma configuração.
  test: {
    // jsdom = um navegador "de mentira", sem janela, para desenhar os componentes
    environment: 'jsdom',
    // Roda antes de cada arquivo de teste (como o conftest.py do pytest)
    setupFiles: ['./src/testes/preparar.js'],
  },

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
