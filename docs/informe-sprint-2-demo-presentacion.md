# Informe Sprint 2 — Motor de cálculos, comparador comercial y sistema de tickets

**Versión:** 1.0  
**Fecha de referencia:** 3 junio 2026  
**Propósito:** corpus estructurado para alimentar un sistema de IA que arma presentaciones ejecutivas y técnicas, y para guiar una demo en vivo del Sprint 2.  
**Ámbito de fuentes:** especificaciones `docs/specs/011-dose-calculation-engine.md`, `012-competitor-comparison-hybrid.md`, `013-comparison-llm-redactor.md`; código en `services/agent`, `services/backoffice-api`, `services/backoffice-web`, `services/common`, `migrations/`; golden set en `evaluation/golden_set.yaml`.  
**Entorno de demo sugerido:** backoffice web (`http://localhost:3000`) + playground del agente en Conversaciones; servicios `agent` (8001) y `backoffice-api` (8002).

---

## Resumen ejecutivo (slide de apertura)

En el **Sprint 2** el agente deja de depender solo de RAG para tres escenarios críticos del RTC:

1. **Motor de cálculos de dosis** — respuesta **determinista** (0% alucinación en mg/tabletas).
2. **Comparador comercial** — diff columna a columna desde Excel validado, redactado para WhatsApp.
3. **Sistema de tickets** — cuando no hay información o confianza, el agente **escala** al equipo científico con trazabilidad.

**Problema que resuelve:** un RTC pregunta *"perro de 25 kg, ¿qué Proteggo le doy?"* o *"MARVO 20 vs Marboxi en dosis"*. Antes: texto libre del LLM sobre chunks. Ahora: lookup en tablas publicadas + redacción acotada, con fallback a ticket si falta dato.

---

## Contexto del sprint (cronograma)

| Ítem | Título | Ventana | Avance reportado | Relación con esta demo |
| ---- | ------ | ------- | ---------------- | ---------------------- |
| 2.1 | Motor de cálculo | 25–28 may | ~70% | **Núcleo de la demo 1** |
| 2.2 | Sistema de tickets | 27–30 may | 0%* | **Núcleo de la demo 3** |
| 2.3 | Trazabilidad | 1–3 jun | 0% | Mostrar `graph_trace` y decisiones |
| 2.4 | Prompt tuning + QA | 4–6 jun | 0% | Fuera de alcance de esta sesión |

\*El esquema de tickets y la UI existen desde el sprint 1 (migración `003_conversations_tickets.sql`); el ítem 2.2 del plan apunta a **operacionalización completa** (flujo científico, métricas, tipo `user_request` manual). En demo conviene mostrar lo que **ya funciona** y marcar pendientes.

---

## Los tres pilares — qué contar en la presentación

### 1. Motor de cálculos de dosis (Spec 011)

**Qué es:** motor **sin LLM** que recomienda presentación comercial según peso y especie.

**Fuentes de verdad:**

- Tablas Postgres: `product_dosing_profiles`, `product_dosing_rules`, `product_dosing_gaps`, `product_dosing_versions`.
- Backoffice: pestaña **"Dosis / presentaciones"** en `/products/[id]`.

**Modos de regla:**

- `weight_band` — ej. Proteggo 3M: 20–40 kg → 1000 mg.
- `formula` — ej. MARVO 20: 1 tableta / 10 kg; Tulaviot: 1 ml / kg (bovinos).

**Flujo en el grafo LangGraph:**

```
IntentClassifier → ProductResolver
  → (intent dose_calculation) WeightSpeciesExtractor
    → (falta peso) repregunta → StateUpdater
    → (ok) DoseCalculator → StateUpdater
```

**Diferencia clave vs RAG:** intent `dose_calculation` **no pasa** por `HybridRetriever`. El clasificador detecta peso en la query (*"perro de 25 kg"*) y calibra el intent desde `dosage_question` cuando hay señales numéricas.

**Respuesta típica al RTC:**

