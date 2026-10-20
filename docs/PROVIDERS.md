# Proveedores locales

Disponibles: ChatGPT mediante OAuth oficial propio de la aplicación y Mock explícito para pruebas sin conexión. Cada instalación conserva su autenticación y controles de consumo; nunca utiliza cuentas de otro operador.

La interfaz de proveedores está separada del procesamiento y de los datos. Añadir un proveedor requiere autenticación oficialmente permitida para terceros, aislamiento de credenciales, consentimiento por entrada, validación estructural y de evidencia, pruebas sin credenciales y una comprobación real autorizada independiente.

Claude y Grok no se muestran como conexiones OAuth disponibles. No se extraen tokens de sus aplicaciones ni se supone que una suscripción de chat habilite una API. No se implementa un cambio automático a facturación por claves.

Consulta las condiciones actuales del proveedor antes de añadir una integración. Documentación de referencia: [OpenAI](https://developers.openai.com/siwc/token-sharing-open-source), [Anthropic](https://code.claude.com/docs/en/legal-and-compliance), [xAI](https://docs.x.ai/developers/quickstart).
