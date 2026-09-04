# Setup inicial — Sistema de tickets

Este paquete ya trae resuelto: entorno Docker, dependencias, y el modelo de
datos completo. Los pasos con 🤖 son buenos candidatos para delegarle a
Antigravity; los demás son comandos fijos, no hace falta gastar tokens de
razonamiento en ellos.

## 1. Preparar el entorno

```bash
git init
cp .env.example .env
# editar .env con una DJANGO_SECRET_KEY real (cualquier string largo random sirve para dev)
```

## 2. Arrancar el proyecto Django (comando fijo)

Si todavía no existe el proyecto Django en este repo:

```bash
docker compose run --rm web django-admin startproject config .
docker compose run --rm web python manage.py startapp core
docker compose run --rm web python manage.py startapp ai
```

## 3. Copiar los archivos ya armados

Copiar `core/models.py`, `core/admin.py`, `ai/providers.py` y `ai/tasks.py`
(los que están en este paquete) a las carpetas correspondientes del
proyecto recién creado, pisando los archivos vacíos que genera Django.

## 4. Configurar settings.py 🤖

Antigravity puede completar esto rápido siguiendo estos puntos (ya
definidos, sin ambigüedad):

- `AUTH_USER_MODEL = "core.Usuario"` (¡antes de la primera migración!)
- Agregar `"core"`, `"ai"`, `"django_htmx"` a `INSTALLED_APPS`
- Configurar `DATABASES` contra Postgres usando las variables de `.env`
  (vía `python-decouple`, ya está en requirements.txt)
- Agregar el middleware de `django_htmx`
- Configurar `HUEY` como se indica en el docstring de `ai/tasks.py`

## 5. Migraciones (comando fijo)

```bash
docker compose up -d db
docker compose run --rm web python manage.py makemigrations
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py createsuperuser
```

## 6. Cargar los proveedores de IA evaluados

Desde el admin (`/admin/`), una vez levantado el server, cargar manualmente
3 filas en `ModeloIA` (una por Groq/Gemini/OpenRouter) y crear la fila de
`ConfiguracionIA` apuntando a la que quieras probar primero. Las API keys
van en `.env`, no en el admin.

## 7. Levantar todo

```bash
docker compose up
```

La app queda en `http://localhost:8000`, el admin en `/admin/`.

## 8. A partir de acá, delegar a Antigravity 🤖

- Vistas + templates + HTMX/Tailwind siguiendo las pantallas del prototipo Figma
- Implementación real de `GroqProvider`, `GeminiProvider`, `OpenRouterProvider`
  en `ai/providers.py` (las firmas ya están, solo falta la llamada HTTP)
- Conectar `generar_analisis_ticket` al guardar un ticket nuevo
- Deploy en Railway/Render (pedime los archivos de config cuando llegues a ese paso)
