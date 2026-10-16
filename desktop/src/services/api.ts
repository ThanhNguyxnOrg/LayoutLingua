/**
 * Centralized API configuration for LayoutLingua.
 * Resolves API requests to the Python core engine (default: http://127.0.0.1:8765).
 */

export const API_BASE = 'http://127.0.0.1:8765'

export function apiUrl(endpoint: string): string {
  const cleanEndpoint = endpoint.startsWith('/') ? endpoint : `/${endpoint}`
  return `${API_BASE}${cleanEndpoint}`
}
