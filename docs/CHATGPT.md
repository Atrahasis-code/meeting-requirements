# Conexión oficial con ChatGPT

## Configuración

1. Abre Configuración y selecciona **Conectar con ChatGPT**.
2. Autoriza la aplicación local mediante la página oficial de OpenAI.
3. El navegador vuelve a `http://127.0.0.1:8080/auth/callback` (o APP_PORT configurado).
4. Comprueba que se concedió el permiso de uso del plan. Selecciona un modelo del catálogo de tu cuenta y guarda preferencias.
5. Abre los controles de Uso de ChatGPT y establece créditos en cero para esta aplicación. Confírmalo manualmente en la UI.
6. Revisa una transcripción y autoriza un análisis. Solo un resultado real completado y validado verifica inferencia.

Las cuentas o políticas que no admiten esta integración deben mostrar la limitación. No se cambia a API keys ni se importan tokens de otros clientes. No necesitas ejecutar `codex login` en el host.

## Implementación

El backend implementa OAuth de cliente público con PKCE S256, state, nonce y validación de ID token mediante JWKS. Solicita `openid profile email offline_access resource.invoke chatgpt.tokens.use.direct`, usando `dynamic_agent_client` solo para registro inicial. El client_id emitido y host ID permanecen asociados a cada registro. Los intentos expiran y el callback se vincula a una cookie HttpOnly/SameSite local.

El proveedor utiliza `openai-codex==0.163.0` y su runtime fijado. Se comprobaron las firmas de `CodexConfig`, `thread_start` y `Thread.run` en el paquete publicado. App-server recibe únicamente el token OAuth propio del proceso, por entorno; no se pasa en argumentos. Se configura `openai_chatgpt_plan` hacia el endpoint público Responses, sin autenticación alternativa ni WebSockets. El SDK mantiene el transporte stdio. Una prueba con un servidor local inspecciona la solicitud real y comprueba `store=false`, streaming y JSON Schema; no necesita credenciales ni realiza inferencia externa.

Se deshabilitan shell, snapshots, múltiples agentes, objetivos autónomos, aplicaciones, plugins, MCP, navegador, generación de imágenes y web. Antes de iniciar app-server se comprueban las opciones del runtime fijado; se rechaza la ejecución si alguna restricción no está aplicada. El entorno de Codex y su HOME son temporales, sin configuración ni conectores del host. Se aplica sandbox de solo lectura, `ApprovalMode.deny_all` y un directorio aislado. Las transcripciones son datos no confiables; solo se solicitan resultados estructurados, validados antes de persistir.

Cada bloque inicia un app-server con el token vigente. La renovación se serializa mediante bloqueo del almacenamiento de credenciales y reemplaza atómicamente el refresh token rotado. Al reiniciar contenedores la sesión persiste; al revocarla se requiere conectar otra vez. Un fallo de red no borra automáticamente una sesión válida. Desconectar intenta revocación oficial y comunica si no se pudo confirmar.

## Consumo

No hay consultas automáticas de inferencia para comprobar disponibilidad. Consultar catálogo no acredita acceso al modelo. No hay reintentos automáticos de inferencias ni compras/recargas.

Si se recibe `subscription_sharing_usage_limit_exceeded`, el trabajo queda blocked y conserva resultados completos de bloques anteriores. Revisa Uso de ChatGPT; no se inventa una fecha de restablecimiento. Guarda de nuevo la confirmación manual de límites y utiliza Revisar y reanudar análisis para volver a autorizar.

La confirmación local de créditos cero no puede sustituir los controles reales de ChatGPT. Si modificas esos límites posteriormente, debes mantenerlos en cero para conservar esa protección. La aplicación no promete conocer tu saldo ni tener un límite independiente de tu cuenta.

## Referencias oficiales

- [Registro y OAuth](https://developers.openai.com/siwc/token-sharing-open-source/sign-in)
- [Sesiones y renovación](https://developers.openai.com/siwc/token-sharing-open-source/profiles-and-sessions)
- [Codex app-server](https://developers.openai.com/siwc/token-sharing-open-source/codex-app-server)
- [Errores y recuperación](https://developers.openai.com/siwc/token-sharing-open-source/errors-and-recovery)
- [Limitaciones de la ruta](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations)

## Un análisis se bloquea con un error de validación

La instalación local permite análisis reales también en reuniones de demostración. La validación automática de la respuesta del proveedor es independiente de la aprobación humana de RF/RN y criterios.

- `invalid_analysis_result`: el proveedor terminó, pero su respuesta no cumple el formato o contiene referencias incoherentes. El mensaje identifica una causa segura (por ejemplo, un requisito inexistente) sin incluir el texto recibido.
- `invalid_provider_response`: el SDK no pudo interpretar la respuesta del runtime. Esto requiere revisar compatibilidad; volver a conectar la cuenta no es la solución predeterminada.
- Los intentos antiguos que solo guardaron `Diagnóstico seguro: validation` no permiten reconstruir el campo exacto rechazado. No se atribuye ese error a la cuota ni a las credenciales sin evidencia.

Una respuesta rechazada no sustituye el análisis activo ni sus exportaciones. No se repite la inferencia automáticamente: para otro intento, utiliza **Revisar y reanudar análisis** y confirma la entrada exacta. El esquema limita las citas a los segmentos autorizados cuando cabe dentro de los límites del proveedor; las citas y relaciones siempre se comprueban después de generar la respuesta.
