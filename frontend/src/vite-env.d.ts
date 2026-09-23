/// <reference types="vite/client" />

// App-specific env vars. MOCK toggles the demo data layer (src/mocks).
interface ImportMetaEnv {
  readonly VITE_MOCK?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
