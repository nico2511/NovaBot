/**
 * Dynamic API Configuration
 * Détecte automatiquement l'IP du serveur depuis l'URL du navigateur
 * Permet l'accès depuis mobile/réseau local sans configuration manuelle
 */

export function getApiUrl(): string {
    // SSR (Server-Side Rendering) - Next.js build time
    if (typeof window === 'undefined') {
        return 'http://localhost:8001'
    }

    // Client-Side - Runtime Discovery
    // Si l'utilisateur accède via http://10.10.20.76:3000
    // L'API sera automatiquement http://10.10.20.76:8001
    const hostname = window.location.hostname
    return `http://${hostname}:8001`
}