- Producto, peso, regla aplicada, banda, resultado en mg/ml/tabletas.
- Pie: *"Fuente: Motor de cálculo de dosis (versión N)."*

**Salvaguardas:**

- Producto incompleto → mensaje explícito, **no inventa mg**.
- Peso fuera de rango → abstención.
- Ambigüedad Proteggo M / 3M → repregunta **antes** de calcular.

**Estado ~70%:** motor, grafo, BO CRUD e import asistido implementados; pendiente seed masivo desde Excel del laboratorio y cierre de gaps (ej. banda 10–20 kg Proteggo M).

**Archivos clave:**

| Área | Ruta |
| ---- | ---- |
| Spec | `docs/specs/011-dose-calculation-engine.md` |
| Motor | `services/common/src/biomont_common/dosing/calculator.py` |
| Nodo grafo | `services/agent/src/app/agent/graph/nodes/calculator.py` |
| Migración | `migrations/011_dose_calculation.sql` |
| UI BO | `services/backoffice-web/app/(dashboard)/products/[id]/page.tsx` |

---

### 2. Comparador comercial (Specs 012 + 013)

**Qué es:** comparación **determinista** entre producto Biomont y competidor usando cuadro Excel **COMPARATIVO COMERCIAL** (columnas dinámicas: fórmula, dosis, especies, indicaciones, precauciones, etc.).

**Fuera de alcance sprint 2:** matriz ESPECTRO estilo Proteggo (SI/NO parásitos) — spec futura con `comparison_facts`.

**Flujo en el grafo:**

```
ProductResolver → CompetitorResolver
  → (falta competidor) repregunta → StateUpdater
  → CommercialComparisonDiff
    → ComparisonRedactor (LLM) → StateUpdater
```

**Capas:**

1. **Diff determinista** — compara filas publicadas celda a celda (`CommercialComparisonDiff`).
2. **Redactor LLM** (Spec 013) — resume para chat: prioriza dosis/fórmula/especies; modos `summary` | `focus` | `full`.
3. **Guardrails** — si el LLM inventa cifras o juicios de valor → fallback a plantilla determinista.

**Producto de referencia en demo:** **MARVO 20 vs Marboxi** (set publicado v1, ~22 columnas).

**Backoffice:** sección **"Comparativa comercial"** en ficha de producto — import Excel + publicar.

**Principio comercial:** el agente **nombra diferencias sin juicio de valor** ("mejor", "recomiendo" están bloqueados).

**Archivos clave:**

| Área | Ruta |
| ---- | ---- |
| Specs | `docs/specs/012-competitor-comparison-hybrid.md`, `013-comparison-llm-redactor.md` |
| Diff | `services/agent/src/app/agent/graph/nodes/commercial_comparison_diff.py` |
| Redactor | `services/agent/src/app/agent/graph/nodes/comparison_redactor.py` |
| Migración | `migrations/012_commercial_comparison.sql` |
| Grafo | `services/agent/src/app/agent/graph/graph.py` |

---

### 3. Sistema de tickets

**Qué es:** mecanismo de escalamiento cuando el agente no puede responder con documentación validada.

**Tipos (`ticket_type`):**

| Tipo | Cuándo se crea | Mensaje al RTC |
| ---- | -------------- | -------------- |
| `no_info` | Retrieval débil / sin chunks útiles | *"No tengo esa información… Creé el ticket #XXXX"* |
| `low_confidence` | Respuesta sin citaciones o producto ambiguo | *"No tengo información con suficiente confianza…"* |
| `user_request` | Reservado para solicitud explícita del RTC | En schema; creación automática pendiente |

**Backoffice:** `/tickets` — filtros Abiertos / En curso / Resueltos; científicos actualizan estado y notas.

**Trazabilidad:** cada ticket enlaza `conversation_id`, `message_id`, summary (primeros 200 chars de la pregunta) y notas técnicas (similarity, gate, error).

