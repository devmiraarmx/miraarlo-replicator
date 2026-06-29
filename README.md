# Miraarlo Replicator 🟡

App web para extraer publicaciones de Mercado Libre, editarlas con Claude y publicarlas en la cuenta de Miraarlo.

## Flujo

```
Extraer (URL o MLM) → Auto-categoría + Atributos dinámicos → Editar con Claude → Publicar en Miraarlo
```

## Novedades v2

- **Auto-detección de categoría**: al extraer, si la API no devuelve categoría, el sistema la predice automáticamente por título
- **Atributos dinámicos obligatorios**: se consultan los atributos requeridos de la categoría y se renderizan como campos editables
- **Pre-llenado inteligente**: los atributos que ya vienen en los datos extraídos se pre-llenan automáticamente
- **Campos con valores permitidos**: si ML define opciones válidas para un atributo, se muestra un dropdown
- **Botón "Recargar atributos"**: permite refrescar los atributos si cambias la categoría manualmente
- **Fix sidebar atributos**: ahora muestra nombre y valor correctamente (antes mostraba `[object Object]`)

## Setup rápido

### 1. Clonar y entrar al proyecto
```bash
cd miraarlo-replicator
```

### 2. Crear entorno virtual e instalar dependencias
```bash
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

pip install -r requirements.txt
```

### 3. Configurar variables de entorno
```bash
cp .env.example .env
```

Edita `.env` y llena:
- `ML_CLIENT_SECRET` — tu clave secreta de la app ML de Miraarlo
- `ML_ACCESS_TOKEN` — token actual de Miraarlo
- `ML_REFRESH_TOKEN` — refresh token de Miraarlo
- `ANTHROPIC_API_KEY` — tu API key de Anthropic

### 4. Correr la app
```bash
python app.py
```

Abre http://localhost:5000

---

## Obtener tokens ML

### Opción A — Desde el VBA (rápido)
Si tienes el macro `Obtener_Campo.bas` activo en Excel con tokens válidos, copia los valores de `m_AccessToken` y `m_RefreshToken` directamente al `.env`.

### Opción B — OAuth desde la app
1. Asegúrate de que `ML_CLIENT_SECRET` esté en el `.env`
2. Haz clic en **🔑 OAuth ML** en la app
3. Autoriza en Mercado Libre
4. Los tokens se guardan automáticamente en el `.env`

---

## Estructura del proyecto

```
miraarlo-replicator/
├── app.py              # Flask — rutas principales + endpoint /category-attributes
├── meli.py             # Cliente ML API + auto-categoría + atributos dinámicos
├── claude_helper.py    # Integración Claude API
├── templates/
│   └── index.html      # Interfaz con atributos dinámicos
├── .env                # Variables (no subir a git)
├── .env.example        # Plantilla de variables
└── requirements.txt
```

---

## Endpoints API

| Ruta | Método | Descripción |
|------|--------|-------------|
| `/extract` | POST | Extrae datos + auto-categoría + atributos obligatorios |
| `/category-attributes` | POST | Consulta atributos obligatorios de una categoría |
| `/enhance` | POST | Mejora contenido con Claude |
| `/publish` | POST | Publica en Miraarlo (usa `dynamic_attrs`) |
| `/predict-category` | POST | Predice categoría por título |
| `/export-excel` | POST | Genera Excel del listing |
| `/fill-template` | POST | Rellena plantilla oficial de ML |
| `/download-photos` | POST | Descarga fotos como ZIP |

---

## Notas

- La extracción funciona **sin token** para publicaciones públicas de ML
- Para publicar necesitas tokens válidos de la cuenta Miraarlo
- Los atributos obligatorios se cargan automáticamente al extraer
- Si cambias la categoría manualmente, usa "Recargar atributos" para actualizar los campos
