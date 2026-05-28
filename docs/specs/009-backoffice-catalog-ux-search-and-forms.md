# 009 - Backoffice: navegación atrás, búsqueda y formularios colapsables (productos y documentos)

## Contexto y objetivo

Las pantallas de **catálogo** del backoffice ([004](./004-backoffice-products-documents-and-agent-decisions.md)) permiten listar y abrir detalle de productos y documentos, pero la operación diaria tiene fricción:

1. **Detalle sin volver atrás:** en `/products/[id]` y `/documents/[id]` no hay control explícito para regresar al listado; el usuario depende del sidebar o del botón "atrás" del navegador.
2. **Sin búsqueda en listados:** con decenas de productos/documentos, encontrar uno requiere scroll; en documentos no hay filtro rápido por producto vinculado.
3. **Formularios siempre visibles:** crear producto y subir documento ocupan espacio arriba del listado aunque el flujo habitual sea consultar y abrir ítems existentes.

**Objetivo:** mejorar UX en **productos** y **documentos** con patrones ya presentes en el diseño del BO (teal/zinc, `card-static`, `page-header`, `filter-chip`, `ActionFeedbackForm`) — **sin introducir un sistema de diseño nuevo**.

**Relación:** independiente de [008](./008-agent-config-from-backoffice-db.md) (config del agente en DB). Solo comparte convenciones de feedback async de [005](./005-backoffice-async-feedback-and-loading-states.md).

## Alcance / fuera de alcance

### En alcance

- Botón **volver** (icono flecha atrás) en páginas de detalle producto y documento.
- **Buscador de texto** en listado de productos (nombre, marca, país).
- **Buscador de texto** en listado de documentos (título, productos vinculados).
- **Filtro por producto** en documentos mediante **chips clickeables** (reutilizar clases `.filter-chip` / `.filter-chip-active` de `globals.css`, ya usadas en tickets).
- Formularios de **crear producto** y **subir documento** **ocultos por defecto**; visibles solo al pulsar botón **"+"** (misma familia visual que botones primarios existentes).
- Comportamiento responsive coherente con grid actual.
- Tests mínimos en front (componentes cliente) donde aplique; sin cambios de schema DB.

### Fuera de alcance

- Rediseño del sidebar, dashboard home o tema global.
- Búsqueda server-side paginada en API (v1: filtrado **en cliente** sobre el payload ya cargado; ver RF de límites).
- Formularios de **edición** en detalle producto/documento (siguen visibles como hoy en `[id]`).
- Búsqueda en otras secciones (RTCs, decisiones IA, tickets).
- Nuevas dependencias npm.

## Estado actual (referencia de código)

| Ruta | Comportamiento hoy |
| ---- | ------------------ |
| `products/page.tsx` | Form crear producto siempre visible (`ActionFeedbackForm` + grid) |
| `products/[id]/page.tsx` | Sin link "volver"; formularios editar/aliases visibles |
| `documents/page.tsx` | `DocumentUploadForm` siempre visible; lista completa sin filtro |
| `documents/[id]/page.tsx` | `DocumentDetailView`; sin volver |
| `tickets/page.tsx` | Referencia de **filter chips** clickeables |
| `globals.css` | `.filter-chip`, `.filter-chip-active` |

Listados cargan hasta `page_size=100` productos y **todos** los documentos en una petición (`GET /documents`).

## Requisitos funcionales

### Navegación atrás (detalle)

- **RF-1**: En `products/[id]/page.tsx`, encabezado con control **Volver a productos**:
  - Icono `ArrowLeft` de `lucide-react` (mismo estilo que iconografía existente).
  - `Link` a `/products` o `router.back()` — **preferir `Link` a `/products`** para destino predecible.
  - Clases: variante secundaria alineada a links teal del listado (no botón primario de submit).
- **RF-2**: Misma RF en `documents/[id]/page.tsx` → **Volver a documentos** → `/documents`.
- **RF-3**: Accesibilidad: `aria-label` descriptivo; foco visible en teclado.

