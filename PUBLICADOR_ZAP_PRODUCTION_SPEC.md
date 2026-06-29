# Publicador Zap — Especificación de Producción

> Documento de referencia para implementar con Claude Code.
> Generado el 29 de junio de 2026.

---

## 1. Resumen del proyecto

Publicador Zap es una herramienta web (PWA) que permite a vendedores de Mercado Libre extraer publicaciones existentes, optimizarlas con inteligencia artificial (Claude API), y republicarlas en sus propias cuentas. El sistema opera como SaaS multi-tenant con modelo de créditos prepagados.

**Repositorio actual:** https://github.com/devmiraarmx/miraarlo-replicator
**Estado actual:** Prototipo funcional (single-user, tokens en .env, sin autenticación)

---

## 2. Decisiones de arquitectura confirmadas

| Decisión | Elección |
|----------|----------|
| Hosting | Render (web service + PostgreSQL managed) |
| Framework | Flask + Jinja2 templates + Blueprints |
| Base de datos | PostgreSQL (Render add-on) |
| ORM | SQLAlchemy + Alembic (migraciones) |
| Autenticación | Dual: email+contraseña Y OAuth Mercado Libre |
| Tokens ML | Self-service por cliente, encriptados en DB |
| Monetización | Paquetes de créditos prepagados (sin suscripción) |
| Procesador de pagos | Mercado Pago Checkout API |
| PWA | Básica: manifest.json + service worker (instalable) |
| Frontend | Jinja2 templates con CSS/JS separados |
| Seguridad | OWASP Top 10 completo |
| Admin | Panel con gestión de usuarios, créditos y stats |

---

## 3. Estructura del proyecto

```
publicador-zap/
├── app/
│   ├── __init__.py                 # Application factory + config
│   ├── config.py                   # Configuración por entorno (dev/staging/prod)
│   ├── extensions.py               # Inicialización de extensiones (db, login, csrf, limiter)
│   ├── models.py                   # Modelos SQLAlchemy
│   │
│   ├── auth/                       # Blueprint: autenticación
│   │   ├── __init__.py
│   │   ├── routes.py               # Login, registro, OAuth ML, logout
│   │   └── forms.py                # WTForms (login, registro)
│   │
│   ├── editor/                     # Blueprint: herramienta principal
│   │   ├── __init__.py
│   │   ├── routes.py               # Extract, enhance, publish, export
│   │   ├── meli.py                 # Cliente ML (refactorizado desde meli.py actual)
│   │   └── claude_helper.py        # Integración Claude API
│   │
│   ├── billing/                    # Blueprint: créditos y pagos
│   │   ├── __init__.py
│   │   └── routes.py               # Planes, checkout Mercado Pago, webhooks
│   │
│   ├── dashboard/                  # Blueprint: panel del usuario
│   │   ├── __init__.py
│   │   └── routes.py               # Historial, stats, configuración cuenta
│   │
│   ├── admin/                      # Blueprint: panel de administración
│   │   ├── __init__.py
│   │   └── routes.py               # Gestión usuarios, créditos, stats globales
│   │
│   ├── templates/
│   │   ├── base.html               # Layout maestro (nav, footer, PWA meta tags)
│   │   ├── auth/
│   │   │   ├── login.html
│   │   │   └── register.html
│   │   ├── editor/
│   │   │   └── index.html          # El editor actual (refactorizado)
│   │   ├── billing/
│   │   │   ├── plans.html          # Paquetes de créditos
│   │   │   └── success.html        # Confirmación de compra
│   │   ├── dashboard/
│   │   │   └── home.html           # Historial + stats del usuario
│   │   └── admin/
│   │       └── panel.html          # Panel administrativo
│   │
│   └── static/
│       ├── css/
│       │   └── main.css            # Estilos extraídos del index.html actual
│       ├── js/
│       │   ├── editor.js           # Lógica del editor extraída
│       │   └── app.js              # Utilidades compartidas
│       ├── manifest.json           # PWA manifest
│       ├── sw.js                   # Service worker básico
│       └── icons/                  # Íconos PWA (192x192, 512x512)
│
├── migrations/                     # Alembic
├── .env.example
├── .gitignore
├── Dockerfile                      # Para Render (resuelve curl_cffi)
├── requirements.txt
├── render.yaml                     # Render Blueprint (IaC)
└── README.md
```