**Valor para Biomont:** convierte "no sé" en **cola de trabajo** para completar catálogo o documentos.

**Archivos clave:**

| Área | Ruta |
| ---- | ---- |
| Migración | `migrations/003_conversations_tickets.sql` |
| Orquestador | `services/agent/src/app/agent/orchestrator.py` |
| UI BO | `services/backoffice-web/app/(dashboard)/tickets/page.tsx` |
| API | `services/backoffice-api/src/app/api/tickets_router.py` |

---

## Arquitectura unificada (slide técnico opcional)

```
WhatsApp RTC ──┐
               ├──► AgentOrchestrator ──► Grafo LangGraph ──┬──► product_dosing_* (cálculo)
Playground BO ─┘                                            ├──► commercial_comparison_* (comparador)
                                                            └──► knowledge_chunks (RAG)
Orquestador ──► tickets + agent_decisions (auditoría)
```

**Regla de capas:** cálculo y comparación **no leen SQL desde handlers HTTP**; pasan por repositorios en `biomont_common`.

---

## Guion de demo con puntos de pausa

**Setup previo (5 min, fuera de cámara):**

- Docker compose levantado (`agent` 8001, `backoffice-api` 8002, `backoffice-web` 3000).
- RTC de prueba habilitado en backoffice.
- Productos con datos publicados: **Proteggo 3M**, **MARVO 20**, idealmente **Tulaviot**.
- Abrir en pestañas: Conversaciones (playground), `/products`, `/tickets`, decisiones del agente.

| # | Slide / bloque | Acción en vivo | Qué decir (30–60 s) |
| - | -------------- | -------------- | ------------------- |
| 0 | Contexto Sprint 2 | Mostrar cronograma del sprint | Tres entregables de valor directo al RTC |
| 1 | Problema | Slide comparativo antes/después | RAG narrativo vs datos estructurados |
| 2 | **PAUSA DEMO 1** | Casos A1–A6 | Motor de cálculos |
| 3 | Backoffice dosis | `/products` → Proteggo 3M → pestaña Dosis | Datos editables, gaps, publicación |
| 4 | **PAUSA DEMO 2** | Casos B1–B5 | Comparador |
| 5 | Backoffice comparativa | MARVO 20 → import/publicación | Excel del lab = fuente de verdad |
| 6 | **PAUSA DEMO 3** | Casos C1–C3 | Tickets |
| 7 | Trazabilidad | Abrir decisión del turno → `graph_trace` | Auditoría reproducible |
| 8 | Cierre | Roadmap 2.3–2.4 | Trazabilidad BO, QA golden set |

---

## Casos de prueba para la demo

Canal: **Playground** en Conversaciones (mismo orquestador que WhatsApp, sin enviar al teléfono).  
País del RTC de prueba: **PE**.

### Bloque A — Motor de cálculos (PAUSA DEMO 1)

#### Caso A1 — Proteggo 3M, banda de peso (caso estrella)

**Pregunta:**

```
¿Qué dosis de Proteggo 3M le doy a un perro de 25 kg?
```

**Esperado:**

- Intent `dose_calculation`.
- Resultado **1000 mg**, banda 20–40 kg.
- Sin bloque "Fuentes:" de RAG.
- Trace incluye nodos `WeightSpeciesExtractor` → `DoseCalculator` (no `HybridRetriever`).

**Qué mostrar en pantalla:** respuesta + panel de decisión con `graph_trace`.

---

#### Caso A2 — MARVO 20, fórmula tableta/10 kg

**Pregunta:**

```
Perro de 25 kg, ¿qué tableta de MARVO 20 le doy?
```

**Esperado:**

- **2.50 tablets** (o equivalente según redondeo publicado).
- Regla tipo fórmula `1 comp/10 kg`.

---

#### Caso A3 — Tulaviot, bovino, ml/kg

**Pregunta:**

```
¿Cuál es la dosis de Tulaviot para una vaca de 450 kg?
```

