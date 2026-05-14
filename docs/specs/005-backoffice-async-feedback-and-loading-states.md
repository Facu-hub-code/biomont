# 005 - Backoffice web: feedback visual y estados de carga en acciones async

## Contexto y objetivo

En el backoffice web, varias pantallas ejecutan acciones que llaman a la API (`fetch`/Server Actions) pero no ofrecen **confirmacion inmediata** de exito o error. El operador solo infiere el resultado cuando la tabla o la vista se actualiza (p. ej. nuevo producto visible en listado), lo que genera incertidumbre ante latencia, fallos silenciosos en cliente o errores HTTP.

**Objetivo:** toda interaccion que **dispare una peticion al backend** y **espere respuesta** debe:

1. Mostrar **estado de carga** en el control que disparo la accion (o sustituto claro, p. ej. overlay en la fila).
2. Tras respuesta exitosa, mostrar **confirmacion visual explicita** (no depender solo del refresco de lista).
3. Tras error, mostrar **mensaje legible** con el cuerpo/`detail` devuelto por la API cuando exista.

Alcance: **backoffice-web** (`services/backoffice-web`), sin cambios de contrato en **backoffice-api** salvo que se descubra bug real en respuestas de error.

## Alcance / fuera de alcance

### En alcance

- Inventario y cobertura de **botones / formularios / acciones** que llaman al back: **Productos** (crear/editar/eliminar, aliases), **Documentos** (subida, acciones secundarias si aplica), **Decisiones del agente** (solo lectura: sin loading de mutacion salvo filtros/busqueda que disparen fetch), **Conversaciones** u otras rutas bajo `(dashboard)` que ejecuten mutaciones o fetches bloqueantes.
- **Loading:** deshabilitar el control primario durante la peticion; indicador visual no ambiguo (spinner, texto "Guardando...", u otra convencion unica del proyecto).
- **Exito:** toast/banner inline/snackbar **una sola vez** por accion completada; mensaje breve localizado (es).
- **Error:** toast o bloque de error con mensaje; en `4xx`/`5xx` preferir `detail` de FastAPI si viene en JSON.
- **Accesibilidad minima:** boton con `aria-busy` o equivalente durante carga; no depender solo del color.

### Fuera de alcance

- Cambiar diseno global del layout (sidebar, tema) salvo donde sea necesario montar un proveedor de toasts.
- Skeleton loaders para listados enteros (mejora opcional en iteracion posterior).
- Optimistic UI (actualizar lista antes de confirmar servidor): no requerido en v1.
- **Nuevas dependencias** salvo justificacion en PR (preferir patron con `useState`/`useTransition` y componentes existentes; si se adopta `sonner` u otra lib, documentar en el mismo PR).

## Requisitos funcionales

- **RF-1 (loading):** cada accion mutante o submit async asocia un flag `isSubmitting` (o equivalente) que impide doble envio y muestra indicador hasta `resolve`/`reject`.
- **RF-2 (exito):** al menos un canal de confirmacion visible (toast preferido si hay infra minima; si no, alerta/banner dismissible en la misma vista).
- **RF-3 (error):** ante fallo de red o HTTP no ok, mostrar mensaje; si el cuerpo es JSON con `detail` string o lista de validacion, formatearlo de forma legible (lista corta).
- **RF-4 (listados post-create):** tras crear/editar recurso, **refrescar** datos de la tabla o **navegar** al detalle con feedback previo (toast "Producto creado") para que la confirmacion no dependa de que el usuario mire la tabla al mismo tiempo.
- **RF-5 (consistencia):** mismo patron visual en todas las pantallas del dashboard afectadas (documentar convencion en comentario o `README` del paquete web si hace falta).

## Requisitos no funcionales

- **RNF-1:** doble click no debe generar dos POST; el boton permanece deshabilitado hasta fin de request.
- **RNF-2:** no bloquear la pestaña completa salvo subida de archivo larga; ahi puede usarse progreso o estado en el formulario de documentos.
- **RNF-3:** mensajes de exito/error sin datos sensibles (no volcar stack traces de servidor al usuario).

## Criterios de aceptacion (Given/When/Then)

- **CA-1 (crear producto)**
  - **Given** un usuario autenticado con permiso de creacion,
  - **When** envia el formulario de nuevo producto,
  - **Then** el boton primario muestra estado de carga hasta respuesta, luego aparece confirmacion visual de exito y el listado o vista refleja el nuevo elemento (o redireccion al detalle con confirmacion).

- **CA-2 (error API)**
  - **Given** la API responde `409` con `detail` de conflicto,
  - **When** el usuario guarda,
  - **Then** ve mensaje de error con el texto de conflicto y el formulario sigue utilizable para corregir datos.

- **CA-3 (subida documento)**
  - **Given** el usuario selecciona PDF y envia,
  - **While** la peticion esta en curso,
  - **Then** el submit esta deshabilitado y hay indicacion de procesamiento; al terminar, exito o error visible sin ambiguedad.

- **CA-4 (edicion alias / delete producto admin)**
  - **When** acciones analogas mutan datos,
  - **Then** mismo patron: loading + feedback + lista o detalle coherente.

## Diseno tecnico

- **Patron recomendado:** por cada formulario o accion, `useState` para `pending`/`errorMessage` o `useTransition` donde encaje con Server Actions de Next.
- **Componentizacion:** extraer `<SubmitButton pending={...} />` o hook `useAsyncAction` interno al repo para no duplicar logica (solo si reduce copia; no abstraer prematuramente).
- **Toasts:** si no hay libreria, implementar un contenedor minimo con React state + portal o banner fijo superior; evaluar `sonner` si el equipo acepta una dependencia liviana (justificar en PR).
- **Archivos a revisar de entrada:** `services/backoffice-web/app/(dashboard)/products/**`, `documents/**`, `agent-decisions/**`, `layout.tsx`, clientes que ya usen `fetch` a la API.

## Migraciones necesarias

`Migraciones necesarias: no`

## Plan de pruebas

- **Manual QA (checklist en PR):** crear producto, conflicto de nombre, editar, eliminar (admin), subir PDF, filtrar listado de decisiones (spinner en busqueda si aplica).
- **Tests automatizados:** opcional en v1; si el repo introduce util de test de React, al menos un test de componente para el boton con `pending`.

## Observabilidad

- Sin cambios de backend obligatorios.
- Opcional: log en consola solo en desarrollo si falla parseo de error (no en produccion noisy).

## Riesgos y rollback

| Riesgo | Mitigacion |
| ------ | ---------- |
| Toasts duplicados por Strict Mode en dev | Idempotencia de lado UI o clave de sesion por accion |
| Feedback tapa errores de validacion de campo | Mantener errores por campo en formulario + toast resumido |

**Rollback:** revert del PR exclusivamente frontend.

## Referencias

- Backoffice funcional relacionado: [004 - productos, documentos, agent-decisions](./004-backoffice-products-documents-and-agent-decisions.md)
