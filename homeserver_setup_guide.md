# Guía de Instalación, Ejecución y Solución de Problemas: Homeserver Deployment Manager

Esta guía detalla los pasos necesarios para desplegar y poner en marcha el gestor de contenedores automatizado en tu servidor casero (`homeserver`), la configuración del enrutamiento web y las soluciones a los problemas comunes.

## 1. Requisitos Previos en el Servidor

Asegúrate de que tu `homeserver` (con Debian/Ubuntu o distribución Linux compatible) cuenta con el software base instalado:

* **Docker Engine** y **Docker Compose**
* **Git**
* El CLI de GitHub (`gh`) autenticado.
* Una cuenta de **Cloudflare Zero Trust** para exponer los servicios.

## 2. Preparar el Entorno en el Servidor

Crea la estructura de directorios y redes necesarias que utilizará el gestor en el disco de tu servidor:

```bash
# 1. Crear directorios base para aplicaciones, secretos, APKs y configuraciones de Caddy
sudo mkdir -p /server/apps
sudo mkdir -p /server/secrets
sudo mkdir -p /server/caddy/sites
sudo mkdir -p /server/data/apks

# 2. Crear las redes Docker aisladas de la arquitectura homeserver
sudo docker network create homeserver-public
sudo docker network create homeserver-data
```

## 3. Configuración de Enrutamiento (Caddy + Cloudflare)

Para gestionar el tráfico entrante de forma segura sin abrir puertos en el router, utilizamos **Caddy** como proxy inverso y **Cloudflare Tunnels**.

### A. Estructura de Directorios
Crea el directorio base para el proxy y otórgale permisos a tu usuario:
```bash
sudo mkdir -p /opt/caddy
sudo chown -R $USER:$USER /opt/caddy
cd /opt/caddy
```

### B. Variables de Entorno (.env)
Para mantener seguro el token del túnel, crea un archivo `.env`:
```bash
nano .env
```
Añade tu token de Cloudflare Zero Trust:
```env
TUNNEL_TOKEN=tu_token_largo_de_cloudflare_aqui
```

### C. Configuración de Caddy (Caddyfile)
Crea el archivo principal de Caddy. Este archivo está configurado para leer dinámicamente las rutas que genera nuestro Gestor de Despliegues:
```bash
nano Caddyfile
```
```caddyfile
import /etc/caddy/sites/*.caddy
```

### D. Archivo Docker Compose
Crea el archivo `docker-compose.yml` que levantará tanto el proxy como el túnel:
```bash
nano docker-compose.yml
```
```yaml
services:
  caddy:
    image: caddy:2
    container_name: caddy-proxy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - /server/caddy/sites:/etc/caddy/sites:ro
      - /server/data/apks:/var/www/apks:ro
      - caddy_data:/data
      - caddy_config:/config
    networks:
      - homeserver-public

  cloudflared:
    image: cloudflare/cloudflared:latest
    container_name: cloudflared-caddy
    restart: unless-stopped
    command: tunnel run
    env_file:
      - .env
    networks:
      - homeserver-public

volumes:
  caddy_data:
  caddy_config:

networks:
  homeserver-public:
    external: true
```

### E. Despliegue
Levanta los servicios en segundo plano:
```bash
docker compose up -d
```
> **Nota de Enrutamiento:** En el dashboard de Cloudflare Zero Trust, al configurar el *Public Hostname* de tus aplicaciones, el Service URL siempre debe apuntar a `http://caddy-proxy:80`.

## 4. Clonar el Repositorio del Gestor

Si utilizas el CLI de GitHub autenticado con tu cuenta, clona el repositorio en tu directorio personal primero para evitar problemas de permisos con `root`, y luego muévelo a `/opt`:

```bash
# 1. Clonar en el directorio del usuario actual
git clone https://github.com/rzepeda/server-manager.git ~/server-manager

# 2. Mover a la ruta de producción en /opt
sudo mv ~/server-manager /opt/server-manager
cd /opt/server-manager
```

## 5. Configurar las Variables de Entorno del Gestor

Crea un archivo `.env` en la raíz de `server-manager` para definir tu dominio base y el intervalo de verificación:

```bash
CHECK_INTERVAL=30
DOMAIN_BASE=agentictools.uk
```

## 6. Ejecutar el Deployment Manager

Levanta el servicio utilizando Docker Compose en segundo plano (recuerda usar `--build` para asegurarte de tener la última versión del código):

```bash
docker compose up -d --build
```

## 7. Verificación y Monitoreo

Para comprobar que el Deployment Manager está corriendo correctamente y observando los repositorios, revisa sus logs en tiempo real:

```bash
docker logs -f homeserver-deployment-manager
```

## 8. Resolución de Problemas Frecuentes (Troubleshooting)

### A. Error de permisos al conectar con el socket de Docker

* **Síntoma:** `permission denied while trying to connect to the docker API at unix:///var/run/docker.sock`
* **Solución:** Tu usuario actual no forma parte del grupo de Docker. Añádelo y actualiza la sesión con:
  ```bash
  sudo usermod -aG docker $USER
  newgrp docker
  ```

### B. El comando `docker compose build` requiere Buildx 0.17.0+

* **Síntoma:** `compose build requires buildx 0.17.0 or later` o no se encuentra el paquete en sistemas como Debian Trixie.
* **Solución:** Instala manualmente el plugin de Buildx directamente en tu directorio de usuario de Docker:
  ```bash
  mkdir -p ~/.docker/cli-plugins
  curl -SL https://github.com/docker/buildx/releases/download/v0.17.1/buildx-v0.17.1.linux-amd64 -o ~/.docker/cli-plugins/docker-buildx
  chmod +x ~/.docker/cli-plugins/docker-buildx
  ```

### C. Error al clonar con `sudo git clone` pidiendo credenciales de GitHub

* **Síntoma:** El sistema solicita contraseña o credenciales al clonar el repositorio protegido.
* **Solución:** Recuerda que `gh auth login` guarda las credenciales asociadas al usuario actual (`rizepe`), no a `root`. Realiza siempre el `git clone` sin `sudo` en tu carpeta de usuario y luego muévelo con `sudo mv`.

### D. Falta el archivo `requirements.txt` durante el build

* **Síntoma:** `failed to solve: failed to compute cache key: "/requirements.txt": not found`
* **Solución:** Asegúrate de que todos los archivos del repositorio (`Dockerfile`, `requirements.txt`, `manager.py`, `docker-compose.yml`) estén creados y guardados dentro de `/opt/server-manager` antes de ejecutar el comando de construcción.

### E. Bucle de redirección en el navegador (ERR_TOO_MANY_REDIRECTS)

* **Síntoma:** La página no carga en el navegador y marca demasiadas redirecciones.
* **Solución:** Ocurre porque Cloudflare gestiona el HTTPS, pero Caddy intenta forzarlo localmente. Asegúrate de que en tu archivo `manager.py` la configuración generada para Caddy empiece explícitamente con `http://` (ejemplo: `http://{subdomain}.{domain_base} {`).