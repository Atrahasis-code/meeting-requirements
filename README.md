# Meeting Requirements AI

Convierte grabaciones autorizadas de reuniones en especificaciones de requisitos revisables y con evidencia. Aplicación local de un solo usuario, interfaz en español y procesamiento manual.

## Arranque

Necesitas **Docker Engine/Desktop y Docker Compose v2.24.4 o posterior**. No necesitas instalar Python, Node.js, FFmpeg ni faster-whisper en el anfitrión.

```sh
docker compose up --build -d
docker compose ps
```

Abre [http://127.0.0.1:8080](http://127.0.0.1:8080). La primera construcción descarga imágenes y dependencias. Los modelos de transcripción se descargan solo al solicitar una transcripción real.

La configuración predeterminada funciona sin `.env`; para ajustar puertos o recursos, copia `.env.example` a `.env` y modifica sus valores. `.env` no debe contener API keys.

```sh
# Desarrollo con HMR React y recarga de la API
docker compose -f compose.yaml -f compose.dev.yaml up --build

# Detener conservando los datos
docker compose down

# Logs sin tokens ni contenido de reuniones
docker compose logs -f
```

El código del worker se monta durante desarrollo, pero requiere `docker compose restart worker` para aplicar cambios: el reinicio preserva los checkpoints. Las dependencias requieren reconstruir las imágenes. Usa siempre los mismos archivos Compose al detener el entorno de desarrollo.

## Flujo de trabajo

1. Crea un proyecto, su contexto y glosario.
2. Registra una reunión y carga un MP4, M4A, MP3 o WAV. Se valida el contenido real; el límite inicial es 4 GiB.
3. Inicia la transcripción. Solo un trabajo pesado se ejecuta a la vez. El perfil inicial usa `small`, CPU, INT8, tres hilos, beam 3 y VAD.
4. Revisa segmentos con el reproductor. Guarda correcciones; el texto original permanece conservado. Puedes marcar dudas y descargar TXT, JSON, SRT y VTT.
5. En Configuración, conecta ChatGPT, elige un modelo disponible y confirma manualmente que estableciste créditos en cero para esta aplicación en los controles de Uso de ChatGPT.
6. Desde la transcripción, revisa la entrada completa y autoriza el análisis. Nunca se envía audio. No se procesa automáticamente ninguna grabación.
7. Revisa evidencia, modifica requisitos y aprueba o rechaza manualmente. Los análisis posteriores son versiones independientes y requieren activación explícita.
8. Genera un paquete Markdown y descarga documentos individuales o ZIP. Cada exportación se conserva con un identificador nuevo.

El proveedor predeterminado es ChatGPT. Para probar sin autenticación, selecciona **Mock** explícitamente en Configuración. Los resultados simulados se etiquetan y no constituyen ingeniería de requisitos real. La transcripción simulada está restringida al entorno de pruebas; la aplicación normal usa faster-whisper.

## ChatGPT y privacidad

La autenticación usa Sign in with ChatGPT, registro dinámico, OAuth Authorization Code/PKCE y un almacenamiento de sesión exclusivo de la aplicación. No monta ni extrae credenciales del anfitrión. No existe alternativa automática con API keys.

La ruta oficial puede consumir plan o saldo de créditos según los controles de ChatGPT. Configura el límite de créditos de esta aplicación en **cero** antes de confirmar la política local. La confirmación es una declaración manual; el software no afirma verificar remotamente ese límite. La cuota se comparte según las reglas de tu cuenta. Al alcanzar un límite se conservan los trabajos y se bloquean nuevas inferencias; reanudar siempre es manual.

La elegibilidad de la cuenta y del entorno se comprueba con la autorización y con una inferencia real completada. Un catálogo de modelos o una conexión OAuth por sí solos no prueban acceso de inferencia. No se consideran verificadas cuentas que no hayan completado una solicitud real autorizada.

Usa únicamente grabaciones cuyo procesamiento esté autorizado por tu organización. No se eluden restricciones de Teams ni políticas corporativas. La interfaz y el backend solo se exponen en loopback; la API se escucha internamente en `0.0.0.0` para recibir el proxy de Compose, sin puerto publicado.

## Pruebas

```sh
docker compose -p meeting-ai-test -f compose.yaml -f compose.test.yaml run --build --rm backend pytest
sh scripts/test.sh
sh scripts/test-operations.sh
sh scripts/test-worker-recovery.sh
```

Las pruebas usan bases temporales incluso al ejecutar `pytest` con el servicio normal. El proyecto Compose de integración es independiente. La suite automatizada no requiere credenciales ni modelos. Usa ffprobe real con audio sintético y ejecuta el pipeline simulado en un worker separado.

```sh
# Comprobación opt-in de faster-whisper REAL en CPU; descarga small si hace falta
docker compose run --rm --no-deps worker python -m app.smoke_transcription
```

Para verificar también la fragmentación real, SQLite, los cuatro formatos y la exportación con análisis Mock:

```sh
docker compose run --rm --no-deps -e PYTHONPATH=/app worker python tests/real_pipeline_probe.py
```

Esta prueba usa datos temporales aislados y reutiliza únicamente el caché de modelos. La comprobación anterior requiere que los volúmenes hayan sido inicializados. No ejecuta análisis externo. Para verificar ChatGPT usa una transcripción sintética desde la interfaz, con tu autorización, modelo y política de consumo configurados.

Para crear datos sintéticos de demostración de forma explícita:

```sh
docker compose exec backend python -m app.seed
```

Cada ejecución crea un proyecto DEMO nuevo con una transcripción y resultados Mock identificados como simulación. No cambia el proveedor configurado ni envía información a ChatGPT.

## Documentación

- [Instalación por plataforma](docs/INSTALLATION.md)
- [Arquitectura, datos y API](docs/ARCHITECTURE.md)
- [Backup, restauración y migración](docs/OPERATIONS.md)
- [Autenticación y límites](docs/CHATGPT.md)
- [Seguridad y privacidad](docs/SECURITY.md)

La aplicación no incluye diarización ni consolidación inteligente entre reuniones. No cambia los límites de WSL2. No publica servicios ni crea repositorios remotos.

## Revisión de criterios

En **Reunión → Resultados → Criterios**, utiliza Editar, Validar o Rechazar. Las decisiones son independientes de los RF/RN. Una modificación devuelve el criterio a pendiente; el texto original y el historial se conservan. Validar aprueba la especificación, no demuestra que exista una implementación probada. Para editar una versión histórica debes activarla primero. Un conflicto conserva el borrador y permite consultar/cargar la revisión vigente.

## PostgreSQL opcional y auditoría

[Guía PostgreSQL](docs/POSTGRESQL.md), [seguridad y privacidad](docs/SECURITY.md), [proveedores](docs/PROVIDERS.md).

La edición local es completa y no exige suscripciones ni registro en un servicio externo de Meeting Requirements AI. Su código, Dockerfiles, dependencias y pruebas están disponibles para revisión. Cada instalación conecta su propia cuenta de ChatGPT. No se incluyen tokens, archivos de reuniones ni historial privado de desarrollo.
