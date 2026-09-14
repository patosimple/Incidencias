# Sistema de tickets — Incidencias

Sistema interno de gestión de incidencias/errores para las apps **Balances** y
**Financiamiento**. Incluye login por roles (solicitante / desarrollador /
coordinador), tickets, comentarios con edición/soft-delete, adjuntos y una capa
de **análisis IA** que resume cada ticket usando un LLM (Groq / Gemini /
OpenRouter / NVIDIA / Ollama).

- Backend: **Django 5.x** + **PostgreSQL** (`psycopg 3`)
- Cola de tareas: **Huey + PostgresHuey** (no requiere Redis)
- Frontend: templates Django + **HTMX** + **Tailwind CDN** (dark mode incluido)
- Deploy: **Render** (Gunicorn + Whitenoise) + **Neon** (Postgres) — ver `render.yaml`

---

## Primeros pasos

### 1. Requisitos

- Python **3.11 o superior** (el `Dockerfile` usa `python:3.12-slim`)
- PostgreSQL (local) **o** Docker (para el `docker-compose.yml` provisto)
- (Opcional, solo para IA) una API key de al menos un proveedor

### 2. Clonar y preparar el entorno

```bash
git clone <url-del-repo>
cd Incidencias
cp .env.example .env
```

> `.env` NO se commitea (está en `.gitignore`). `.env.example` es la plantilla
> con todas las variables documentadas. Completá al menos `DATABASE_URL` (sin
> esta variable el sitio no arranca).

#### Opción A — venv local (recomendado en dev)

```bash
# Windows
python -m venv venv
.\venv\Scripts\activate              # PowerShell: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Para correr todo comando de Django usá el Python del venv:

```bash
# Windows
.\venv\Scripts\python.exe manage.py <comando>
# Linux/macOS
venv/bin/python manage.py <comando>
```

#### Opción B — Docker

El `docker-compose.yml` levanta un **Postgres 16** (`db`) y la **app** (`web`).
Con Docker, la `DATABASE_URL` apunta al servicio `db` de la red de compose:

```bash
# en .env
DATABASE_URL=postgresql://tickets:tickets@db:5432/tickets
```

```bash
docker compose up --build
```

La app queda en `http://localhost:8000` y el admin en `http://localhost:8000/admin/`.

> ¿Solo Postgres local y la app en el venv? Levantá únicamente la BD:
> `docker compose up -d db` y andá por la **Opción A** apuntando
> `DATABASE_URL` a `postgresql://tickets:tickets@localhost:5432/tickets`.

### 3. Arrancar la base y migrar

```bash
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py createsuperuser   # el único usuario con acceso a /admin/
```

### 4. Cargar datos base (`seed_init`)

```bash
.\venv\Scripts\python.exe manage.py seed_init
.\venv\Scripts\python.exe manage.py seed_init --update_prompt   # pisa el prompt existente
```

**Qué hace `seed_init`** (puede correrse las veces que quieras; es idempotente):

- Crea los **Sistemas** del catálogo: `BALANCES` y `FINANCIAMIENTO`, cada uno con
  su campo `prompt` (descripción del sistema usada como contexto por la IA).
  Solo lo completa si está vacío (no pisa ediciones del admin). El flag
  `--update_prompt` sobrescribe **siempre** el prompt con la versión del seed
  (útil para sincronizar el prompt en un entorno como Neon desde un `.py` nuevo).
- Crea el **catálogo de `ModeloIA`**: Groq, Gemini, OpenRouter, NVIDIA y Ollama,
  cada uno con su `formato_salida` (cómo pedirle el JSON de salida al modelo).
- Crea la fila singleton de **`ConfiguracionIA`** con el modelo **Groq** como
  activo (si todavía no hay configuración).

> El **modelo/proveedor de IA activo** se cambia desde el admin
> (`/admin/core/configuracionia/`) → elegís qué `ModeloIA` se usa al analizar.
> Las **API keys** van en `.env`, nunca en la base.

### 5. (Opcional) Tickets de demostración (`seed_tickets`)

```bash
.\venv\Scripts\python.exe manage.py seed_tickets            # 5 solicitantes + N tickets
.\venv\Scripts\python.exe manage.py seed_tickets --tickets 20
.\venv\Scripts\python.exe manage.py seed_tickets --reset    # borra SOLO lo del seed
.\venv\Scripts\python.exe manage.py seed_tickets --reset_all  # limpieza total (no recrea)
```