### Búsqueda — productos

- **RF-4**: Componente cliente `ProductsCatalogToolbar` (o nombre equivalente) sobre el grid de tarjetas:
  - Input tipo search con placeholder: "Buscar por nombre, marca o país…"
  - Filtrado case-insensitive, sin acentos opcional (usar normalización simple: `normalize` NFD o comparar lowercase).
  - Actualización en tiempo real al escribir (sin botón "Buscar").
- **RF-5**: Si el filtro deja 0 resultados, mensaje empty state: "Ningún producto coincide con la búsqueda" (mantener estilo dashed card del listado vacío actual).
- **RF-6**: La búsqueda **no oculta** el botón "+" de crear (ver RF-10).

### Búsqueda y chips — documentos

- **RF-7**: Componente cliente `DocumentsCatalogToolbar`:
  - Campo de búsqueda: título del documento + texto de productos vinculados (`linked_products[].name`, `product_name` legacy).
- **RF-8**: Fila de **chips de producto** debajo del buscador:
  - Chip **Todos** (activo por defecto) — muestra todos los documentos (sujeto a búsqueda de texto).
  - Un chip por producto del catálogo (`GET /products?page=1&page_size=100` ya disponible en la página).
  - Al clic en un chip de producto, filtrar documentos que tengan ese `product_id` en `linked_products` o coincidencia por nombre primario.
  - Estilo: `.filter-chip` / `.filter-chip-active` (copiar patrón de `tickets/page.tsx`).
  - Solo un producto seleccionable a la vez en v1 (chip activo único + "Todos").
- **RF-9**: Combinación: búsqueda de texto **AND** filtro de chip activo.
- **RF-10**: Empty state cuando no hay coincidencias.

### Formularios colapsables (crear / subir)

- **RF-11**: En `products/page.tsx`, el bloque `ActionFeedbackForm` de creación **no se renderiza** al cargar la página.
- **RF-12**: Botón **"+"** (o "Nuevo producto") en el `page-header` o junto al toolbar:
  - Al clic, expande el formulario existente (mismos campos y `createProductAction`).
  - Segundo clic o botón "Cancelar" colapsa y limpia campos opcional.
  - Icono `Plus` de lucide; botón secundario/outline consistente con tarjetas (`rounded-2xl`, borde teal suave).
- **RF-13**: En `documents/page.tsx`, `DocumentUploadForm` oculto por defecto; misma interacción "+" para mostrar subida PDF.
- **RF-14**: Tras **éxito** de crear/subir, colapsar el formulario y mostrar toast/feedback existente ([005](./005-backoffice-async-feedback-and-loading-states.md)); refrescar lista (router.refresh o revalidate según patrón actual).
- **RF-15**: Rol `viewer`: no mostrar botón "+" ni formularios (igual que hoy no puede mutar).

### API / backend

- **RF-16**: Sin nuevos endpoints en v1; si el listado supera 100 ítems, documentar limitación en UI ("Mostrando primeros 100 productos") — opcional v1.1: query `?q=` server-side.

## Requisitos no funcionales

- **RNF-1**: Hidratación correcta: toolbars como Client Components; páginas pueden seguir siendo Server Components que pasan `items` serializables.
- **RNF-2**: Filtrado en cliente O(n) sobre ≤ few hundred rows — aceptable en v1.
- **RNF-3**: No agregar dependencias; usar React state + `useMemo` para filtros.
- **RNF-4**: Mantener contraste y tamaños táctiles ≥ 44px en chips y botón volver en mobile.

## Criterios de aceptación (Given/When/Then)

- **CA-1 (Volver producto)**
  - **Given** estoy en `/products/{id}`,
  - **When** clic en "Volver a productos",
  - **Then** navego a `/products` sin error.

- **CA-2 (Volver documento)**
  - **Given** estoy en `/documents/{id}`,
  - **When** clic en volver,
  - **Then** navego a `/documents`.

