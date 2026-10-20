# Backup, restauración y migración

Las herramientas de mantenimiento corren dentro de contenedores; no requieren utilidades de Python ni tar en el host. Los ejemplos usan nombres de contenedores auxiliares exclusivos de esta operación. No utilices nombres que ya pertenezcan a otro trabajo.

## Backup consistente

Detén las escrituras y crea un archivo portable. No copies únicamente el archivo SQLite mientras los servicios escriben.

```sh
mkdir -p backups
docker compose stop backend worker
docker compose run --name mra-backup --no-deps maintenance backup /tmp/meeting-backup.tar.gz
docker cp mra-backup:/tmp/meeting-backup.tar.gz ./backups/meeting-backup.tar.gz
docker rm mra-backup
docker compose start backend worker
```

Para incluir modelos, añade `--include-models` al final del comando backup. Los enlaces internos del caché se guardan como archivos normales para permitir restauración sin red; esto puede aumentar el tamaño del paquete. Se excluyen los enlaces que apuntan fuera del volumen de modelos. El archivo contiene copia SQLite mediante su API de backup, archivos multimedia, transcripciones y exportaciones, más manifiesto y checksums SHA-256. No incluye autenticación ni tokens. Protege el backup porque sí contiene reuniones y datos corporativos. Guárdalo en `backups/`, excluido de Git y del contexto Docker. Los archivos `*.tar.gz` y `*.tgz` también se excluyen aunque se copien a otra carpeta; estas reglas no protegen archivos ya versionados ni sustituyen el control de acceso o cifrado del backup.

No reinicies servicios hasta que termine la copia; los archivos y la base deben pertenecer al mismo período de mantenimiento. El bloqueo impide hacer backup con el worker activo; el operador también debe detener la API.

## Restaurar en volúmenes nuevos

Selecciona un proyecto Compose nuevo; no sobrescribas una instalación con datos. Copia también el código/versión de la aplicación y los archivos de configuración no sensibles necesarios.

```sh
docker compose -p meeting-restored build backend worker frontend initialize maintenance
docker compose -p meeting-restored run --rm --no-deps initialize python -m app.initialize --prepare-only
docker compose -p meeting-restored run -d --name mra-restore --no-deps --entrypoint sleep maintenance infinity
docker cp ./backups/meeting-backup.tar.gz mra-restore:/tmp/meeting-backup.tar.gz
docker exec mra-restore python -m app.maintenance restore /tmp/meeting-backup.tar.gz
docker rm -f mra-restore
docker compose -p meeting-restored up -d
```

Detén antes la instalación original si ambas publican el mismo APP_PORT. La restauración rechaza volúmenes con datos, archivos con rutas inseguras, enlaces, entradas fuera de los directorios permitidos, checksums incorrectos y SQLite sin integridad referencial. El arranque posterior ejecuta Alembic y comprueba salud.

## Migrar entre equipos

1. Crea el backup consistente y lleva código, lockfiles y backup al equipo nuevo.
2. Instala Docker/Compose en el equipo nuevo. Construye nativamente para su arquitectura.
3. Restaura en volúmenes nuevos siguiendo el procedimiento anterior.
4. Configura recursos adecuados y verifica proyectos, reuniones, transcripciones, requisitos y exportaciones.
5. Conecta ChatGPT nuevamente. La instalación nueva crea un host ID distinto y no recibe tokens del equipo anterior.

Las sesiones de la instalación original permanecen allí hasta que las desconectes. No transfieras volúmenes de autenticación como parte del backup de datos. Conserva el backup original hasta terminar la validación. `docker compose down` conserva datos; `down -v` los elimina.

## Diagnóstico

`docker compose ps` muestra salud, `docker compose logs backend worker` las etapas/errores operativos y `docker stats` permite observar CPU/RAM. Un contenedor unhealthy no se reinicia automáticamente por el solo healthcheck; la política de reinicio actúa cuando el proceso termina. Si un trabajo fue interrumpido, reintenta desde la interfaz; no edites SQLite manualmente.

## Comprobaciones reproducibles

```sh
sh scripts/test.sh
sh scripts/test-operations.sh
sh scripts/test-worker-recovery.sh
sh scripts/check-platform.sh linux/amd64
sh scripts/check-platform.sh linux/arm64
```

La prueba de operaciones usa proyectos exclusivos con sufijo de proceso, verifica la exclusión de un segundo worker, crea datos sintéticos, transmite el backup entre contenedores, restaura y recrea servicios. Detiene sus contenedores al terminar y conserva los volúmenes para inspección. No accede a los datos normales.

La comprobación de plataforma carga imágenes locales y ejecuta imports nativos y FFmpeg. En un equipo amd64, ejecutar arm64 mediante QEMU constituye emulación. Esta comprobación no sustituye una inferencia real ni una prueba en macOS nativo.

La prueba de recuperación ejecuta únicamente Mock en un proyecto aislado, espera checkpoints, envía SIGKILL al worker y comprueba que el trabajo queda interrumpido sin perder los bloques confirmados ni reanudar inferencia automáticamente.