**Qué hace `seed_tickets`**: crea **5 usuarios solicitantes** de prueba (todos
con acceso a BALANCES + FINANCIAMIENTO, password `soli`) y **5 tickets reales
del dominio** (incidencias de Balances/Financiamiento, una por solicitante,
preservando el sistema original). Además crea el **desarrollador demo
`dev.demo`** (password `desa`), que es `is_staff` con acceso al admin para
gestionar usuarios/sistemas/modelos IA. El flag `--tickets N` controla la
cantidad de tickets (`--tickets 20` crea 20; **default: 5**, recorre en ciclo
los 5 reales reasignando solicitantes sin repetir).

| Usuario demo | |
|---|---|
| `maria.lopez`, `carlos.gonzalez`, `lucia.fernandez`, `joaquin.rodriguez`, `valentina.martinez` (Solicitantes) | password: `soli` |
| `dev.demo` (Desarrollador) | password: `desa` |

`--reset` borra exclusivamente esos 5 usuarios, `dev.demo` y sus tickets (no
toca otros users). `--reset_all` hace una **limpieza total**: borra todos los
tickets/comentarios/adjuntos del sistema (incluidos los `soft-deleted`), los
usuarios del seed y `dev.demo`, conserva Sistemas/catálogo IA y usuarios
no-demo, y reinicia el contador de id de `Ticket` a 0 (el próximo ticket es el
**1**). No recrea nada: tras `--reset_all` corré `seed_tickets` de nuevo si
querés sembrar. Tip: `on_delete` de `Ticket.solicitante` es `PROTECT`, no se
puede borrar un usuario que tenga tickets asociados.

### 6. Levantar la app

```bash
.\venv\Scripts\python.exe manage.py runserver
```

Web: `http://localhost:8000` · Admin: `http://localhost:8000/admin/`

---

## Roles y acceso

- `rol` en el usuario = permiso de negocio (Solicitante / Desarrollador /
  Coordinador). `is_staff` / `is_superuser` = acceso al panel `/admin/`. Están
  desacoplados a propósito: un dev puede no ser staff.
- **Solicitante**: ve y reporta sus tickets, comenta, cierra/reabre los propios.
- **Desarrollador** (y Coordinador): ve tickets de sus sistemas, toma/libera
  tickets, comenta, cierra/reabre, genera el **análisis IA**.
- **Superuser**: ve todo sin restricciones de rol/sistema.

## Variable clave de `.env`

| Variable | Qué hace |
|---|---|
| `DATABASE_URL` | **Obligatoria**. URL de Postgres (Neon en producción o local). |
| `DJANGO_SECRET_KEY` | Clave secreta de Django. En dev se usa un default inseguro si falta. |
| `DJANGO_DEBUG` | `True` en dev / `False` en producción. |
| `DJANGO_ALLOWED_HOSTS` | Hosts permitidos. `*` abre a cualquier host (no comentar para "restringir": el default es `['*']`). Vacía = solo `localhost`/`127.0.0.1`/`.onrender.com`. |
| `GROQ_API_KEY`, `GOOGLE_AI_API_KEY`, `OPENROUTER_API_KEY`, `NVIDIA_API_KEY` | API keys de IA (solo se usa la del proveedor activo). |
| `OLLAMA_HOST` | Host de Ollama (opcional, default `http://localhost:11434`). Puede venir como bind del daemon (`0.0.0.0`); el provider lo normaliza a URL de cliente (`http://127.0.0.1:11434`) vía `_normalizar_host_ollama()`. |
| `MODO_FILTRO_CLIENTE` | `True` = filtrado/paginación en el navegador; `False` = server-side con HTMX. |
| `AI_IMMEDIATE` | `True` = Huey síncrono (sin worker); `False` = cola real, levantar el worker con `manage.py run_huey`. |

## IA — análisis de tickets

- Un **desarrollador/coordinador** abre un ticket → botón **Analizar/Reanalizar**
  → la app llama al proveedor activo (2-8 s típicos con Groq) y guarda un
  `AnalisisIA` de tipo TÉCNICO con la salida estructurada.
- El prompt usa **mensajes `system`/`user` separados**: la descripción del
  ticket se envía en **texto plano**, con **contexto** (título, sistema y su
  `Sistema.prompt`) y con **defensa anti prompt-injection** (la descripción es
  SOLO el dato a analizar, nunca instrucciones).
- El campo `informacion_faltante` se genera y guarda en la DB pero no se muestra
  en la UI por ahora.
- Si el proveedor activo no tiene API key configurada, verás un error (ej.
  `401`) al analizar.

## Extras útiles

- **Worker de cola real** (con `AI_IMMEDIATE=False`): `.\venv\Scripts\python.exe manage.py run_huey`
- **Adjuntos**: se guardan en `media/` (storage local/efímero). En producción
  (Render) los archivos físicos no persisten entre redeploys; la BD conserva los
  registros. Migración a Supabase Storage es un pendiente.
- El detalle del contexto del proyecto y la arquitectura vive en `AGENTS.md`.