**Esperado:**

- Especie bovina inferida o aplicada.
- **450 ml** (1 ml/kg).
- Fuente motor de cálculo.

---

#### Caso A4 — Repregunta por peso faltante

**Pregunta:**

```
¿Qué tableta de Proteggo M le doy?
```

**Esperado:**

- **No** calcula dosis.
- Repregunta peso del animal.
- Trace: `WeightSpeciesExtractor` → repregunta, sin `DoseCalculator`.

**Narrativa:** el agente no adivina el peso.

---

#### Caso A5 — Borde / fuera de rango

**Pregunta:**

```
Perro de 70 kg, ¿qué Proteggo 3M?
```

**Esperado:**

- Error `out_of_range` o mensaje de peso fuera del máximo documentado.
- **Sin** mg inventado.

---

#### Caso A6 — Contraste: dosis informativa sigue en RAG

**Pregunta:**

```
¿Cuál es la dosis de Proteggo en gestación?
```

**Esperado:**

- Intent **`dosage_question`** o **`safety_question`**, **no** `dose_calculation`.
- Flujo RAG con citaciones documentales.

**Narrativa:** no todo "dosis" es cálculo numérico.

---

### Bloque B — Comparador comercial (PAUSA DEMO 2)

#### Caso B1 — Resumen corto (modo summary)

**Pregunta:**

```
MARVO 20 versus Marboxi diferencias
```

**Esperado:**

- Respuesta ≤ ~12 líneas con bullets.
- Menciona **dosis** y **fórmula**.
- Cierre: *"Fuente: comparativa comercial Biomont (v1)"*.
- Hint de más diferencias (precauciones, etc.).
- Trace: `CommercialComparisonDiff` + `ComparisonRedactor`.

---

#### Caso B2 — Foco en un eje (modo focus)

**Pregunta:**

```
MARVO 20 vs Marboxi solo en dosis
```

**Esperado:**

- Respuesta centrada en DOSIS.
- Comparación concreta (ej. 1 tableta/10 kg vs mg/kg del competidor).
- No lista laboratorio/país.

**Tip presentador:** ideal como segundo mensaje tras B1 para mostrar conversación natural.

---

#### Caso B3 — Modo completo bajo pedido

**Pregunta:**

```
Listame todas las diferencias entre MARVO 20 y Marboxi
```

**Esperado:**

- Respuesta más extensa, múltiples columnas.
- Trace con `presentation_mode=full`.

---

#### Caso B4 — Competidor faltante

**Pregunta:**

```
Comparar MARVO 20 con el otro
```

**Esperado:**

- Repregunta: *"¿Con qué producto querés comparar…?"*
- Sin diff ni LLM.

---

#### Caso B5 — OPRURIX vs Apoquel (si set cargado)

**Pregunta:**

```
Comparar OPRURIX vs Apoquel
```

**Esperado:**

- Intent `comparison_with_competitor`.
- Respuesta con referencia a comparativa comercial o mensaje de catálogo incompleto si no hay set publicado.

**Nota:** verificar en BO antes de la demo si OPRURIX tiene set `complete`.

---

### Bloque C — Sistema de tickets (PAUSA DEMO 3)

#### Caso C1 — Sin información → ticket `no_info`

**Pregunta:**

```
¿Cuál es la capital de Francia?
```

**Esperado:**

- Decisión `no_match`.
- Mensaje: *"No tengo esa información en mis documentos validados"* + **#ticket**.
- Ticket nuevo en `/tickets` tipo **`no_info`**, estado **open**.

**Después:** ir a `/tickets`, filtrar Abiertos, mostrar summary = pregunta.

---

#### Caso C2 — Producto ambiguo → ticket `low_confidence`

**Pregunta:**

```
¿Cuánto cuesta el Proteggo?
```

**Esperado:**

- Repregunta Proteggo M / Proteggo 3M **o** ticket `low_confidence` según rama del grafo.
- En golden set (`evaluation/golden_set.yaml`, id `ambiguous-proteggo`): decisión `low_confidence`.

