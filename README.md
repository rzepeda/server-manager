# Server Deployment Manager

Gestor automatizado para despliegues locales basados en Docker, GitHub Container Registry (GHCR) y Caddy.

## Estructura en el Servidor
- `/server/apps/`: Directorio donde se clonan los repositorios o se alojan los `deploy.yml`.
- `/server/secrets/`: Archivos `.env` con credenciales de entorno fuera de Git.
- `/server/caddy/sites/`: Configuración dinámica de subdominios generada por el manager.
- `/server/data/apks/`: Almacén persistente de APKs extraídas para distribución estática.

## Guías de Referencia
- [Guía de Instalación del Servidor](homeserver_setup_guide.md): Puesta a punto de Caddy, Cloudflare Tunnel y Deployment Manager.
- [Guía de Actualización de Aplicaciones (APK Hub)](app_update_guide.md): Instrucciones para actualizar apps y distribuir APKs nativas automáticamente.

## Despliegue del Manager
```bash
docker compose up -d --build
```