---

## 4. Modelo de datos (PostgreSQL)

### 4.1 Tabla: users

```sql
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255),               -- NULL si se registró solo con ML OAuth
    nickname        VARCHAR(100),
    ml_user_id      BIGINT UNIQUE,              -- ID de Mercado Libre (nullable)
    ml_access_token TEXT,                        -- Encriptado con Fernet
    ml_refresh_token TEXT,                       -- Encriptado con Fernet
    ml_token_expires_at TIMESTAMP,
    is_admin        BOOLEAN DEFAULT FALSE,
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW(),
    last_login      TIMESTAMP
);
```

### 4.2 Tabla: credit_packages

```sql
CREATE TABLE credit_packages (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(50) NOT NULL,        -- 'trial', 'starter', 'pro', 'business'
    credits         INTEGER NOT NULL,
    price_mxn       DECIMAL(10,2) NOT NULL,      -- 0.00 para trial
    is_active       BOOLEAN DEFAULT TRUE
);

-- Datos iniciales:
-- ('trial',    10,     0.00)
-- ('starter',  50,   299.00)
-- ('pro',     200,   799.00)
-- ('business',500,  1499.00)
```

### 4.3 Tabla: credit_transactions

```sql
CREATE TABLE credit_transactions (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id),
    package_id      INTEGER REFERENCES credit_packages(id),
    credits         INTEGER NOT NULL,            -- Créditos otorgados
    amount_mxn      DECIMAL(10,2) DEFAULT 0,     -- Monto pagado
    mp_payment_id   VARCHAR(100),                -- ID de pago Mercado Pago
    mp_status       VARCHAR(50),                 -- approved, pending, rejected
    expires_at      TIMESTAMP,                   -- Solo para trial (7 días)
    created_at      TIMESTAMP DEFAULT NOW()
);
```

### 4.4 Tabla: publications

```sql
CREATE TABLE publications (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id),
    source_mlm      VARCHAR(20),                 -- MLM original extraído
    new_mlm         VARCHAR(20),                 -- MLM publicado (resultado)
    title           VARCHAR(100),
    category_id     VARCHAR(20),
    price           DECIMAL(12,2),
    status          VARCHAR(20) DEFAULT 'draft', -- draft, published, failed
    ai_actions_used TEXT[],                       -- Array de acciones Claude usadas
    credits_used    INTEGER DEFAULT 1,
    created_at      TIMESTAMP DEFAULT NOW()
);
```

### 4.5 Vista: user_credit_balance

```sql
CREATE VIEW user_credit_balance AS
SELECT
    u.id AS user_id,
    COALESCE(SUM(
        CASE
            WHEN ct.expires_at IS NULL OR ct.expires_at > NOW()
            THEN ct.credits
            ELSE 0
        END
    ), 0)
    - COALESCE((SELECT SUM(credits_used) FROM publications WHERE user_id = u.id AND status = 'published'), 0)
    AS available_credits
FROM users u
LEFT JOIN credit_transactions ct ON ct.user_id = u.id AND ct.mp_status IN ('approved', NULL)
GROUP BY u.id;
```

---

## 5. Autenticación

### 5.1 Email + contraseña

- Registro: email + contraseña (mínimo 8 caracteres)
- Hash: `bcrypt` via `flask-bcrypt`
- Sesiones: `flask-login` con cookies seguras
- Al registrar: se otorga paquete trial automáticamente (10 créditos, expiran en 7 días)

### 5.2 OAuth Mercado Libre

