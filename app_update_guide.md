# Guía de Actualización de Aplicaciones: Integración con el Hub de APKs

Esta guía describe paso a paso cómo actualizar una aplicación existente (o una basada en `server-app-starter`) para que compile, empaquete y distribuya automáticamente su binario **Android APK** a través del Hub de APKs (`https://apks.agentictools.uk`) usando el `server-manager`.

---

## Índice
1. [Resumen del Flujo de Distribución](#1-resumen-del-flujo-de-distribución)
2. [Paso 1: Actualizar `deploy.yml`](#paso-1-actualizar-deployyml)
3. [Paso 2: Actualizar el `Dockerfile`](#paso-2-actualizar-el-dockerfile)
4. [Paso 3: Actualizar el Flujo de CI/CD (`publish-image.yml`)](#paso-3-actualizar-el-flujo-de-cicd-publish-imageyml)
5. [Paso 4: Adaptar el Código Dart/Flutter](#paso-4-adaptar-el-código-dartflutter)
6. [Paso 5: Permisos de Red en Android](#paso-5-permisos-de-red-en-android)
7. [Paso 6: Despliegue y Verificación](#paso-6-despliegue-y-verificación)
8. [Resolución de Problemas Comunes](#resolución-de-problemas-comunes)

---

## 1. Resumen del Flujo de Distribución

El objetivo es no necesitar servidores SSH, buckets S3 ni procesos manuales:
1. **GitHub Actions** compila la Web de Flutter y, en la rama `main` (o mediante ejecución manual), compila el archivo `app-release.apk`.
2. El `Dockerfile` copia dicho `.apk` dentro de la imagen Docker en `/app/app-release.apk`.
3. Al publicar la imagen, `server-manager` detecta la actualización en tu homeserver, extrae el archivo APK mediante la API de Docker y lo deposita en `/server/data/apks/<nombre-app>.apk`.
4. El proxy **Caddy** expone ese directorio de forma estática en `https://apks.agentictools.uk`.

---

## Paso 1: Actualizar `deploy.yml`

En el repositorio de tu aplicación, localiza o crea el archivo `deploy.yml` y añade la sección `apk`:

```yaml
version: 1
name: tu-aplicacion             # Nombre de la app (el APK se publicará como tu-aplicacion.apk)
image: ghcr.io/tu-usuario/tu-aplicacion:main
container_name: srv-tu-aplicacion
container_port: 8000

public:
  enabled: true
  subdomain: tu-subdominio      # Accesible en tu-subdominio.agentictools.uk

database:
  postgres: true                # Si requiere base de datos

apk:
  enabled: true                 # <-- ACTIVA la extracción del APK en server-manager
  container_path: "/app/app-release.apk" # Ruta interna donde el Dockerfile guardó el APK
```

---

## Paso 2: Actualizar el `Dockerfile`

Tu imagen Docker empaqueta el backend y la web frontend. Añade una instrucción `COPY` para absorber también el APK dentro del contenedor:

```dockerfile
# ... (Pasos de compilación / setup del backend) ...

# Copiar el APK compilado por el pipeline al filesystem del contenedor
COPY app/frontend/app-release.apk /app/app-release.apk

# ... (CMD o ENTRYPOINT para iniciar el servicio) ...
```

> **Nota:** Si la estructura de carpetas de tu proyecto ubica el frontend en la raíz o en `./frontend`, ajusta la ruta de origen en el `COPY` (por ejemplo: `COPY frontend/app-release.apk /app/app-release.apk`).

---

## Paso 3: Actualizar el Flujo de CI/CD (`publish-image.yml`)

Reemplaza o adapta `.github/workflows/publish-image.yml` en la raíz de tu repositorio. Este flujo compila el APK sólo en `main` o al dispararse manualmente, ahorrando tiempo en `dev`:

```yaml
name: Build and Publish Docker Image

on:
  push:
    branches:
      - main
      - dev
  workflow_dispatch:
    inputs:
      force_apk:
        description: 'Compilar APK en rama de prueba'
        required: false
        type: boolean
        default: true

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout código
        uses: actions/checkout@v4

      # 1. Configurar Java JDK (indispensable para compilar Android)
      - name: Configurar Java JDK
        uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '17'
          cache: 'gradle'

      # 2. Configurar Flutter SDK
      - name: Configurar Flutter
        uses: subosito/flutter-action@v2
        with:
          channel: 'stable'
          cache: true

      - name: Descargar dependencias de Flutter
        working-directory: app/frontend  # Ajustar a la ruta de tu frontend Flutter
        run: flutter pub get

      # 3. Compilación de Flutter Web (siempre activa)
      - name: Compilar Flutter Web
        working-directory: app/frontend
        run: flutter build web --release

      # 4. Compilación condicional de APK (solo en main o ejecución manual)
      - name: Compilar Flutter APK
        if: github.ref_name == 'main' || github.event_name == 'workflow_dispatch'
        working-directory: app/frontend
        run: |
          # Inyectar dinámicamente la URL del backend según la rama
          if [ "${{ github.ref_name }}" = "main" ]; then
            API_URL="https://${{ github.event.repository.name }}.agentictools.uk"
          else
            API_URL="https://dev-${{ github.event.repository.name }}.agentictools.uk"
          fi
          echo "Compilando APK apuntando a: $API_URL"
          
          flutter build apk --release --dart-define=API_BASE_URL=$API_URL
          
          # Mover el binario generado a la ubicación estándar para el Dockerfile
          cp build/app/outputs/flutter-apk/app-release.apk ./app-release.apk

      # 5. Crear APK simulado si la compilación se omitió (evita error en Docker COPY)
      - name: Crear Mock APK si no compila
        if: github.ref_name != 'main' && github.event_name != 'workflow_dispatch'
        working-directory: app/frontend
        run: touch ./app-release.apk

      # 6. Configurar Docker Buildx y Autenticar con GHCR
      - name: Configurar Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Iniciar sesión en GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      # 7. Construir y Publicar la Imagen Docker
      - name: Construir y Publicar Imagen Docker
        uses: docker/build-push-action@v6
        with:
          context: .
          push: true
          tags: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.ref_name }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

---

## Paso 4: Adaptar el Código Dart/Flutter

Para que la aplicación Android sepa a qué servidor comunicarse sin tener URLs fijas (hardcodeadas), lee la variable inyectada `--dart-define=API_BASE_URL`.

### 1. Crear clase de configuración (`lib/config/api_config.dart`)

```dart
class ApiConfig {
  /// Valor inyectado en tiempo de compilación mediante --dart-define=API_BASE_URL=...
  /// Si no se pasa (por ejemplo en desarrollo local), toma un fallback adecuado.
  static const String _rawBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000', // 10.0.2.2 apunta al host en emulador Android
  );

  /// URL limpia sin barra final
  static String get baseUrl {
    if (_rawBaseUrl.endsWith('/')) {
      return _rawBaseUrl.substring(0, _rawBaseUrl.length - 1);
    }
    return _rawBaseUrl;
  }

  /// Construye un Uri completo para peticiones HTTP
  static Uri endpoint(String path) {
    final cleanPath = path.startsWith('/') ? path : '/$path';
    return Uri.parse('$baseUrl$cleanPath');
  }
}
```

### 2. Uso en tus llamadas HTTP

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:tu_app/config/api_config.dart';

Future<void> login(String email, String password) async {
  final url = ApiConfig.endpoint('/api/auth/login');
  
  final response = await http.post(
    url,
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({'email': email, 'password': password}),
  );
  
  // Procesar respuesta...
}
```

---

## Paso 5: Permisos de Red en Android

Por defecto, los proyectos Flutter en Android requieren permiso explícito para conectarse a Internet en modo Release.

Asegúrate de que en `android/app/src/main/AndroidManifest.xml` figure la siguiente línea antes de la etiqueta `<application>`:

```xml
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <!-- Permiso obligatorio para llamadas de red en el APK -->
    <uses-permission android:name="android.permission.INTERNET" />

    <application
        android:label="TuApp"
        android:name="${applicationName}"
        android:icon="@mipmap/ic_launcher">
        <!-- ... -->
    </application>
</manifest>
```

---

## Paso 6: Despliegue y Verificación

1. **Hacer commit y push a la rama `main`:**
   ```bash
   git add .
   git commit -m "feat: soporte para distribución de APK nativa"
   git push origin main
   ```
2. **Revisar GitHub Actions:** Verifica que el paso `Build Flutter APK` se ejecute satisfactoriamente y que la imagen Docker se suba a GHCR.
3. **Monitorear `server-manager` en el servidor casero:**
   Conéctate al servidor y revisa los logs del gestor:
   ```bash
   docker logs -f homeserver-deployment-manager
   ```
   Verás mensajes similares a:
   ```text
   📦 Verificando aplicación: tu-aplicacion
   🔄 Reemplazando contenedor existente...
   🚀 Iniciando contenedor srv-tu-aplicacion...
   📦 Extrayendo APK desde /app/app-release.apk...
   ✅ APK tu-aplicacion.apk extraído y publicado en el Hub.
   ```
4. **Comprobar la descarga pública:**
   - Abre tu navegador en: `https://apks.agentictools.uk`
   - Deberás ver `tu-aplicacion.apk` disponible en la lista de archivos estáticos de Caddy.

---

## Resolución de Problemas Comunes

| Síntoma | Causa Probable | Solución |
| :--- | :--- | :--- |
| `failed to compute cache key: "app-release.apk": not found` en GitHub Action | El paso de compilación del APK se saltó o falló y no se creó el mock. | Verifica que el paso `Mock APK if skipped` exista con `touch ./app-release.apk` en la misma ruta donde el `Dockerfile` lo busca. |
| `⚠️ No se pudo extraer el APK` en logs de `manager.py` | La ruta `container_path` en `deploy.yml` no coincide con donde el `Dockerfile` colocó el archivo. | Confirma que `container_path` en `deploy.yml` sea `/app/app-release.apk` y que el `Dockerfile` haga `COPY ... /app/app-release.apk`. |
| `SocketException: Connection failed` dentro de la app Android | Falta el permiso de Internet en el manifiesto de Android. | Agrega `<uses-permission android:name="android.permission.INTERNET" />` en `android/app/src/main/AndroidManifest.xml`. |
| La app móvil intenta conectar a `http://10.0.2.2:8000` en producción | No se compiló con `--dart-define=API_BASE_URL` o no se usó `ApiConfig.baseUrl`. | Verifica que el comando de Flutter en el workflow incluya `--dart-define=API_BASE_URL=$API_URL`. |
| El archivo no aparece en `https://apks.agentictools.uk` | Falta el volumen `/server/data/apks` en el contenedor de Caddy o en deployment manager. | Confirma en `caddy/docker-compose.yml` la línea `- /server/data/apks:/var/www/apks:ro` y reinicia el servicio con `docker compose up -d`. |
