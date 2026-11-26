/**
 * Roda antes de cada arquivo de teste (é o "conftest.py" do Vitest;
 * ligado em vite.config.js, em test.setupFiles).
 */
import '@testing-library/jest-dom/vitest' // expect(...).toBeInTheDocument() e afins
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

afterEach(() => {
  cleanup() // desmonta o que o teste desenhou: cada teste começa do zero
  vi.unstubAllGlobals() // desfaz o fetch falso (veja simularApi.js)
  vi.restoreAllMocks()
})
