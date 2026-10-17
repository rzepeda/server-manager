# Guía de Instalación y Ejecución: Homeserver Deployment Manager

Esta guía detalla los pasos necesarios para desplegar y poner en marcha el gestor de contenedores automatizado en tu servidor casero (`homeserver`).

---

## 1. Requisitos Previos en el Servidor
Asegúrate de que tu `homeserver` (con Ubuntu u otra distribución Linux) cuenta con el software base instalado:
* **Docker Engine** y el plugin de **Docker Compose**
* **Git**
* Un servidor proxy inverso **Caddy** instalado globalmente en el host (o corriendo como contenedor gestionado).

---

## 2. Preparar el Entorno en el Servidor
Crea la estructura de directorios y redes necesarias que utilizará el gestor en el disco de tu servidor:

```bash
# 1. Crear directorios base para aplicaciones, secretos y configuraciones de Caddy
sudo mkdir -p /server/apps
sudo mkdir -p /server/secrets
sudo mkdir -p /server/caddy/sites

# 2. Crear las redes Docker aisladas de la arquitectura homeserver
sudo docker network create homeserver-public
sudo docker network create homeserver-data
```

---

## 3. Clonar el Repositorio
Clona tu repositorio `server-manager` dentro del servidor (por ejemplo, en una ruta como `/opt/server-manager` o en tu directorio personal):

```bash
git clone https://github.com/rzepeda/server-manager.git /opt/server-manager
cd /opt/server-manager
```

---

## 4. Configurar las Variables de Entorno (Opcional)
Si deseas ajustar el intervalo de revisión o el dominio base para los subdominios generados automáticamente por Caddy, puedes crear un archivo `.env` en la raíz de `server-manager` dentro del servidor:

```env
CHECK_INTERVAL=30
DOMAIN_BASE=tudominio.cl
```

---

## 5. Ejecutar el Deployment Manager
Una vez clonado el repositorio y con las redes Docker creadas, levanta el servicio utilizando Docker Compose en segundo plano:

```bash
docker compose up -d --build
```

---

## 6. Verificación y Monitoreo
Para comprobar que el Deployment Manager está corriendo correctamente y observando los repositorios, revisa sus logs en tiempo real:

```bash
docker logs -f homeserver-deployment-manager
```

Deberías ver un mensaje indicando que el gestor se ha iniciado y está revisando periódicamente la carpeta `/server/apps`.