- **CA-3 (Buscar producto)**
  - **Given** listado con "Imperia" y "Proteggo M",
  - **When** escribo "imper" en el buscador,
  - **Then** solo veo tarjetas que coinciden.

- **CA-4 (Chips documento)**
  - **Given** documentos de Imperia y otros productos,
  - **When** activo chip "Imperia",
  - **Then** solo veo documentos vinculados a Imperia; chip muestra estado activo.

- **CA-5 (Form colapsado)**
  - **Given** abro `/products` como scientist,
  - **When** la página carga,
  - **Then** no veo campos de crear producto hasta pulsar "+".

- **CA-6 (Crear y colapsar)**
  - **Given** expandí formulario y creé producto con éxito,
  - **When** termina la acción,
  - **Then** formulario colapsado + toast de éxito + nuevo ítem en grid.

- **CA-7 (Viewer)**
  - **Given** rol viewer en `/products`,
  - **Then** no hay botón "+" ni formulario de alta.

## Diseño técnico

`Migraciones necesarias: **no**`

### Componentes nuevos (propuesta)

| Componente | Tipo | Ubicación |
| ---------- | ---- | --------- |
| `CatalogBackLink` | Server o client | `components/catalog-back-link.tsx` |
| `ProductsCatalogToolbar` | Client | `components/products-catalog-toolbar.tsx` |
| `DocumentsCatalogToolbar` | Client | `components/documents-catalog-toolbar.tsx` |
| `CollapsibleCatalogForm` | Client wrapper | `components/collapsible-catalog-form.tsx` |

`CollapsibleCatalogForm` envuelve children (form existente) y maneja estado `open` + botón Plus en header slot.

### Wireframe ASCII (listado productos)

```
[← no aplica en listado]

Productos                                    [ + Nuevo ]
Buscar: [________________________]

[ grid tarjetas filtradas ]
```

### Wireframe ASCII (detalle)

```
← Volver a productos

Imperia
... formularios edición ...
```

### Archivos impactados

- `services/backoffice-web/app/(dashboard)/products/page.tsx`
- `services/backoffice-web/app/(dashboard)/products/[id]/page.tsx`
- `services/backoffice-web/app/(dashboard)/documents/page.tsx`
- `services/backoffice-web/app/(dashboard)/documents/[id]/page.tsx`
- `services/backoffice-web/components/*` (nuevos)
- Opcional: tests `*.test.tsx` con Vitest si ya está en el paquete; si no, prueba manual documentada.

### Restricción de diseño

- Reutilizar: `page-header`, `page-title`, `card-static`, `form-label`, `form-input`, `SubmitButton`, `filter-chip*`, paleta teal/zinc.
- **No** introducir shadcn nuevo ni cambiar `tailwind.config.ts` salvo clase utilitaria mínima si falta para el botón "+" (preferir composición de clases existentes).

## Plan de pruebas

- Manual checklist en CA-1…CA-7.
- Si hay Vitest: mount toolbar con lista mock, assert filtro y chip activo.
- Regresión visual: detalle producto/documento con formularios de edición intactos.

## Observabilidad

- Sin métricas nuevas (solo front).
- Opcional: evento analítico interno fuera de alcance.

## Riesgos y rollback

| Riesgo | Mitigación |
| ------ | ---------- |
| Listas >100 ítems no filtran todo el catálogo | Mensaje en UI; spec 009.1 server search |
| Client bundle ligeramente mayor | Componentes pequeños, sin libs |
| Usuario no encuentra cómo crear | Label claro en botón "+" |

**Rollback:** revert del PR web únicamente; sin migraciones.

## Referencias

- [004](./004-backoffice-products-documents-and-agent-decisions.md)
- [005](./005-backoffice-async-feedback-and-loading-states.md)
- [006](./006-backoffice-product-document-links.md) — `linked_products` para chips
- [008](./008-agent-config-from-backoffice-db.md) — config agente (paralela)
