# Cómo verificar la edición local

Ejecuta todas las comprobaciones dentro de Docker:

```sh
sh scripts/test.sh
sh scripts/test-postgres.sh
sh scripts/test-operations.sh
sh scripts/test-worker-recovery.sh
```

Los proyectos de prueba y sus volúmenes están separados de los datos normales; las suites no requieren cuentas ni modelos. La integración usa ffprobe real, grabaciones sintéticas, transcripción simulada y Mock. Las pruebas de interfaz incluyen cambios de criterios, rechazo con motivo, conservación de borrador tras conflicto y renderizado seguro del texto.

Las comprobaciones reales de ChatGPT y faster-whisper son opt-in. No hay llamadas de inferencia para verificar automáticamente una cuenta; hace falta autorización explícita sobre el texto. Conservar evidencia local de cada comprobación sin publicar tokens ni contenidos de reuniones.

La Alpha fue probada en Linux amd64 mediante Docker Desktop/WSL2; se construyeron y probaron dependencias e inferencia arm64 mediante emulación. Las modificaciones posteriores requieren su propia verificación antes de afirmar compatibilidad. Las pruebas emuladas no acreditan rendimiento ni ejecución nativa en macOS Intel o Apple Silicon. No se afirma validación nativa de macOS.

## Verificación de esta entrega

En Linux amd64 / Docker Desktop con WSL2: 50 pruebas del backend SQLite, 13 de interfaz y 11 del flujo/PostgreSQL aprobadas. Las seis omisiones de la suite SQLite corresponden a pruebas de PostgreSQL/HTTP ejecutadas en sus proyectos específicos. Las pruebas normales usan proveedores simulados, sin modelos ni credenciales personales. El candidato público se verifica como árbol independiente; el registro privado de entrega conserva la evidencia operativa. Esta comprobación no acredita ejecución nativa en macOS ni servicios remotos.
