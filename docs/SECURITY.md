# Seguridad y privacidad de la edición local

La edición local es para una persona y se expone únicamente en localhost mediante Docker Compose. No tiene cuentas comerciales, suscripciones ni dependencia de un servidor Meeting Requirements AI. No publiques su puerto directamente en Internet.

Los tokens de ChatGPT pertenecen a esta instalación y se conservan en el volumen privado de autenticación con permisos 0600. No se leen credenciales del anfitrión, no se montan directorios del usuario ni el socket Docker y no hay alternativa automática con API keys. Una instalación nueva debe conectar su propia cuenta y confirmar los controles de consumo.

La transcripción usa CPU e INT8. Solo se envía al proveedor el texto autorizado explícitamente para cada análisis. Los originales, citas y versiones se conservan en la base local. Los análisis y sus exportaciones no equivalen a una aprobación humana.

La aplicación se comunica con OpenAI al conectar, renovar, consultar modelos o analizar con consentimiento, y con los repositorios de modelos al descargar un perfil solicitado. Docker y los instaladores descargan las imágenes y dependencias fijadas durante la construcción. No hay telemetría propia ni peticiones de licencia o de suscripción.

La transcripción y el resultado del modelo son datos no confiables: no habilitan comandos, conectores, navegación, lectura de archivos ni delegación. Las salidas se validan con esquema, citas y referencias; los campos se renderizan como texto. Esto limita capacidades y exposición, pero no constituye una garantía de detección perfecta de prompt injection.

Las rutas de archivos, contenidos multimedia y tamaños se validan. Los contenedores principales no son root; mantienen límites de recursos. La base y los backups contienen información sensible: protege el equipo, sus discos y las copias. No guardes tokens ni grabaciones en Git. Un archivo grabado nunca empieza a transcribirse automáticamente.

Para informar de una vulnerabilidad, utiliza el canal privado de seguridad del repositorio cuando esté habilitado. Evita adjuntar secretos, grabaciones o transcripciones a incidencias públicas.
