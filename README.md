# Publicador Zap ⚡

Herramienta web para extraer publicaciones de Mercado Libre, optimizarlas con Claude AI y republicarlas en la cuenta de Miraarlo — todo desde el celular.

## Flujo principal

```
URL o MLM → Extracción + Auto-categoría → Atributos dinámicos → Edición con Claude AI → Publicar en Miraarlo
```

## Características

**Extracción inteligente** — Acepta URLs de producto, IDs tipo `MLM123456789` y productos de catálogo. Combina datos de la API pública con scraping vía `curl_cffi` (impersonación TLS de Chrome) para evadir bloqueos anti-bot de ML.

**Auto-categoría y atributos** — Al extraer, el sistema predice la categoría por título si la API no la devuelve. Consulta los atributos obligatorios de la categoría y los renderiza como campos editables con dropdowns para valores permitidos y pre-llenado automático con datos del item original.

**Optimización con Claude AI** — Cinco acciones integradas con la API de Anthropic:
- Mejorar título (máx. 60 caracteres)
- Reescribir descripción (texto plano, fluido)
- Optimizar SEO para búsquedas de ML
- Adaptar tono a la voz de Miraarlo
- Agregar palabras clave de forma natural

**Publicación robusta** — Detecta automáticamente si la cuenta usa el modelo `user_product_seller` (envía `family_name`) o el estándar (envía `title`). Maneja fallback de shipping (`me2` → `not_specified`), herencia de atributos del item original (GTIN, EAN, UPC, SIZE_GRID_ID), dimensiones de paquete, e inyección de descripción post-publicación.

**Modo creación en blanco** — Permite crear productos desde cero: sube fotos desde cámara o galería, escribe título y categoría, y pasa al editor completo con atributos dinámicos.

**Exportación** — Genera Excel formateado del listing, rellena plantillas oficiales de ML, y descarga fotos como ZIP.

## Setup

### 1. Clonar e instalar

```bash
git clone https://github.com/devmiraarmx/miraarlo-replicator.git
cd miraarlo-replicator

python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

### 2. Configurar variables de entorno

```bash
cp .env.example .env
```

Edita `.env` con tus credenciales:

| Variable | Descripción |
|----------|-------------|
| `ML_CLIENT_ID` | ID de la app registrada en ML Developers |
| `ML_CLIENT_SECRET` | Secret de la app ML |
| `ML_REDIRECT_URI` | URL de callback OAuth (default: `http://localhost:5000/auth/callback`) |
| `ML_ACCESS_TOKEN` | Token de acceso (se puede obtener vía OAuth desde la app) |
| `ML_REFRESH_TOKEN` | Refresh token (se actualiza automáticamente) |
| `ANTHROPIC_API_KEY` | API key de Anthropic para Claude |

### 3. Ejecutar

```bash
python app.py
```

Abre `http://localhost:5000`

## Obtener tokens de Mercado Libre

**Desde la app (recomendado)** — Clic en ⚙️ → OAuth ML. Autoriza en Mercado Libre y los tokens se guardan automáticamente en `.env`.

**Manual** — Si tienes tokens de otra fuente (VBA, Postman, etc.), pégalos directamente en el `.env`.

## Estructura del proyecto

```
miraarlo-replicator/
├── app.py              # Flask — rutas, OAuth, exportación Excel/ZIP
├── meli.py             # Cliente ML: extracción, scraping, categorías, publicación
├── claude_helper.py    # 5 acciones de IA vía Anthropic API
├── templates/
│   └── index.html      # UI mobile-first (Gold × Purple)
├── .env.example        # Plantilla de variables (sin credenciales)
├── .gitignore
└── requirements.txt
```

## Endpoints

| Ruta | Método | Descripción |
|------|--------|-------------|
| `/extract` | POST | Extrae datos + auto-categoría + atributos obligatorios |
| `/category-attributes` | POST | Consulta atributos obligatorios de una categoría |
| `/category-path` | POST | Devuelve breadcrumb de la categoría |
| `/predict-category` | POST | Predice categoría por título |
| `/enhance` | POST | Mejora contenido con Claude AI |
| `/publish` | POST | Publica en Miraarlo con atributos dinámicos |
| `/export-excel` | POST | Genera Excel formateado del listing |
| `/fill-template` | POST | Rellena plantilla oficial de ML |
| `/download-photos` | POST | Descarga fotos como ZIP |
| `/auth` | GET | Inicia flujo OAuth con ML |
| `/auth/callback` | GET | Callback OAuth — guarda tokens en `.env` |
| `/refresh-token` | POST | Renueva access token |
| `/me` | GET | Valida token y devuelve datos de la cuenta |

## Stack técnico

- **Backend**: Flask + Python 3.10+
- **Scraping**: `curl_cffi` con impersonación Chrome 136, `BeautifulSoup`
- **AI**: Anthropic API (Claude Sonnet)
- **ML API**: OAuth 2.0, endpoints de items/categories/pictures
- **Frontend**: HTML/CSS/JS vanilla, Inter + JetBrains Mono, Lucide icons
- **Exportación**: `openpyxl` para Excel

## Notas

- La extracción funciona sin token para publicaciones públicas
- Para publicar se requieren tokens válidos de la cuenta Miraarlo
- Los atributos obligatorios se cargan automáticamente al extraer; si cambias la categoría, usa "Recargar atributos"
- Las imágenes se suben vía API de ML (URL o base64) antes de publicar

---

Hecho con ⚡ por devmiraarmx
