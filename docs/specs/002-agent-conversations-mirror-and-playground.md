# 002 - Vista espejo de conversaciones (estilo WhatsApp Web) y playground del agente

## Contexto y objetivo

Operadores del backoffice necesitan **ver** el historial de interacciones del agente con cada RTC tal como queda materializado en el sistema (mensajes de usuario y asistente), con una interfaz familiar tipo **WhatsApp Web**, **sin** poder enviar mensajes “como si fueran el agente” desde esa vista.

En paralelo, se requiere un **playground** para **probar** el agente: un flujo que simula un dispositivo (modal con forma de tablet), donde se elige un RTC y se conversa **fuera del canal WhatsApp**. Esas pruebas deben **reflejar el mismo hilo conversacional** que el chat real del RTC (misma conversación activa en base de datos), de modo que mensajes recibidos por WhatsApp y mensajes enviados desde el playground aparezcan en un único transcript coherente cuando correspondan al mismo ciclo de actividad del RTC.

Hoy el agente persiste en PostgreSQL (`public.conversations`, `public.messages`) y resuelve la conversación activa por `rtc_user_id` con ventana de inactividad (`ConversationRepository.get_or_create_active_conversation` en `services/common`). La spec alinea producto y backend con ese modelo.

## Alcance / fuera de alcance

- **En alcance**:
  - Nueva sección en el backoffice web con layout de dos columnas inspirado en WhatsApp Web: lista de conversaciones (orden por última actividad) y panel de mensajes del hilo seleccionado.
  - Solo **lectura** en la vista espejo: sin campo de envío ni acciones que modifiquen el chat desde esa pantalla.
  - Botón global o de sección que abre un **modal** con marco tipo tablet: selector de RTC → panel de chat con envío de texto.
  - El playground usa el **mismo criterio de conversación activa** que WhatsApp (mismo `rtc_user_id`, misma ventana de inactividad), de forma que el transcript mostrado en espejo y en el modal sea el **mismo** mientras compartan conversación activa.
  - APIs del backoffice (autenticadas con el mismo modelo de sesión del BO) para listar conversaciones/mensajes y para enviar mensajes del playground.
  - Respuesta del agente en playground **en la respuesta HTTP** (o streaming si se acuerda en implementación), **sin reenviar la respuesta al teléfono del cliente por WhatsApp** (evitar ping doble al usuario real).

- **Fuera de alcance**:
  - Enviar mensajes salientes como si fueran el humano/agente desde la vista espejo.
  - Replicar al 100% la UI de WhatsApp (menos legal/brand); basta “inspiración visual” (burbujas, lista, timestamps legibles).
  - Soporte multimedia (imágenes, audios, plantillas) en la v1 del espejo; solo texto alineado con lo que hoy persiste el webhook WhatsApp (`type == "text"`).
  - Notificaciones push, socket en tiempo real obligatorio para la v1: **se puede** empezar con polling corto documentado; realtime (SSE/WebSocket) queda como mejora opcional si no cumple latencia aceptable.
  - Cambiar la lógica de negocio de tickets/decisiones del orchestrator salvo lo necesario para invocar el mismo pipeline con `skip_whatsapp_send`.

## Requisitos funcionales

- **RF-1**: Listado de conversaciones con: identificador de RTC (nombre + teléfono en formato legible), última actividad, preview del último mensaje (texto truncado), indicador de conversación seleccionada.
- **RF-2**: Al seleccionar una conversación, mostrar mensajes en orden cronológico con rol claro (usuario vs asistente). Contenido acorde a `public.messages.content` y `message_role`.
- **RF-3**: La vista espejo **no** muestra controles de envío ni llamadas al endpoint de playground.
- **RF-4**: Botón “Probar agente” (copy final definible) abre modal tablet; paso 1 elegir RTC de la lista habilitada; paso 2 chat con input de texto y lista de mensajes.
- **RF-5**: Cada envío desde el playground ejecuta el **mismo procesamiento de agente** que un mensaje entrante de WhatsApp (RAG, prompts, persistencia de mensajes y decisiones), con la salvedad de **no enviar** la respuesta por WhatsApp al cliente.
- **RF-6**: Tras enviar desde el playground, el historial del modal **y** la vista espejo (si está la misma conversación seleccionada o al refrescar) reflejan los nuevos mensajes sin inconsistencias de orden.
- **RF-7**: Si el RTC recibe mensajes por WhatsApp mientras un operador tiene abierto el playground para ese RTC, al actualizar (poll manual o automático) deben verse esos mensajes en el modal y en el espejo.
- **RF-8**: Autorización: solo usuarios autenticados del backoffice; sin exponer datos de conversaciones a anónimos.

