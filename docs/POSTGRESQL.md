# PostgreSQL local opcional

SQLite sigue siendo la opción predeterminada. PostgreSQL no añade una suscripción ni convierte la instalación en un servicio alojado.

Crea un archivo privado con una contraseña aleatoria y define `POSTGRES_PASSWORD_FILE` con su ruta absoluta. No lo guardes en el repositorio. Luego ejecuta:

```sh
docker compose -f compose.yaml -f compose.postgres.yaml up --build -d
```

El servicio PostgreSQL no publica puertos. El inicializador root lee únicamente el archivo de contraseña explícito, que puede conservar permisos 0600 en el anfitrión. Copia la contraseña a dos volúmenes privados separados: uno para PostgreSQL (UID 999) y otro para la aplicación (UID 10001), con directorios 0700 y archivos 0600. Los servicios los montan de solo lectura; no reciben otros secretos del anfitrión. Cambiar el archivo no cambia automáticamente la contraseña de una base existente: una discrepancia detiene la inicialización y exige una rotación explícita. La imagen oficial está fijada por digest; la cola usa transacciones cortas y un bloqueo asesor impide dos workers locales. Mantén una base propia por instalación y evita compartirla entre instalaciones activas.

Pruebas sin credenciales personales:

```sh
sh scripts/test-postgres.sh
```

## Migrar desde SQLite

1. Detén backend y worker y crea el backup consistente descrito en OPERATIONS.md. Conserva el origen y comprueba el manifiesto/checksums.
2. Inicializa un destino PostgreSQL vacío mediante Compose. No reutilices una base con datos. Detén sus servicios de aplicación antes de importar.
3. Copia el backup al contenedor de mantenimiento y utiliza `restore`: verifica el archivo, importa la instantánea SQLite a PostgreSQL y restaura los archivos de los volúmenes. El esquema del destino debe estar migrado.
4. El importador conserva identificadores, originales, revisiones y relaciones, comprueba recuentos y hashes lógicos y rechaza destinos no vacíos. La transacción revierte ante error.
5. Conecta de nuevo ChatGPT si se trata de otra instalación. Los backups excluyen credenciales y no transfieren OAuth.

Para importar únicamente una copia de la base, el comando del contenedor es `python -m app.migrate_database --source /tmp/snapshot.sqlite3`; los archivos multimedia/transcripciones/exportaciones deben transferirse con el backup completo. Nunca pases la base SQLite en uso como origen de una migración.

El backup de PostgreSQL local genera una instantánea SQLite portable con el esquema vigente, además de los archivos, para reutilizar la comprobación de integridad y el formato de restauración. No utiliza ni requiere herramientas PostgreSQL en el anfitrión.
