import requests
import os
import re
import json
from urllib.parse import unquote
from bs4 import BeautifulSoup
from dotenv import load_dotenv, set_key
from curl_cffi import requests as cffi_requests

load_dotenv()
ENV_PATH = '.env'

# Headers que simulan un navegador real — evita bloqueos de ML
BROWSER_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'es-MX,es;q=0.8,en-US;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
}

API_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
    'Accept': 'application/json',
}


class MeliClient:
    BASE_URL = "https://api.mercadolibre.com"
    AUTH_URL = "https://auth.mercadolibre.com.mx/authorization"
    TOKEN_URL = "https://api.mercadolibre.com/oauth/token"

    def __init__(self):
        self.client_id = os.getenv('ML_CLIENT_ID', '1928213031259439')
        self.client_secret = os.getenv('ML_CLIENT_SECRET', '')
        self.redirect_uri = os.getenv('ML_REDIRECT_URI', 'https://miraar.mx/')
        self.access_token = os.getenv('ML_ACCESS_TOKEN', '')
        self.refresh_token_val = os.getenv('ML_REFRESH_TOKEN', '')

    def has_token(self):
        return bool(self.access_token)

    def get_auth_url(self, redirect_uri=None):
        return (f"{self.AUTH_URL}?response_type=code"
                f"&client_id={self.client_id}&redirect_uri={redirect_uri or self.redirect_uri}")

    def _api_headers(self):
        h = dict(API_HEADERS)
        if self.access_token:
            h['Authorization'] = f'Bearer {self.access_token}'
        return h

    def _reload_token(self):
        load_dotenv(override=True)
        self.access_token = os.getenv('ML_ACCESS_TOKEN', '')
        self.refresh_token_val = os.getenv('ML_REFRESH_TOKEN', '')

    def _ml_get(self, url, headers=None, params=None, timeout=10):
        """GET request usando curl_cffi (imita TLS de Chrome real) para evitar bloqueos de ML."""
        h = headers or dict(API_HEADERS)
        return cffi_requests.get(url, headers=h, params=params,
                                 timeout=timeout, impersonate="chrome136")

    # ─────────────────────────────────────────────────────────────
    # PARSEO DE INPUT
    # ─────────────────────────────────────────────────────────────
    def parse_input(self, input_value):
        v = unquote(input_value.strip())  # decode %3A → : etc.

        if re.match(r'^MLM\d+$', v, re.IGNORECASE):
            return {'item_id': v.upper(), 'catalog_id': None, 'url': None}

        if re.match(r'^MLMU\d+$', v, re.IGNORECASE):
            return {'item_id': None, 'catalog_id': v.upper(), 'url': v}

        m = re.search(r'item_id[:=](MLM\d+)', v, re.IGNORECASE)
        if m:
            cat = re.search(r'/up/(MLMU\d+)', v, re.IGNORECASE)
            return {
                'item_id': m.group(1).upper(),
                'catalog_id': cat.group(1) if cat else None,
                'url': v
            }

        m = re.search(r'/up/(MLMU\d+)', v, re.IGNORECASE)
        if m:
            return {'item_id': None, 'catalog_id': m.group(1).upper(), 'url': v}

        # URL catálogo con /p/MLM... (product page)
        m = re.search(r'/p/(MLM\d+)', v, re.IGNORECASE)
        if m:
            return {'item_id': None, 'catalog_id': m.group(1).upper(), 'url': v}

        m = re.search(r'MLM-?(\d+)', v, re.IGNORECASE)
        if m:
            mlm = f"MLM{m.group(1)}"
            return {'item_id': mlm, 'catalog_id': None, 'url': v}

        return None

    def _build_item_url(self, item_id):
        return f"https://articulo.mercadolibre.com.mx/{item_id.replace('MLM', 'MLM-')}"

    # ─────────────────────────────────────────────────────────────
    # SCRAPING (método principal — no requiere API key)
    # ─────────────────────────────────────────────────────────────
    def _extract_category_from_html(self, html):
        """Extrae category_id del HTML de la página de ML."""
        # Buscar en el JS embebido (PRELOADED_STATE, scripts, etc.)
        patterns = [
            r'"category_id"\s*:\s*"(MLM\d+)"',
            r"'category_id'\s*:\s*'(MLM\d+)'",
            r'category_id[=/](MLM\d+)',
        ]
        for pattern in patterns:
            m = re.search(pattern, html)
            if m:
                cat_id = m.group(1)
                print(f"[SCRAPE] category_id extraído del HTML: {cat_id}")
                return cat_id

        # Buscar en breadcrumb links (el último link suele tener la categoría en la URL)
        from bs4 import BeautifulSoup as BS
        soup = BS(html, 'html.parser')
        breadcrumb_links = soup.select('ol.andes-breadcrumb a, nav.andes-breadcrumb a')
        if breadcrumb_links:
            # La URL del último breadcrumb a veces contiene el category slug
            last_href = breadcrumb_links[-1].get('href', '')
            m = re.search(r'MLM\d+', last_href)
            if m:
                print(f"[SCRAPE] category_id extraído del breadcrumb: {m.group(0)}")
                return m.group(0)

        return None

    def _scrape_item(self, url):
        try:
            # curl_cffi imita la huella TLS de Chrome real
            session = cffi_requests.Session(impersonate="chrome136")
            session.get('https://www.mercadolibre.com.mx', headers=BROWSER_HEADERS, timeout=8)
            r = session.get(url, headers=BROWSER_HEADERS, timeout=15, allow_redirects=True)
        except Exception as e:
            return None, f'Error de conexión: {str(e)}'

        if r.status_code != 200:
            return None, f'Error HTTP {r.status_code} al cargar la página'

        soup = BeautifulSoup(r.text, 'html.parser')

        # Extraer category_id del HTML (disponible en cualquier método de scraping)
        scraped_category = self._extract_category_from_html(r.text)

        data = self._extract_jsonld(soup)
        if data:
            if not data.get('price'):
                data['price'] = self._extract_price_css(soup)
            if scraped_category:
                data['category_id'] = scraped_category
            return data, None

        data = self._extract_meta(soup, url)
        if data:
            if not data.get('price'):
                data['price'] = self._extract_price_css(soup)
            if scraped_category:
                data['category_id'] = scraped_category
            return data, None

        data = self._extract_preloaded_state(r.text)
        if data:
            if scraped_category:
                data['category_id'] = scraped_category
            return data, None

        data = self._extract_css(soup, url)
        if data:
            if scraped_category:
                data['category_id'] = scraped_category
            return data, None

        return None, 'No se pudo extraer la información de la página.'

    def _extract_price_css(self, soup):
        """Extrae el precio de la página usando selectores CSS (fallback)."""
        for sel in ['.andes-money-amount__fraction', '.price-tag-fraction',
                    '[itemprop="price"]', 'span.andes-money-amount']:
            el = soup.select_one(sel)
            if el:
                val = el.get('content') or el.get_text(strip=True).replace(',', '').replace('$', '')
                try:
                    return float(re.sub(r'[^\d.]', '', val))
                except ValueError:
                    continue
        return 0.0

    def _extract_jsonld(self, soup):
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string or '')
                if isinstance(data, dict) and data.get('@type') in ('Product', 'ItemPage'):
                    offers = data.get('offers', {})
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    images = data.get('image', [])
                    if isinstance(images, str):
                        images = [images]
                    return {
                        '_source': 'jsonld',
                        'title': data.get('name', ''),
                        'price': float(offers.get('price', 0) or 0),
                        'currency': offers.get('priceCurrency', 'MXN'),
                        'description': data.get('description', ''),
                        'photos': images,
                        'condition': 'new' if 'NewCondition' in str(offers.get('itemCondition', '')) else 'used',
                        'sku': data.get('sku', ''),
                        'brand': data.get('brand', {}).get('name', '') if isinstance(data.get('brand'), dict) else '',
                    }
            except Exception:
                continue
        return None

    def _extract_preloaded_state(self, html):
        patterns = [
            r'window\.__PRELOADED_STATE__\s*=\s*({.+?});\s*(?:window|</script>)',
            r'"initialState"\s*:\s*({.+?})\s*};\s*</script>',
            r'__listing_initial_state__\s*=\s*({.+?});\s*</script>',
        ]
        for pattern in patterns:
            m = re.search(pattern, html, re.DOTALL)
            if m:
                try:
                    state = json.loads(m.group(1))
                    item = (state.get('initialState', {})
                            .get('components', {})
                            .get('header', {}))
                    if item.get('title'):
                        return {'_source': 'preloaded', **item}
                except Exception:
                    continue
        return None

    def _extract_meta(self, soup, url):
        def meta(prop=None, name=None):
            if prop:
                el = soup.find('meta', property=prop) or soup.find('meta', attrs={'property': prop})
            else:
                el = soup.find('meta', attrs={'name': name})
            return (el.get('content', '') if el else '').strip()

        title = (soup.find('title') or soup.new_tag('x')).get_text(strip=True)
        title = meta(prop='og:title') or meta(name='twitter:title') or title

        price_raw = meta(prop='product:price:amount') or meta(prop='og:price:amount') or '0'
        try:
            price = float(re.sub(r'[^\d.]', '', price_raw))
        except ValueError:
            price = 0.0

        currency = meta(prop='product:price:currency') or meta(prop='og:price:currency') or 'MXN'
        description = meta(prop='og:description') or meta(name='description') or ''

        photos = []
        for og_img in soup.find_all('meta', property='og:image'):
            src = og_img.get('content', '')
            if src and src not in photos:
                src = re.sub(r'-[A-Z]\.jpg', '-O.jpg', src)
                photos.append(src)

        condition_raw = meta(prop='product:condition') or ''
        condition = 'used' if 'used' in condition_raw.lower() else 'new'
        sku = meta(prop='product:retailer_item_id') or ''

        if not title:
            return None

        return {
            '_source': 'meta',
            'title': title,
            'price': price,
            'currency': currency,
            'description': description,
            'photos': photos,
            'condition': condition,
            'sku': sku,
            'brand': meta(prop='product:brand') or '',
        }

    def _extract_css(self, soup, url):
        try:
            title = ''
            for sel in ['h1.ui-pdp-title', 'h1.item-title__primary', 'h1']:
                el = soup.select_one(sel)
                if el:
                    title = el.get_text(strip=True)
                    break

            price = 0.0
            for sel in ['.andes-money-amount__fraction', '.price-tag-fraction', '[itemprop="price"]']:
                el = soup.select_one(sel)
                if el:
                    val = el.get('content') or el.get_text(strip=True).replace(',', '')
                    try:
                        price = float(re.sub(r'[^\d.]', '', val))
                        break
                    except ValueError:
                        continue

            photos = []
            for img in soup.select('figure.ui-pdp-gallery__figure img, .ui-pdp-image img'):
                src = img.get('data-zoom') or img.get('src') or ''
                if src and 'http' in src and src not in photos:
                    src = re.sub(r'-[A-Z]\.jpg', '-O.jpg', src)
                    photos.append(src)

            description = ''
            for sel in ['.ui-pdp-description__content', '.item-description__text p']:
                el = soup.select_one(sel)
                if el:
                    description = el.get_text(separator='\n', strip=True)
                    break

            if not title and not photos:
                return None

            return {
                '_source': 'css',
                'title': title,
                'price': price,
                'currency': 'MXN',
                'description': description,
                'photos': photos,
                'condition': 'new',
                'sku': '',
                'brand': '',
            }
        except Exception:
            return None

    # ─────────────────────────────────────────────────────────────
    # CATEGORY ATTRIBUTES — NUEVO
    # ─────────────────────────────────────────────────────────────
    def get_category_attributes(self, category_id):
        """
        Consulta los atributos de una categoría en ML.
        Devuelve solo los obligatorios (required) con sus valores permitidos.
        """
        if not category_id:
            return []

        try:
            r = self._ml_get(
                f"{self.BASE_URL}/categories/{category_id}/attributes"
            )
            if r.status_code != 200:
                print(f"[CAT ATTRS] Error {r.status_code} para {category_id}")
                return []

            all_attrs = r.json()
            result = []

            for attr in all_attrs:
                if not isinstance(attr, dict):
                    continue

                tags = attr.get('tags', {}) or {}
                is_required = tags.get('required', False)
                is_catalog_required = tags.get('catalog_required', False)
                is_conditional_required = tags.get('conditional_required', False)

                # Atributos tipo grid_id son estructuralmente requeridos en ropa
                # aunque ML no los marque con tag required
                is_grid = attr.get('value_type') in ('grid_id',)

                # Solo incluir obligatorios (required, catalog_required, conditional_required, o grid)
                if not is_required and not is_catalog_required and not is_conditional_required and not is_grid:
                    continue

                # Excluir ITEM_CONDITION — se maneja por separado en el UI
                if attr.get('id') == 'ITEM_CONDITION':
                    continue

                attr_info = {
                    'id': attr.get('id', ''),
                    'name': attr.get('name', ''),
                    'type': attr.get('value_type', 'string'),
                    'required': is_required,
                    'catalog_required': is_catalog_required,
                    'conditional_required': is_conditional_required,
                    'is_grid': is_grid,
                    'tooltip': attr.get('tooltip', ''),
                    'hint': attr.get('hint', ''),
                }

                # Valores permitidos (dropdown)
                values = attr.get('values', [])
                if values and isinstance(values, list):
                    attr_info['allowed_values'] = [
                        {'id': v.get('id', ''), 'name': v.get('name', '')}
                        for v in values
                        if isinstance(v, dict) and v.get('name')
                    ]
                else:
                    attr_info['allowed_values'] = []

                # Unidad de medida
                if attr.get('default_unit'):
                    attr_info['unit'] = attr['default_unit']

                result.append(attr_info)

            print(f"[CAT ATTRS] {category_id}: {len(result)} atributos obligatorios de {len(all_attrs)} totales")
            return result

        except Exception as e:
            print(f"[CAT ATTRS] Excepción: {str(e)}")
            return []

    def predict_category(self, title):
        """Usa el predictor de ML para sugerir categoría por título."""
        try:
            r = self._ml_get(
                f"{self.BASE_URL}/sites/MLM/domain_discovery/search",
                params={'q': title, 'limit': 1}
            )
            if r.status_code == 200:
                results = r.json()
                if results:
                    return results[0].get('category_id', '')
        except Exception:
            pass
        return None

    # ─────────────────────────────────────────────────────────────
    # EXTRACT PRINCIPAL
    # ─────────────────────────────────────────────────────────────
    def extract_item(self, input_value):
        parsed = self.parse_input(input_value)
        if not parsed:
            return {
                'success': False,
                'error': 'Formato no válido. Pega la URL completa de ML o un ID tipo MLM123456789.'
            }

        self._reload_token()

        item_id = parsed.get('item_id')
        catalog_id = parsed.get('catalog_id')
        raw_url = parsed.get('url') or ''

        # Si es URL de catálogo /p/MLM... intentar extraer item_id del query string
        if not item_id and raw_url:
            m = re.search(r'item_id[=:](MLM\d+)', raw_url, re.IGNORECASE)
            if m:
                item_id = m.group(1).upper()

        if raw_url and raw_url.startswith('http'):
            scrape_url = raw_url
        elif item_id:
            scrape_url = self._build_item_url(item_id)
        elif catalog_id:
            scrape_url = f"https://www.mercadolibre.com.mx/p/{catalog_id}"
        else:
            return {'success': False, 'error': 'No se pudo determinar la URL del producto.'}

        # ── ESTRATEGIA: API primero (si hay token), scraping como fallback ──
        result = None

        # 1. Intentar API directamente con curl_cffi (huella TLS real)
        if item_id:
            try:
                print(f"[EXTRACT] Intentando API para {item_id}...")
                api_h = dict(API_HEADERS)
                if self.access_token:
                    api_h['Authorization'] = f'Bearer {self.access_token}'
                r = self._ml_get(f"{self.BASE_URL}/items/{item_id}", headers=api_h)
                
                # --- LÓGICA DE AUTO-REFRESH ---
                if r.status_code in [401, 403]:
                    print("[EXTRACT] Token expirado o denegado (403/401). Intentando refresh_token...")
                    refresh_result = self.refresh_token()
                    
                    if refresh_result.get('success'):
                        print("[EXTRACT] Token refrescado exitosamente. Reintentando request...")
                        api_h['Authorization'] = f'Bearer {self.access_token}'
                        r = self._ml_get(f"{self.BASE_URL}/items/{item_id}", headers=api_h)
                    else:
                        print(f"[EXTRACT] Error al refrescar el token: {refresh_result.get('error')}")
                # ------------------------------

                print(f"[EXTRACT] API status: {r.status_code}")
                if r.status_code == 200:
                    result = self._parse_item(r.json(), item_id)
                    print(f"[EXTRACT] API exitosa → título: {result.get('title', '')[:50]}")
                else:
                    print(f"[EXTRACT] API rechazó: {r.text[:200]}")
            except Exception as e:
                print(f"[EXTRACT] API falló: {e}")

        # 2. Si la API directa no funcionó, intentar vía Search API (pública)
        if (not result or not result.get('success')) and item_id:
            try:
                print(f"[EXTRACT] Intentando Search API para {item_id}...")
                sr = self._ml_get(
                    f"{self.BASE_URL}/sites/MLM/search",
                    params={'q': item_id, 'limit': 1}
                )
                print(f"[EXTRACT] Search API status: {sr.status_code}")
                if sr.status_code == 200:
                    search_data = sr.json()
                    items_found = search_data.get('results', [])
                    if items_found:
                        found = items_found[0]
                        if found.get('id', '').upper() == item_id.upper():
                            photos = [
                                re.sub(r'-[A-Z]\.jpg$', '-O.jpg', p.get('secure_url', ''))
                                for p in found.get('pictures', [])
                                if isinstance(p, dict) and p.get('secure_url')
                            ]
                            if not photos and found.get('thumbnail'):
                                photos = [found['thumbnail'].replace('-I.jpg', '-O.jpg')]

                            attributes = {}
                            for a in found.get('attributes', []):
                                if a.get('id') and a.get('value_name'):
                                    attributes[a['id']] = {
                                        'id': a['id'],
                                        'name': a.get('name', ''),
                                        'value_name': a['value_name']
                                    }

                            description = ''
                            try:
                                dr = self._ml_get(
                                    f"{self.BASE_URL}/items/{item_id}/description"
                                )
                                if dr.status_code == 200:
                                    description = dr.json().get('plain_text', '')
                            except Exception:
                                pass

                            result = {
                                'success': True, 'type': 'item', 'source': 'search_api',
                                'mlm_id': item_id,
                                'title': found.get('title', ''),
                                'price': found.get('price', 0),
                                'currency': found.get('currency_id', 'MXN'),
                                'category_id': found.get('category_id', ''),
                                'condition': found.get('condition', 'new'),
                                'description': description,
                                'photos': photos,
                                'attributes': attributes,
                                'listing_type': found.get('listing_type_id', 'gold_special'),
                                'available_quantity': found.get('available_quantity', 1),
                                'permalink': found.get('permalink', ''),
                            }
                            print(f"[EXTRACT] Search API exitosa → {result['title'][:50]}")
                        else:
                            print(f"[EXTRACT] Search devolvió item diferente: {found.get('id')}")
                    else:
                        print(f"[EXTRACT] Search no devolvió resultados")
            except Exception as e:
                print(f"[EXTRACT] Search API falló: {e}")

        # 3. Si la API no funcionó, intentar scraping
        if not result or not result.get('success'):
            print(f"[EXTRACT] Intentando scraping de {scrape_url}...")
            scraped, scrape_error = self._scrape_item(scrape_url)

            if scraped:
                scraped_title = scraped.get('title', '').lower().strip()
                # Validar que el scraping trajo datos reales
                if scraped_title and scraped_title != 'mercado libre':
                    result = self._merge_data(scraped, None, item_id or catalog_id, scrape_url)
                    print(f"[EXTRACT] Scraping exitoso → título: {result.get('title', '')[:50]}")
                else:
                    print(f"[EXTRACT] Scraping trajo título basura: '{scraped_title}'")

        if not result or not result.get('success'):
            return {
                'success': False,
                'error': 'No se pudo obtener la información. Verifica que la URL sea válida y el listing esté activo.'
            }

        # ── AUTO-DETECCIÓN DE CATEGORÍA ──
        if not result.get('category_id'):
            # Fallback 1: intentar API pública de Items solo para category_id
            mlm = result.get('mlm_id', '').strip().upper()
            print(f"[AUTO-CAT] Sin categoría. mlm_id={mlm}. Intentando API pública...")
            if mlm and 'MLM' in mlm:
                try:
                    r = requests.get(
                        f"{self.BASE_URL}/items/{mlm}",
                        headers={'Accept': 'application/json'},
                        timeout=8
                    )
                    print(f"[AUTO-CAT] API pública status: {r.status_code}")
                    if r.status_code == 200:
                        pub_cat = r.json().get('category_id', '')
                        if pub_cat:
                            result['category_id'] = pub_cat
                            result['category_source'] = 'public_api'
                            print(f"[AUTO-CAT] Categoría vía API pública: {pub_cat}")
                        else:
                            print(f"[AUTO-CAT] API pública respondió pero sin category_id")
                    else:
                        print(f"[AUTO-CAT] API pública error: {r.text[:200]}")
                except Exception as e:
                    print(f"[AUTO-CAT] API pública falló: {e}")

        if not result.get('category_id'):
            # Fallback 2: intentar scraping de la página solo para category_id
            permalink = result.get('permalink', '')
            if permalink:
                print(f"[AUTO-CAT] Intentando extraer categoría del HTML...")
                try:
                    session = cffi_requests.Session(impersonate="chrome136")
                    r = session.get(permalink, headers=BROWSER_HEADERS, timeout=10, allow_redirects=True)
                    if r.status_code == 200:
                        cat_from_html = self._extract_category_from_html(r.text)
                        if cat_from_html:
                            result['category_id'] = cat_from_html
                            result['category_source'] = 'html_scrape'
                except Exception as e:
                    print(f"[AUTO-CAT] Scraping de categoría falló: {e}")

        if not result.get('category_id'):
            # Fallback 2: predictor de ML por título (menos confiable)
            title = result.get('title', '')
            if title:
                predicted = self.predict_category(title)
                if predicted:
                    result['category_id'] = predicted
                    result['category_source'] = 'predicted'
                    print(f"[AUTO-CAT] Categoría predicha por título: {predicted}")

        # ── ATRIBUTOS OBLIGATORIOS DE LA CATEGORÍA ──
        cat_id = result.get('category_id', '')
        if cat_id:
            cat_attrs = self.get_category_attributes(cat_id)
            result['category_attributes'] = cat_attrs

            existing_attrs = result.get('attributes', {})
            prefilled = {}
            for ca in cat_attrs:
                attr_id = ca['id']
                if attr_id in existing_attrs:
                    ea = existing_attrs[attr_id]
                    if isinstance(ea, dict):
                        prefilled[attr_id] = ea.get('value_name', '') or ea.get('value_id', '')
                    else:
                        prefilled[attr_id] = str(ea)
            result['prefilled_attributes'] = prefilled

        return result

    def _merge_data(self, scraped, api_data, mlm_id, permalink):
        photos = scraped.get('photos', [])

        if api_data and api_data.get('pictures'):
            api_photos = [
                re.sub(r'-[A-Z]\.jpg$', '-O.jpg', p.get('url', ''))
                for p in api_data.get('pictures', [])
            ]
            if api_photos:
                photos = api_photos

        attributes = {}
        if api_data:
            for attr in api_data.get('attributes', []):
                attr_id = attr.get('id', '')
                attr_name = attr.get('name', '')
                attr_value = attr.get('value_name', '')
                if attr_id and attr_value:
                    attributes[attr_id] = {
                        'id': attr_id,
                        'name': attr_name,
                        'value_name': attr_value,
                    }
        elif scraped.get('brand'):
            attributes['BRAND'] = {'id': 'BRAND', 'name': 'Marca', 'value_name': scraped['brand']}

        description = scraped.get('description', '')
        if api_data:
            api_item_id = api_data.get('id')
            if api_item_id:
                try:
                    r = self._ml_get(f"{self.BASE_URL}/items/{api_item_id}/description")
                    if r.status_code == 200:
                        api_desc = r.json().get('plain_text', '')
                        if len(api_desc) > len(description):
                            description = api_desc
                except Exception:
                    pass

        return {
            'success': True,
            'type': 'catalog' if str(mlm_id).startswith('MLMU') else 'item',
            'source': scraped.get('_source', 'scraping'),
            'mlm_id': mlm_id or '',
            'title': scraped.get('title') or (api_data or {}).get('title', ''),
            'price': scraped.get('price') or (api_data or {}).get('price', 0),
            'currency': 'MXN',
            'category_id': (api_data or {}).get('category_id', '') or scraped.get('category_id', ''),
            'condition': scraped.get('condition', 'new'),
            'description': description,
            'photos': photos,
            'attributes': attributes,
            'listing_type': (api_data or {}).get('listing_type_id', 'gold_special'),
            'available_quantity': (api_data or {}).get('available_quantity', 1),
            'permalink': permalink,
        }

    def _parse_item(self, item, mlm_id):
        try:
            desc_r = self._ml_get(f"{self.BASE_URL}/items/{mlm_id}/description")
            description = desc_r.json().get('plain_text', '') if desc_r.status_code == 200 else ''
        except Exception:
            description = ''

        photos = [re.sub(r'-[A-Z]\.jpg$', '-O.jpg', p.get('url', ''))
                  for p in item.get('pictures', []) if p.get('url')]

        attributes = {}
        for a in item.get('attributes', []):
            if a.get('id') and (a.get('value_name') or a.get('value_id')):
                attributes[a['id']] = {
                    'id': a['id'],
                    'name': a.get('name', ''),
                    'value_name': a.get('value_name', ''),
                    'value_id': a.get('value_id', ''),
                }

        return {
            'success': True, 'type': 'item', 'source': 'api',
            'mlm_id': mlm_id,
            'title': item.get('title', ''),
            'price': item.get('price', 0),
            'currency': item.get('currency_id', 'MXN'),
            'category_id': item.get('category_id', ''),
            'condition': item.get('condition', 'new'),
            'description': description,
            'photos': photos,
            'attributes': attributes,
            'listing_type': item.get('listing_type_id', 'gold_special'),
            'available_quantity': item.get('available_quantity', 1),
            'permalink': item.get('permalink', ''),
        }

    # ─────────────────────────────────────────────────────────────
    # TOKEN MANAGEMENT
    # ─────────────────────────────────────────────────────────────
    def refresh_token(self):
        if not self.refresh_token_val:
            return {'success': False, 'error': 'No hay refresh token en el .env'}
        r = requests.post(self.TOKEN_URL, data={
            'grant_type': 'refresh_token',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'refresh_token': self.refresh_token_val
        })
        if r.status_code == 200:
            data = r.json()
            self.access_token = data.get('access_token', '')
            self.refresh_token_val = data.get('refresh_token', '')
            set_key(ENV_PATH, 'ML_ACCESS_TOKEN', self.access_token)
            set_key(ENV_PATH, 'ML_REFRESH_TOKEN', self.refresh_token_val)
            return {'success': True, 'message': 'Token refrescado y guardado'}
        return {'success': False, 'error': f'Error {r.status_code}: {r.text}'}

    def exchange_code(self, code, redirect_uri=None):
        r = requests.post(self.TOKEN_URL, data={
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'redirect_uri': redirect_uri or self.redirect_uri
        })
        if r.status_code == 200:
            data = r.json()
            self.access_token = data.get('access_token', '')
            self.refresh_token_val = data.get('refresh_token', '')
            set_key(ENV_PATH, 'ML_ACCESS_TOKEN', self.access_token)
            set_key(ENV_PATH, 'ML_REFRESH_TOKEN', self.refresh_token_val)
            return {'success': True}
        return {'success': False, 'error': r.text}

    # ─────────────────────────────────────────────────────────────
    # PUBLISH
    # ─────────────────────────────────────────────────────────────
    def get_me(self):
        self._reload_token()
        r = requests.get(f"{self.BASE_URL}/users/me", headers=self._api_headers(), timeout=8)
        if r.status_code == 200:
            return r.json()
        return None

    def _maximize_photo_url(self, url):
        """Convierte URL de foto de ML a la versión de máxima resolución."""
        if not url:
            return url
        # ML usa sufijos como -I.jpg (thumbnail), -D.jpg (detail), -O.jpg (original/max)
        # También puede ser .webp o sin sufijo de tamaño
        url = re.sub(r'-[A-Z]\.(jpg|jpeg|png|webp)', r'-O.\1', url, flags=re.IGNORECASE)
        # Forzar .jpg si es .webp (mejor compatibilidad con upload)
        url = re.sub(r'\.webp', '.jpg', url, flags=re.IGNORECASE)
        return url

    def upload_image(self, image_url):
        if not self.access_token:
            print("[UPLOAD] Error: No hay access_token disponible.")
            return None

        # Intentar obtener la versión de máxima resolución
        image_url = self._maximize_photo_url(image_url)
        print(f"[UPLOAD] Descargando imagen: {image_url}")
        try:
            img_resp = cffi_requests.get(image_url, headers=BROWSER_HEADERS,
                                         timeout=15, impersonate="chrome136")
            if img_resp.status_code != 200:
                print(f"[UPLOAD] Error al descargar imagen externa. Status: {img_resp.status_code}")
                return None

            # ── Validar y ajustar tamaño mínimo (ML exige ≥500px en un lado, ≥250 en el otro) ──
            from PIL import Image
            from io import BytesIO

            img_bytes = img_resp.content
            try:
                img = Image.open(BytesIO(img_bytes))
                w, h = img.size
                MIN_SIZE = 500  # Forzar ambos lados ≥500 para evitar rechazos

                # Convertir a RGB siempre
                if img.mode in ('RGBA', 'P', 'LA'):
                    bg = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    bg.paste(img, mask=img.split()[-1] if 'A' in img.mode else None)
                    img = bg
                elif img.mode != 'RGB':
                    img = img.convert('RGB')

                if w < MIN_SIZE or h < MIN_SIZE:
                    scale = max(MIN_SIZE / w, MIN_SIZE / h)
                    new_w = max(int(w * scale), MIN_SIZE)
                    new_h = max(int(h * scale), MIN_SIZE)
                    img = img.resize((new_w, new_h), Image.LANCZOS)
                    print(f"[UPLOAD] Imagen escalada: {w}x{h} → {new_w}x{new_h}")
                else:
                    print(f"[UPLOAD] Imagen OK: {w}x{h}")

                buf = BytesIO()
                img.save(buf, format='JPEG', quality=92)
                img_bytes = buf.getvalue()
            except Exception as e:
                print(f"[UPLOAD] No se pudo procesar imagen (subiendo original): {e}")

            ext = 'jpg'
            ct = 'image/jpeg'

            headers = {
                'Authorization': f'Bearer {self.access_token}'
            }

            upload = requests.post(
                f"{self.BASE_URL}/pictures/items/upload",
                headers=headers,
                files={'file': (f'photo.{ext}', img_bytes, ct)},
                timeout=30
            )

            if upload.status_code == 201:
                pic_id = upload.json().get('id')
                print(f"[UPLOAD] Imagen subida con éxito. ID asignado: {pic_id}")
                return pic_id
            else:
                print(f"[UPLOAD] Falló la subida a ML. Status: {upload.status_code}, Resp: {upload.text}")
                return None
        except Exception as e:
            print(f"[UPLOAD] Excepción al procesar imagen: {str(e)}")
            return None

    def upload_image_base64(self, data_url):
        """Sube una imagen en formato base64 data URL a ML."""
        if not self.access_token:
            print("[UPLOAD-B64] Error: No hay access_token.")
            return None

        try:
            import base64
            from PIL import Image
            from io import BytesIO

            # Extraer el base64 del data URL
            # Formato: data:image/jpeg;base64,/9j/4AAQSkZJRg...
            if ',' in data_url:
                header, b64_data = data_url.split(',', 1)
            else:
                b64_data = data_url

            img_bytes = base64.b64decode(b64_data)

            # Procesar imagen (mismo flujo que upload_image)
            img = Image.open(BytesIO(img_bytes))
            w, h = img.size
            MIN_SIZE = 500

            if img.mode in ('RGBA', 'P', 'LA'):
                bg = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                bg.paste(img, mask=img.split()[-1] if 'A' in img.mode else None)
                img = bg
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            if w < MIN_SIZE or h < MIN_SIZE:
                scale = max(MIN_SIZE / w, MIN_SIZE / h)
                new_w = max(int(w * scale), MIN_SIZE)
                new_h = max(int(h * scale), MIN_SIZE)
                img = img.resize((new_w, new_h), Image.LANCZOS)
                print(f"[UPLOAD-B64] Imagen escalada: {w}x{h} → {new_w}x{new_h}")
            else:
                print(f"[UPLOAD-B64] Imagen OK: {w}x{h}")

            buf = BytesIO()
            img.save(buf, format='JPEG', quality=92)
            img_bytes = buf.getvalue()

            headers = {'Authorization': f'Bearer {self.access_token}'}
            upload = requests.post(
                f"{self.BASE_URL}/pictures/items/upload",
                headers=headers,
                files={'file': ('photo.jpg', img_bytes, 'image/jpeg')},
                timeout=30
            )

            if upload.status_code == 201:
                pic_id = upload.json().get('id')
                print(f"[UPLOAD-B64] Imagen subida. ID: {pic_id}")
                return pic_id
            else:
                print(f"[UPLOAD-B64] Falló. Status: {upload.status_code}")
                return None
        except Exception as e:
            print(f"[UPLOAD-B64] Excepción: {str(e)}")
            return None

    def publish_item(self, item_data):
        if not self.access_token:
            return {'success': False, 'error': 'No autenticado en Mercado Libre. Revisa tu conexión.'}

        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        try:
            me_req = requests.get(f"{self.BASE_URL}/users/me", headers=headers)
            if me_req.status_code == 200:
                seller_id = me_req.json().get('id')
                tags_cuenta = me_req.json().get('tags', [])
            else:
                return {'success': False, 'error': 'No se pudo validar el perfil de vendedor asociado al token.'}
        except Exception as e:
            return {'success': False, 'error': f'Error de red al consultar el perfil de usuario: {str(e)}'}

        category_id = item_data.get('category_id', '').strip()
        if not category_id:
            return {'success': False, 'error': 'El ID de la categoría está vacío o es inválido.'}

        # Procesamiento de imágenes
        picture_ids = []
        raw_photos = item_data.get('photos', [])
        if isinstance(raw_photos, str):
            try: raw_photos = json.loads(raw_photos)
            except: raw_photos = [raw_photos]

        for p_url in raw_photos:
            if p_url and str(p_url).startswith('http'):
                pid = self.upload_image(p_url)
                if pid:
                    picture_ids.append({'id': pid})
            elif p_url and str(p_url).startswith('data:image'):
                pid = self.upload_image_base64(p_url)
                if pid:
                    picture_ids.append({'id': pid})

        # Limpieza de título
        clean_title = item_data.get('title', '').strip()
        clean_title = re.sub(r'[^\w\s\-\/\%\.\,\:\&\(\)]', '', clean_title)
        clean_title = ' '.join(clean_title.split())[:60]

        # Construcción de atributos — dinámicos desde el frontend
        publish_attrs = []

        # Atributos dinámicos del frontend (dynamic_attrs: {attr_id: value})
        dynamic_attrs = item_data.get('dynamic_attrs') or {}
        for attr_id, attr_value in dynamic_attrs.items():
            val = str(attr_value).strip()
            if val:
                publish_attrs.append({'id': attr_id, 'value_name': val})

        # ITEM_CONDITION
        condition_val = item_data.get('condition', 'new')
        condition_value_id = '2230284' if condition_val == 'new' else '2230289'
        ids_presentes = {a['id'] for a in publish_attrs}
        if 'ITEM_CONDITION' not in ids_presentes:
            publish_attrs.append({
                'id': 'ITEM_CONDITION',
                'value_id': condition_value_id
            })

        # Fallback: si BRAND no vino en dinámicos, usar attr_brand del form viejo
        ids_presentes = {a['id'] for a in publish_attrs}
        if 'BRAND' not in ids_presentes:
            brand_val = item_data.get('attr_brand', '').strip() or 'Genérica'
            publish_attrs.append({'id': 'BRAND', 'value_name': brand_val})

        # Fallback: atributos del item original que no vinieron en dinámicos
        # (incluye GTIN, EAN, UPC, MPN, etc. que son conditional_required)
        ids_presentes = {a['id'] for a in publish_attrs}
        original_attrs = item_data.get('attributes') or {}
        for attr_id, attr_val in original_attrs.items():
            if attr_id not in ids_presentes and attr_id != 'ITEM_CONDITION':
                if isinstance(attr_val, dict):
                    vname = attr_val.get('value_name', '')
                    vid = attr_val.get('value_id', '')
                else:
                    vname = str(attr_val)
                    vid = ''
                if vname.strip():
                    publish_attrs.append({'id': attr_id, 'value_name': vname.strip()})
                    print(f"[PUBLISH] Atributo heredado del original: {attr_id} = {vname.strip()[:30]}")
                elif vid.strip():
                    # Para atributos tipo grid_id que solo tienen value_id
                    publish_attrs.append({'id': attr_id, 'value_id': vid.strip()})
                    print(f"[PUBLISH] Atributo heredado (value_id): {attr_id} = {vid.strip()[:30]}")

        # Dimensiones del paquete
        ids_presentes = {a['id'] for a in publish_attrs}
        pkg_h = item_data.get('pkg_height')
        pkg_w = item_data.get('pkg_width')
        pkg_l = item_data.get('pkg_length')
        pkg_wt = item_data.get('pkg_weight')

        if pkg_h and 'seller_package_height' not in ids_presentes:
            publish_attrs.append({'id': 'seller_package_height', 'value_name': f"{int(float(pkg_h))} cm"})
        if pkg_w and 'seller_package_width' not in ids_presentes:
            publish_attrs.append({'id': 'seller_package_width', 'value_name': f"{int(float(pkg_w))} cm"})
        if pkg_l and 'seller_package_length' not in ids_presentes:
            publish_attrs.append({'id': 'seller_package_length', 'value_name': f"{int(float(pkg_l))} cm"})
        if pkg_wt and 'seller_package_weight' not in ids_presentes:
            gramos = int(float(pkg_wt) * 1000)
            publish_attrs.append({'id': 'seller_package_weight', 'value_name': f"{gramos} g"})

        print(f"[PUBLISH] Atributos ({len(publish_attrs)}): {[a['id'] for a in publish_attrs]}")

        listing_type = item_data.get('listing_type', 'gold_special')
        price = float(item_data.get('price', 0) or 0)

        payload = {
            'category_id': category_id,
            'price': price,
            'currency_id': 'MXN',
            'available_quantity': int(item_data.get('available_quantity', 1) or 1),
            'buying_mode': 'buy_it_now',
            'condition': condition_val,
            'listing_type_id': listing_type,
            'attributes': publish_attrs,
            'pictures': picture_ids if picture_ids else [{'source': self._maximize_photo_url(u)} for u in raw_photos if u and str(u).startswith('http')]
        }

        if 'user_product_seller' in tags_cuenta:
            print("[PUBLISH] Perfil: user_product_seller → usando family_name (modelo UP)")
            payload['family_name'] = clean_title
        else:
            print("[PUBLISH] Perfil: vendedor estándar → usando title")
            payload['title'] = clean_title

        payload['shipping'] = {
            'mode': 'me2',
            'local_pick_up': False,
            'free_shipping': False
        }

        print(f"\n[PUBLISH] Payload Final:\n{json.dumps(payload, indent=2, ensure_ascii=False)}\n")

        r = requests.post(f"{self.BASE_URL}/items", json=payload, headers=headers)
        print(f"[PUBLISH] Status: {r.status_code}")
        if r.status_code != 201:
            print(f"[PUBLISH] Error ML: {r.text}\n")

        if r.status_code == 400 and "shipping" in r.text.lower():
            print("[PUBLISH] Conflicto con shipping → reintentando con not_specified...")
            payload['shipping'] = {
                'mode': 'not_specified',
                'local_pick_up': True,
                'free_shipping': False
            }
            r = requests.post(f"{self.BASE_URL}/items", json=payload, headers=headers)
            print(f"[PUBLISH] Status reintento: {r.status_code}")

        if r.status_code == 400:
            try:
                cat_attrs = requests.get(
                    f"{self.BASE_URL}/categories/{category_id}/attributes",
                    headers=headers, timeout=8
                ).json()
                required = [
                    f"{a.get('id')} ({a.get('name')})"
                    for a in cat_attrs
                    if isinstance(a, dict) and a.get('tags', {}).get('required')
                ]
                print(f"[DIAGNÓSTICO] Atributos requeridos por categoría {category_id}: {required}")
            except Exception:
                pass

        if r.status_code == 201:
            new_item = r.json()
            new_mlm = new_item.get('id', '')

            desc = item_data.get('description', '').strip()
            if desc and new_mlm:
                dr = requests.post(
                    f"{self.BASE_URL}/items/{new_mlm}/description",
                    json={'plain_text': desc}, headers=headers
                )
                print(f"[PUBLISH] Resultado de inyección de descripción: {dr.status_code}")

            return {
                'success': True,
                'new_id': new_mlm,
                'url': new_item.get('permalink', ''),
                'category_used': category_id,
                'seller_id': seller_id
            }

        try:
            err = r.json()
            msg = err.get('message', '') or err.get('error', '') or str(err)
            cause = err.get('cause', [])
            if cause:
                detalles = []
                for c in cause:
                    if isinstance(c, dict):
                        detalles.append(c.get('message', str(c)))
                    else:
                        detalles.append(str(c))
                msg += ' — Detalle: ' + '; '.join(detalles)
            return {'success': False, 'error': f"Error de Mercado Libre ({r.status_code}): {msg}"}
        except:
            return {'success': False, 'error': f"Error inesperado de la API (Status {r.status_code}): {r.text[:300]}"}