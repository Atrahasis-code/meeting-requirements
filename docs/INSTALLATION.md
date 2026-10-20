# Instalación por plataforma

## Windows con WSL2

Instala Docker Desktop, activa su backend WSL2 y la integración con tu distribución. Ejecuta los comandos Compose desde esa distribución, preferentemente con el repositorio dentro del filesystem Linux, no una carpeta corporativa sincronizada. Comprueba `docker version` y `docker compose version`.

No instales Python, Node ni FFmpeg en Windows o WSL para ejecutar la aplicación. No montes el socket Docker dentro de contenedores. Los volúmenes nombrados se alojan en el almacenamiento local de Docker.

Si Docker informa un fallo del helper de credenciales de Windows desde WSL, comprueba la integración de Docker Desktop y el contexto: `docker context ls`. El contexto `default` debe acceder al engine disponible. Los permisos elevados no sustituyen una integración WSL incorrecta.

La siguiente configuración de `%UserProfile%/.wslconfig` es una referencia opcional, no un cambio aplicado por la aplicación:

```ini
[wsl2]
memory=5GB
processors=4
swap=2GB
```

Después de modificarla manualmente, `wsl --shutdown` detiene todas las distribuciones. Estos límites afectan a todas las distribuciones y servicios WSL2. El conjunto de contenedores y sus compilaciones necesita memoria adicional al límite del worker; aumenta la memoria de Docker si la construcción se queda sin recursos.

## Linux

Instala Docker Engine y el plugin Docker Compose. Comprueba que tu usuario tiene acceso al daemon mediante la configuración de Docker de tu distribución. No cambies permisos del socket a `777`. No se requiere instalar el stack de desarrollo del proyecto.

## macOS Intel y Apple Silicon

Instala Docker Desktop y habilita Compose. El proyecto deja que Docker seleccione la arquitectura nativa: no fuerza `platform: linux/amd64` en Apple Silicon.

Las imágenes base y las principales dependencias nativas publican variantes Linux amd64 y arm64. Esto no constituye una prueba de ejecución de esta aplicación en macOS. Consulta el registro de comprobaciones para distinguir construcción, emulación y ejecución nativa. La compatibilidad con cada plataforma se declara únicamente tras probarla.

## Configuración común

```sh
docker compose up --build -d
docker compose ps
docker compose logs -f
```

Abre exactamente `http://127.0.0.1:8080`. Usa esa dirección también para OAuth; `localhost` es un host distinto para cookies y no sustituye al callback registrado. Si cambias APP_PORT, recrea los servicios y usa el puerto nuevo.

El servicio initialize prepara volúmenes con UID/GID 10001 y ejecuta Alembic después de abandonar root. Los procesos principales son no root. Un error de migración impide arrancar API/worker; conserva los datos y revisa logs antes de reintentar.

Para cambiar CPU/RAM, edita `.env` y ejecuta `docker compose up -d --force-recreate`. Los límites de ejecución no limitan automáticamente la memoria de las construcciones BuildKit. El perfil Calidad puede exceder 3 GiB y terminar por OOM; aumenta WORKER_MEM_LIMIT o utiliza Equilibrado/Económico.

Una descarga interrumpida de modelos se reintenta desde el caché al iniciar otra transcripción. Los errores de red no autorizan envío de audio a terceros.
