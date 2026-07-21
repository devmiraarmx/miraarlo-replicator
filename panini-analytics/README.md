# Panini Analytics ⚡

Sistema de análisis de ventas Panini con IA (basado en el patrón NAIA).
Flask + SQLite + Anthropic Claude API.

> **Estado: Fase 1 completa** — base de datos + ingesta de Excel mensual sin duplicados.
> Fases 2–6 (KPIs, chat NL→SQL, auth, pulido, deploy) pendientes.

## Qué hace hoy (Fase 1)

- Sube un Excel mensual de ventas y lo acumula en una base SQLite histórica.
- Deduplica por `id_venta` (PRIMARY KEY) usando `INSERT OR IGNORE`: subir el
  mismo archivo dos veces **no** duplica registros.
- Registra cada carga en `cargas_log` (filas recibidas / insertadas / duplicadas)
  para auditoría.
- UI mínima de carga con resumen inmediato e historial de cargas.

## Estructura

```
panini-analytics/
├── app.py            # Flask: GET / y POST /upload
├── db.py             # Conexión SQLite, esquema, cargar_excel()
├── test_ingesta.py   # Verificación de dedup (carga el mismo Excel 2 veces)
├── requirements.txt
├── env.example
├── templates/
│   └── upload.html
├── data/             # ventas.db (persistente, no versionado)
└── uploads_temp/     # Excel temporal durante el procesamiento
```

## Correr localmente

```bash
cd panini-analytics
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp env.example .env          # y completa SECRET_KEY
python app.py                # http://localhost:5000
```

## Verificar la ingesta (dedup)

```bash
python test_ingesta.py
```

Debe terminar con `✅ Fase 1 OK` tras confirmar que la segunda carga del
mismo archivo inserta 0 filas.

## Columnas esperadas en el Excel

`ID_Venta`, `Fecha`, `Clave`, `Titulo`, `Proveedor`, `Tipo`, `Cantidad`,
`Precio_Unitario`, `Costo_Unitario`, `Importe_Venta`, `Importe_Costo`, `Utilidad`.

Si falta alguna, `/upload` responde 400 con la lista de columnas faltantes.

## Próximas fases

2. KPIs + dashboard (venta total, utilidad, margen %, top proveedor/tipo, deltas MoM).
3. Chat NL→SQL con Claude (`claude_agent.py`, prompt de sistema, ejecución SQL segura).
4. Autenticación (`APP_USER` / `APP_PASS`).
5. Pulido de interfaz.
6. Deployment (volumen persistente para SQLite).
