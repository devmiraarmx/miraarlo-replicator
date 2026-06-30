import anthropic
import os

client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

ACTIONS = {
    'improve_title': {
        'label': 'Mejorar título',
        'field': 'title',
        'build_prompt': lambda title, desc, cat: f"""Eres un experto en e-commerce de Mercado Libre México.
Mejora este título de producto para que sea más atractivo, claro y persuasivo.
Mantén el nombre del producto y sus características clave. Máximo 60 caracteres.
No uses comillas, no uses mayúsculas innecesarias.

Título actual: {title}
Categoría ID: {cat}

Responde ÚNICAMENTE con el título mejorado. Sin explicaciones, sin comillas."""
    },
    'rewrite_description': {
        'label': 'Reescribir descripción',
        'field': 'description',
        'build_prompt': lambda title, desc, cat: f"""Eres un experto en e-commerce de Mercado Libre México.
Reescribe esta descripción de producto de forma fluida, clara y persuasiva.
Usa párrafos cortos. Destaca los beneficios principales. Evita mayúsculas excesivas y caracteres especiales raros.
No uses markdown, solo texto plano.

Producto: {title}
Descripción actual:
{desc[:3000]}

Responde ÚNICAMENTE con la descripción reescrita. Sin explicaciones ni encabezados."""
    },
    'optimize_seo': {
        'label': 'Optimizar para SEO de ML',
        'field': 'title',
        'build_prompt': lambda title, desc, cat: f"""Eres un experto en SEO de Mercado Libre México.
Optimiza este título para mejorar el posicionamiento en búsquedas de ML.
Incluye las palabras clave más buscadas por compradores reales. Máximo 60 caracteres.
El título debe sonar natural, no como lista de keywords.

Título actual: {title}
Categoría ID: {cat}
Contexto del producto: {desc[:400]}

Responde ÚNICAMENTE con el título optimizado. Sin explicaciones, sin comillas."""
    },
    'adapt_tone': {
        'label': 'Adaptar tono a Miraarlo',
        'field': 'description',
        'build_prompt': lambda title, desc, cat: f"""Eres el copywriter de Miraarlo, una tienda en Mercado Libre México.
El tono de Miraarlo es: profesional, confiable, directo y orientado al cliente.
Transmite confianza. Usa un lenguaje claro y cercano. No exageres.
No uses markdown, solo texto plano.

Producto: {title}
Descripción actual:
{desc[:3000]}

Responde ÚNICAMENTE con la descripción adaptada al tono de Miraarlo. Sin explicaciones."""
    },
    'add_keywords': {
        'label': 'Agregar palabras clave',
        'field': 'description',
        'build_prompt': lambda title, desc, cat: f"""Eres un experto en e-commerce de Mercado Libre México.
Enriquece esta descripción integrando palabras clave relevantes de forma natural.
Las keywords deben fluir dentro del texto, no aparecer como lista aparte.
No uses markdown, solo texto plano.

Producto: {title}
Categoría ID: {cat}
Descripción actual:
{desc[:3000]}

Responde ÚNICAMENTE con la descripción enriquecida con keywords. Sin explicaciones."""
    },
}


class ClaudeHelper:

    def get_actions(self):
        return [{'key': k, 'label': v['label']} for k, v in ACTIONS.items()]

    def enhance(self, action, title, description, category):
        if action not in ACTIONS:
            return {'success': False, 'error': f'Acción "{action}" no reconocida.'}

        action_config = ACTIONS[action]
        prompt = action_config['build_prompt'](title, description, category)

        try:
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                messages=[{'role': 'user', 'content': prompt}]
            )

            result_text = message.content[0].text.strip()

            return {
                'success': True,
                'field': action_config['field'],
                'value': result_text,
                'action': action,
                'label': action_config['label']
            }

        except Exception as e:
            return {'success': False, 'error': f'Error con Claude API: {str(e)}'}