- Flujo: botón "Conectar con Mercado Libre" → redirect a `auth.mercadolibre.com.mx` → callback con code → exchange por tokens → consultar `/users/me` para obtener `user_id`, `nickname`, `email`
- Si el email ya existe en DB: vincular cuenta ML al usuario existente
- Si no existe: crear usuario nuevo con datos de ML (sin password_hash)
- Tokens ML se encriptan con `cryptography.fernet` antes de guardar en DB
- La clave Fernet se almacena en variable de entorno `FERNET_KEY`

### 5.3 Refresh de tokens ML

- Antes de cada operación ML: verificar `ml_token_expires_at`
- Si está vencido o por vencer (< 30 min): refresh automático y actualizar en DB
- Si el refresh falla: marcar al usuario para re-autenticación

---

## 6. Sistema de créditos

### 6.1 Paquetes

| Nombre | Créditos | Precio MXN | Expiración |
|--------|----------|------------|------------|
| Trial | 10 | Gratis | 7 días desde registro |
| Starter | 50 | $299 | Sin expiración |
| Pro | 200 | $799 | Sin expiración |
| Business | 500 | $1,499 | Sin expiración |

### 6.2 Consumo

- Cada publicación exitosa (status = 'published') consume 1 crédito
- Las acciones de Claude AI (mejorar título, reescribir, etc.) NO consumen créditos adicionales
- Un draft (extracción sin publicar) NO consume créditos
- Si el usuario no tiene créditos: bloquear botón de publicar, mostrar CTA a comprar paquete

### 6.3 Flujo de compra con Mercado Pago

1. Usuario selecciona paquete en `/billing/plans`
2. Backend crea preferencia de pago via Mercado Pago Checkout API
3. Redirect a checkout de Mercado Pago
4. Mercado Pago redirige a `/billing/success?payment_id=...` o `/billing/failure`
5. Webhook de MP notifica a `/billing/webhook` (IPN)
6. Backend valida el pago vía API de MP y acredita créditos en `credit_transactions`

---

## 7. Seguridad (OWASP Top 10)

### 7.1 Implementar

| Protección | Herramienta |
|------------|-------------|
| CSRF | `flask-wtf` (CSRFProtect) en todos los forms |
| XSS | Jinja2 auto-escaping (habilitado por default) |
| SQL Injection | SQLAlchemy ORM (queries parametrizadas) |
| Passwords | `flask-bcrypt` (bcrypt hash) |
| Tokens ML en DB | `cryptography.fernet` (AES-128-CBC) |
| Rate limiting | `flask-limiter` (ej: 5 publicaciones/min, 20 extracciones/min) |
| HTTPS | Render lo provee automáticamente |
| Cookies | HttpOnly=True, Secure=True, SameSite='Lax' |
| CSP headers | `flask-talisman` (Content Security Policy) |
| Input validation | Validar en servidor TODO lo que viene del frontend |

### 7.2 Variables de entorno requeridas en producción

```
SECRET_KEY=<random-64-chars>
FERNET_KEY=<generated-with-Fernet.generate_key()>
DATABASE_URL=<postgresql-url-from-render>
ML_CLIENT_ID=3509386763056859
ML_CLIENT_SECRET=<secret>
ANTHROPIC_API_KEY=<key>
MP_ACCESS_TOKEN=<mercado-pago-access-token>
MP_PUBLIC_KEY=<mercado-pago-public-key>
FLASK_ENV=production
```

---

## 8. Panel de administración

### 8.1 Acceso

- Solo usuarios con `is_admin = TRUE`
- Ruta: `/admin/`
- Protegido con decorador `@admin_required`

### 8.2 Funcionalidades

**Gestión de usuarios:**
- Lista de usuarios con filtros (activos, por fecha, por créditos)
- Ver detalle de usuario (créditos, publicaciones, tokens ML vinculados)
- Activar/desactivar usuarios
- Otorgar créditos manualmente (cortesía)