## Requisitos no funcionales

- **RNF-1**: Latencia percibida: envío playground &lt; 15s p95 en condiciones normales (depende del LLM); UI con estado de “enviando…”.
- **RNF-2**: Seguridad: endpoints de conversaciones y playground detrás de `Authorization` del BO; rate limit razonable en POST playground (anti-abuso).
- **RNF-3**: Observabilidad: logs estructurados en el servicio que ejecute el pipeline con `rtc_user_id`, `conversation_id`, origen `playground` vs `whatsapp_webhook`, `request_id`.
- **RNF-4**: Privacidad: el playground está destinado a operación interna; no registrar payloads sensibles adicionales fuera de lo ya persistido.

## Criterios de aceptacion (Given/When/Then)

- **CA-1 (listado y lectura)**
  - **Given** un usuario BO autenticado y existencia de al menos una fila en `conversations` con mensajes,
  - **When** abre la nueva vista de conversaciones,
  - **Then** ve la lista ordenada por última actividad desc y puede abrir un hilo sin ver controles de envío en el panel principal.

- **CA-2 (modal playground básico)**
  - **Given** un usuario BO autenticado,
  - **When** pulsa “Probar agente”, elige un RTC y envía “Hola prueba”,
  - **Then** recibe respuesta del asistente en el modal y aparecen dos mensajes nuevos en `messages` asociados a la conversación activa de ese `rtc_user_id`.

- **CA-3 (sin WhatsApp en playground)**
  - **Given** el mismo escenario que CA-2 y un mock/monitoreo del cliente WhatsApp (o entorno de prueba sin envío real),
  - **When** se envía mensaje desde el playground,
  - **Then** no se invoca el envío de plantilla/mensaje saliente de WhatsApp al `phone_e164` del RTC para esa respuesta.

- **CA-4 (coherencia con WhatsApp)**
  - **Given** un RTC con conversación activa alimentada previamente por WhatsApp,
  - **When** el operador abre el playground para ese RTC,
  - **Then** el historial inicial del modal coincide con los mensajes ya persistidos para ese `conversation_id` (orden y contenido).

- **CA-5 (nuevo hilo por inactividad — regresión de modelo existente)**
  - **Given** un RTC cuya última actividad supera la ventana `inactivity_minutes` configurada en el repositorio,
  - **When** llega un mensaje (WhatsApp o playground),
  - **Then** se crea una conversación nueva y eso se refleja en el listado del BO como conversación distinta (nueva fila o segmentación clara según diseño de listado acordado en implementación).

## Diseno tecnico

### Modelo de datos (existente)

- `public.conversations`: `rtc_user_id`, `last_message_at`, …
- `public.messages`: `conversation_id`, `role` (`user` | `assistant` | `system`), `content`, …

La conversación “activa” es la que ya implementa `get_or_create_active_conversation`; no se duplica criterio en front.

### Backend

- **Listado y detalle (solo lectura)** vía `services/backoffice-api`: nuevo router (p. ej. `conversations_router`) + repositorio SQL encapsulado en `app/db/` siguiendo el patrón de `rtc_admin_repository` / `analytics_repository`. Join con `rtc_users` para nombre y `phone_e164`.

