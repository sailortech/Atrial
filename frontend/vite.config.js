import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  server: {
    // Proxy: o React roda em http://localhost:5173 e o Flask em :5000.
    // Quando o React pede "/painel/dados", o Vite repassa o pedido para
    // o Flask. Para o navegador, parece tudo um site só (sem CORS).
    //
    // ATRIAL_BACKEND troca o endereço do Flask, se precisar
    // (ex.: um Flask de teste em outra porta). O padrão é :5000.
    proxy: {
      '/painel/dados': process.env.ATRIAL_BACKEND ?? 'http://127.0.0.1:5000',
    },
  },
})