**Gestión de créditos:**
- Historial de transacciones (compras, trials, cortesías)
- Filtro por estado de pago Mercado Pago
- Resumen de créditos otorgados vs consumidos

**Estadísticas:**
- Ingresos totales y por período (diario, semanal, mensual)
- Usuarios registrados y activos
- Publicaciones totales y por usuario
- Créditos vendidos vs consumidos
- Uso de acciones Claude AI (cuál se usa más)
- Top 10 usuarios por publicaciones

---

## 9. PWA (básica)

### 9.1 manifest.json

```json
{
  "name": "Publicador Zap",
  "short_name": "Zap",
  "description": "Publica en Mercado Libre con IA",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0c0318",
  "theme_color": "#f5b731",
  "icons": [
    { "src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

### 9.2 Service worker

- Cache de assets estáticos (CSS, JS, fuentes, íconos)
- Estrategia network-first para API calls
- Página offline básica si no hay conexión

---

## 10. Deploy en Render

### 10.1 render.yaml (Blueprint)

```yaml
services:
  - type: web
    name: publicador-zap
    runtime: docker
    repo: https://github.com/devmiraarmx/miraarlo-replicator
    branch: main
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: publicador-zap-db
          property: connectionString
      - key: SECRET_KEY
        generateValue: true
      - key: FLASK_ENV
        value: production

databases:
  - name: publicador-zap-db
    plan: starter
    databaseName: publicador_zap
```

### 10.2 Dockerfile

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    libcurl4-openssl-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:create_app()"]
```

---

## 11. Fases de implementación

### Fase 1 — Fundación (prioridad máxima)
1. Reestructurar proyecto a Flask factory pattern + Blueprints
2. Configurar PostgreSQL con SQLAlchemy + modelos
3. Implementar autenticación (email+password + OAuth ML)
4. Migrar tokens ML de .env a DB encriptados
5. Refactorizar index.html: separar CSS/JS, integrar en base.html
6. Dockerfile + deploy en Render

### Fase 2 — Monetización
7. Sistema de créditos (modelo, consumo, validación)
8. Trial automático al registrar (10 créditos, 7 días)
9. Integración Mercado Pago Checkout API
10. Página de planes + flujo de compra
11. Webhook de confirmación de pago

### Fase 3 — Dashboard + Admin
12. Dashboard del usuario (historial, créditos, stats)
13. Panel de administración (usuarios, transacciones, stats)
14. Otorgar créditos manualmente

### Fase 4 — Pulido
15. PWA (manifest, service worker, íconos)
16. Rate limiting + CSP headers
17. Página de landing/marketing
18. Tests básicos (auth, créditos, publicación)

---

## 12. Identidad visual

- **Nombre:** Publicador Zap
- **Paleta:** Gold (#f5b731) × Deep Purple (#8b5cf6) sobre fondos oscuros (#0c0318)
- **Tipografía:** Inter (UI) + JetBrains Mono (datos técnicos)
- **Íconos:** Lucide
- **Tono:** Profesional, directo, confiable

---

## 13. Dependencias de producción (requirements.txt)

```
flask>=3.0.0
flask-sqlalchemy>=3.1.0
flask-migrate>=4.0.0
flask-login>=0.6.3
flask-bcrypt>=1.0.1
flask-wtf>=1.2.0
flask-limiter>=3.5.0
flask-talisman>=1.1.0
sqlalchemy>=2.0.0
psycopg2-binary>=2.9.9
requests>=2.31.0
python-dotenv>=1.0.0
anthropic>=0.25.0
beautifulsoup4>=4.12.0
openpyxl>=3.1.0
curl_cffi>=0.7.0
cryptography>=42.0.0
gunicorn>=22.0.0
mercadopago>=2.2.0
```

---

*Este documento es la fuente de verdad para la implementación. Cada fase debe completarse y probarse antes de avanzar a la siguiente.*
