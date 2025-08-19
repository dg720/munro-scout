/// <reference types="vite/client" />

// (Optional) be explicit about the env you use
interface ImportMetaEnv {
  readonly VITE_API_BASE?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