---

#### Caso C3 — Ciclo de cierre en backoffice

**Precondición:** ticket abierto de C1 o C2.

**Acción en BO:**

1. Abrir ticket → cambiar estado a **En curso**.
2. Agregar nota: *"Fuera de alcance / no aplica al catálogo veterinario"*.
3. Marcar **Resuelto**.

**Narrativa:** el científico cierra el loop; el RTC ya recibió el ID en WhatsApp.

---

### Bloque D — Trazabilidad (puente a Sprint 2.3)

Tras cualquier caso anterior, en **Decisiones del agente** (o detalle de conversación):

**Mostrar en `graph_trace`:**

- Nodos ejecutados y latencias.
- Payload de `DoseCalculator` (peso, regla, resultado).
- Payload de `ComparisonRedactor` (modo, columnas usadas, fallback si hubo).

**Mensaje:** cada respuesta es **auditable y reproducible** — requisito clínico/comercial.

---

## Slides sugeridos (estructura para la IA generadora)

1. **Portada** — Sprint 2 Biomont: cálculo, comparación, escalamiento.
2. **Agenda** — Demo en 3 actos + trazabilidad.
3. **El reto del RTC** — preguntas numéricas y comparativas en WhatsApp.
4. **Arquitectura híbrida** — RAG + motores deterministas.
5. **Motor de cálculos** — reglas, bandas, fórmulas, 0% error.
6. **Demo A1–A3** — capturas o video corto.
7. **Backoffice dosis** — completitud, gaps, publicación.
8. **Comparador** — Excel → diff → redactor LLM con guardrails.
9. **Demo B1–B2** — resumen vs foco.
10. **Tickets** — cuándo escala, tipos, flujo científico.
11. **Demo C1 + pantalla tickets**.
12. **Trazabilidad** — `graph_trace` y versiones publicadas.
13. **Avance vs plan** — 70% motor, comparador entregado, tickets operativos base.
14. **Próximos pasos** — 2.3 trazabilidad BO, 2.4 QA/prompt tuning, seed Proteggo M.
15. **Q&A**.

---

## Mensajes clave para no perder en la presentación

1. **Determinismo donde importa:** mg y comparativas salen de tablas publicadas, no del LLM.
2. **LLM con correa corta:** solo redacta comparativas ya calculadas; validador post-LLM.
3. **Abstención honesta:** incompleto o sin dato → ticket, no inventar.
4. **Operabilidad:** científicos cargan Excel, publican versiones, cierran tickets.
5. **Mismo cerebro en WhatsApp y playground:** lo que se prueba en BO es lo que ve el RTC.

---

## Riesgos / fallback si algo falla en vivo

| Riesgo | Plan B |
| ------ | ------ |
| Producto sin perfil publicado | Mostrar ficha en BO con badge "incompleto" + Caso A4 (repregunta) |
| MARVO sin comparativa | Usar captura de respuesta de tests o activar flag `AGENT_COMPARISON_LLM_REDACTOR=false` |
| LLM lento en redactor | Mencionar fallback determinista automático |
| Playground caído | Mostrar tests en `evaluation/golden_set.yaml` + trace en decisiones históricas |

---

## Referencias cruzadas

| Documento | Relación |
| --------- | -------- |
| `docs/informe-avances-semana-para-presentaciones.md` | Informe Sprint 1 (RAG, grafo base, backoffice) |
| `docs/specs/011-dose-calculation-engine.md` | Spec completa motor de dosis |
| `docs/specs/012-competitor-comparison-hybrid.md` | Spec comparador Excel |
| `docs/specs/013-comparison-llm-redactor.md` | Spec redactor LLM |
| `docs/specs/002-agent-conversations-mirror-and-playground.md` | Playground y espejo de conversaciones |
| `evaluation/golden_set.yaml` | Casos de evaluación automatizada alineados a la demo |
