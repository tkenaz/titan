/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_HMAC_SECRET: string
  readonly VITE_ADMIN_TOKEN: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
