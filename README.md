# Server Deployment Manager

Gestor automatizado para despliegues locales basados en Docker, GitHub Container Registry (GHCR) y Caddy.

## Estructura en el Servidor
- `/server/apps/`: Directorio donde se clonarán los repositorios o se mantendrán los `deploy.yml`.
- `/server/secrets/`: Archivos `.env` con las credenciales fuera de Git.
- `/server/caddy/sites/`: Configuración dinámica de subdominios.

## Despliegue del Manager
```bash
docker compose up -d --build