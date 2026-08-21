// Shared ApiError → Spanish copy. Views with context-specific timeout
// guidance (e.g. ingest may have partially saved data) keep their own
// timeout branch via INGEST_TIMEOUT_COPY.
import type { ApiError } from './api'

export const GENERIC_TIMEOUT_COPY =
  'La consulta tardó demasiado. Probá de nuevo.'

export const INGEST_TIMEOUT_COPY =
  'La búsqueda tardó demasiado. El jugador quizás ya se esté procesando; probá de nuevo en unos minutos.'

export function errorCopy(err: ApiError): string {
  switch (err.kind) {
    case 'timeout':
      return GENERIC_TIMEOUT_COPY
    case 'network':
      return 'No hay conexión con el backend. Verificá que esté corriendo.'
    case 'server':
      return 'El servidor no pudo procesar la solicitud. Probá de nuevo.'
    case 'auth':
      return 'Se requiere una API key. Configurala en Ajustes.'
    default:
      return 'Ocurrió un error inesperado.'
  }
}
