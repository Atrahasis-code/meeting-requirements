# Arquitectura

## Componentes

- Frontend React/TypeScript/Vite, Tailwind y componentes de patrón shadcn/ui sobre Radix. Router, TanStack Query y formularios React Hook Form/Zod. Nginx no root sirve la compilación y hace proxy de API/callback. Vite realiza el mismo proxy durante desarrollo.
- FastAPI separa contratos Pydantic, acceso a datos, servicios de aplicación, almacenamiento, OAuth, análisis y exportación.
- Worker dedicado con bloqueo `flock` en el volumen SQLite. Cada trabajo usa un proceso spawn aislado que libera memoria nativa al terminar. El supervisor mantiene heartbeat incluso durante inferencia.
- SQLite local con claves foráneas, busy_timeout 5000, WAL y transacciones cortas. La inicialización de esquema ocurre con Alembic antes de los servicios principales. Un índice parcial impide dos trabajos running y otro impide trabajos activos duplicados para una reunión.

La cola no usa Redis/Celery. Los trabajos nuevos solo aparecen por acciones manuales. Los estados internos están en inglés; la UI los traduce. Registered representa una reunión aún sin archivo. Blocked e interrupted complementan los estados solicitados y conservan el motivo y los checkpoints. Reiniciar solo la API no modifica un trabajo que sigue ejecutándose.

## Volúmenes

| Volumen | Montaje | Contenido |
|---|---|---|
| database | /data/db | SQLite, WAL/SHM, bloqueo del worker y heartbeat persistido |
| media | /data/media | Grabaciones con nombres UUID y formatos validados |
| transcripts | /data/transcripts | TXT/JSON/SRT/VTT y fragmento temporal de audio |
| exports | /data/exports | Paquetes por proyecto/reunión/UUID, nunca sobreescritos |
| models | /data/models | Modelos reutilizables de Hugging Face/CTranslate2 |
| authentication | /data/auth | Host ID, registros OAuth y tokens de esta aplicación |

Los nombres efectivos llevan el prefijo del proyecto Compose. `docker compose down` conserva los volúmenes. **No uses `down -v` con datos reales.** NFS/SMB/9p/virtiofs no están admitidos para SQLite. No remapees database a carpetas sincronizadas o compartidas entre equipos.

## Transcripción y análisis

FFmpeg produce un fragmento mono PCM 16 kHz de cinco minutos con dos segundos de contexto en cada extremo. Las palabras se asignan a intervalos centrales semiabiertos por su punto medio global. Así, un mismo resultado temporal no se incorpora dos veces; la calidad acústica de palabras reconocidas de forma distinta en ambos fragmentos sigue requiriendo revisión humana. El avance indica segundos de fragmentos confirmados, no una predicción de tiempo restante.

La descarga y carga de modelos son indeterminadas. Una cancelación se comprueba entre fragmentos/segmentos; tras el período de gracia se termina el grupo de procesos y se conserva lo confirmado. Los checkpoints no son transcripciones completas. No hay botón de pausa: cancelar y reintentar permite continuar desde checkpoints.

El texto original es inmutable. Las correcciones usan una revisión global para detectar ediciones concurrentes. Un análisis conserva su entrada autorizada, contexto, glosario, revisión y hash. Los requisitos conservan contenido generado, evidencia y revisiones humanas. Las exportaciones utilizan los requisitos editados y la copia de transcripción correspondiente al análisis, evitando mezclar evidencia con correcciones posteriores incompatibles.

La extracción de entradas largas se realiza por bloques de segmentos. Se validan citas, referencias y códigos y se fusionan duplicados exactos dentro de la ejecución. No existe consolidación semántica entre reuniones. Los resultados no aprobados se exportan con su estado; una exportación nunca equivale a aprobación. La API aporta `code_mapping` para resolver referencias generadas a los códigos persistidos de cada versión en historias, criterios y backlog. El JSON original se conserva inmutable; las dependencias se exportan con códigos legibles y la matriz incluye backlog.

## API

OpenAPI está disponible en `/api/openapi.json` y la documentación interactiva en `/api/docs`, a través del proxy local. Se mantienen proyectos, reuniones, carga, transcribe/analyze, jobs/cancel, transcript-segments, requirements/validate, exports/download, health y settings.

Cambios respecto al documento inicial:

- GET `/api/dashboard` devuelve contadores y trabajos reales.
- GET `/api/meetings/{id}/analysis-input` devuelve la entrada exacta y su hash; POST analyze exige ese hash y consentimiento para un proveedor externo.
- GET `/api/meetings/{id}/analyses`, POST `/api/analysis-runs/{id}/activate` y GET `/api/meetings/{id}/exports` administran versiones.
- POST `/api/jobs/{id}/retry` exige nueva autorización para análisis y permite continuar checkpoints compatibles.
- DELETE `/api/meetings/{id}/media?confirm=true` elimina solo audio/video, conservando la evidencia textual; DELETE meeting elimina todo tras confirmación.
- GET `/api/meetings/{id}/transcript/download?format=txt|json|srt|vtt` y GET export download con `file` descargan formatos/documentos permitidos.
- La UI utiliza polling cada dos segundos; no se implementa `/jobs/{id}/events` porque no se usa SSE.
- OAuth y catálogo usan `/api/auth/chatgpt/*`, `/auth/callback` y `/api/providers/chatgpt/models`.

Los secretos nunca forman parte de schemas de respuesta. Los endpoints de archivos resuelven rutas relativas dentro del volumen autorizado. Se validan tamaño real recibido, extensión, contenedor y presencia de audio. No se interpolan comandos de shell.

## Revisiones, PostgreSQL y extensiones

Los criterios tienen consulta individual, edición y validación/rechazo explícitos con revisión optimista. Una modificación de Dado/Cuando/Entonces devuelve a pendiente; un guardado idéntico no cambia el estado. Se exige motivo de rechazo y versión activa. Originales y RF/RN no se alteran al aprobar un criterio. El historial nuevo identifica al usuario local; un evento antiguo sin identidad no se atribuye retroactivamente.

SQLite conserva WAL y sus opciones de conexión. PostgreSQL es opt-in mediante override Compose y utiliza bloqueo asesor para un único worker local. Las relaciones impiden mezclar organizaciones y cada transacción establece su contexto; la distribución local utiliza siempre el espacio local. Los adaptadores de almacenamiento/proveedor y la política de ejecución tienen valores predeterminados locales completos, sin imports o dependencias de una edición privada.