- **Ejecución del playground**: el orchestrator actual (`services/agent/src/app/agent/orchestrator.py`) finaliza con envío WhatsApp. Se introduce un camino explícito **“inbound sin entrega WhatsApp”** (nombre tentativo `skip_whatsapp_delivery`), preservando inserción de mensajes y decisiones.

  - **Opción preferida**: exponer en `services/agent` un endpoint interno (p. ej. `POST /internal/playground/messages`) protegido por **secret compartido** o red privada, que recibe `rtc_user_id` + `text` y delega en el orchestrator. `services/backoffice-api` hace de **proxy** y adjunta el secreto, para no empaquetar todo el orchestrator en el BO ni duplicar lógica RAG.

  - **Alternativa** (solo si el despliegue lo exige): factor mínimo compartido en `biomont_common` — evitar duplicar SQL del orchestrator en handlers del BO.

### Frontend

- `services/backoffice-web`: nueva ruta bajo `(dashboard)` (p. ej. `app/(dashboard)/conversations/page.tsx`) con componentes presentacionales para lista + hilo.
- Modal tablet: componente reutilizable (Tailwind), selector de RTC reutilizando tipos/contrato de listado de RTCs existente (`rtcs` API).
- Sincronización v1: **polling** cada N segundos con debounce al enviar; documentar N en implementación.

### Archivos impactados (previstos)

- `services/backoffice-api`: nuevo router + repositorio; `main.py` registrando router; schemas Pydantic; tests HTTP.
- `services/agent`: orchestrator + posible nuevo router interno; settings para secret playground; tests del orchestrator/endpoint.
- `services/backoffice-web`: nueva página, componentes UI, llamadas `apiRequest`.
- `services/common`: solo si se extraen tipos/helpers compartidos (opcional).

## Migraciones necesarias

`Migraciones necesarias: no`

La v1 usa el esquema actual de `conversations` / `messages`. Si en el futuro se desea distinguir canal de origen por mensaje (WhatsApp vs playground), valorar una migración aparte con columna nullable `source` o `channel` y backfill.

### Evidencia de estructura (referencia)

Definición ya versionada en `migrations/003_conversations_tickets.sql`: tablas `conversations` y `messages` con FK a `rtc_users` e índice `idx_conversations_rtc` sobre `(rtc_user_id, last_message_at DESC)`.

## Plan de pruebas

- **Unitarios**: repositorio de listado (orden, join RTC, paginación si aplica); orchestrator con `skip_whatsapp_delivery` (mock `WhatsAppClient` sin assert de llamada).
- **Integración/HTTP backoffice-api**: GET conversaciones y GET mensajes con auth válida / 401 sin token.
- **HTTP agent (interno)**: POST playground con secret válido e inválido; cuerpo mínimo validado.
- **E2E manual** (checklist): webhook WhatsApp de prueba + mismo RTC en playground → transcript unificado visible en BO.
- **Mocks**: LLM y WhatsApp como en política del repo; no llamar Meta ni modelo real en CI.

## Observabilidad

- Logs con `event=conversation_list`, `event=playground_message`, `decision` ya existente en orchestrator + campo `channel=playground|whatsapp`.
- Métrica opcional: contador de mensajes playground por día (si hay stack de métricas; si no, solo logs agregables).

## Riesgos y rollback

| Riesgo | Mitigación |
| --- | --- |
| Proxy BO→Agent mal configurado en producción | Healthcheck interno; fallar cerrado si falta secret; documentar variables en `.env.example` |
| Operador confunde playground con chat real del cliente | Copy claro en UI; disclaimer en modal |
| Doble envío accidental a WhatsApp | Tests que asienten `skip_whatsapp_delivery`; code review del path de `_send` |
| Polling agresivo carga DB | Intervalo razonable; índices existentes; paginación en listado |

**Rollback**: revertir despliegue de `backoffice-api`, `backoffice-web` y `agent`; sin migraciones no hay rollback SQL. Desactivar ruta interna del agent vía feature flag o remoción de secret en ingress.
