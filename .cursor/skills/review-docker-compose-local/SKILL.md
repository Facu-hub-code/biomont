---
name: review-docker-compose-local
description: >-
  Revisar logs de Docker Compose local del monorepo Biomont (agent,
  backoffice-api, backoffice-web): comandos típicos, seguir en vivo,
  filtrar por servicio o contenedor y correlacionar con errores de Next.js SSR
  o APIs Python. Usar cuando haga falta debug local con compose levantado,
  errores opacos en producción dentro del contenedor web, o tras cambios entre
  servicios sin rebuild.
---

# Logs de Docker Compose (local Biomont)

Contexto del repo: el archivo Compose es **`docker-compose.yml`** en la raíz del monorepo. La red se llama `biomont-network`. La base PostgreSQL **no** está en Compose (Railway + `DATABASE_URL`).

## Servicios y contenedores

| Servicio Compose | `container_name`     | Puerto host (mapeado) |
|------------------|-------------------------|------------------------|
| `agent`          | `biomont-agent`        | `8001`                 |
| `backoffice-api` | `biomont-backoffice-api` | `8002`               |
| `backoffice-web` | `biomont-backoffice-web` | `3000`               |

Los tres leen **`./.env`** vía `env_file`.

## Pre-requisitos

- Compose v2 desde la **raíz del repo** (`cd` al directorio donde vive `docker-compose.yml`).
- Contenedores en ejecución (`docker compose ps`).

## Comandos base (priorizar estos)

Seguir todos los servicios (últimas líneas + stream):

```bash
docker compose logs -f --tail 200
```

Solo un servicio (nombre lógico de Compose):

```bash
docker compose logs -f --tail 200 backoffice-web
docker compose logs -f --tail 200 backoffice-api
docker compose logs -f --tail 200 agent
```

Por nombre de contenedor (equivalente si `compose` no está en PATH):

```bash
docker logs -f --tail 200 biomont-backoffice-web
```

Ventana de tiempo útil después de reproducir el error:

```bash
docker compose logs --since 10m backoffice-web backoffice-api
```

Timestamps:

```bash
docker compose logs -f -t --tail 100 agent
```

## Qué revisar según síntoma

- **Errores en navegador al cargar el backoffice o “chat de prueba” / Server Components** (`digest`, mensaje omitido): mirar **`backoffice-web`** y **`backoffice-api`** al mismo momento. Los detalles reales del error de React/Next suelen estar en **`backoffice-web`**; llamadas fallidas aparecen en **`backoffice-api`**.
- **`401`, auth, cookies**: `backoffice-web` (SSR / server actions) + `backoffice-api` (`/auth/*`).
- **RAG, WhatsApp, agente**: `agent` (+ a veces `backoffice-api` si proxy o BO llama al agent).

## Nota sobre mensajes omitidos en “production”

En Compose, **`backoffice-web`** usa `NODE_ENV=production`; Next puede ocultar el mensaje exacto del error en el cliente. Para diagnóstico, correlationar **`docker compose logs backoffice-web`** en el segundo del fallo; si hace falta el stack trace completo, conviene ejecutar **`npm run dev`** en `services/backoffice-web` contra la misma API o ajustar temporalmente el entorno de build (solo para debug local), fuera del alcance rutinario de esta skill.

## Evitar fugas sensibles en el chat del agente

- No pegar líneas enteras que contengan URLs con tokens, cookies o `DATABASE_URL`.
- Preferir hashes `digest=` y rutas públicas conocidas (`/health`, rutas API documentadas).

## Ver estado rápido

```bash
docker compose ps
docker inspect biomont-agent --format '{{.State.Health.Status}}'
```

(repetir para otros contenedores si el healthcheck no pasa.)
