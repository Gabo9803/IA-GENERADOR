# config.py
VALID_DOC_TYPES = {'texto', 'markdown', 'pdf', 'docx', 'html'}
VALID_TEMPLATES = {''} | {'carta_formal', 'contrato', 'informe', 'factura'}
VALID_LEVELS = {'basico', 'medio', 'profesional'}
VALID_LANGUAGES = {'es', 'en', 'fr', 'de', 'it'}
MAX_PROMPT_LENGTH = 1500
MAX_FIELD_LENGTH = 500

TEMPLATES = {
    "carta_formal": """
Estimado/a {destinatario},

{contenido}

Atentamente,
{remitente}
    """,
    "contrato": """
CONTRATO DE {tipo}

Entre {parte_a}, y {parte_b}, se acuerda lo siguiente:

{contenido}

Firmado en {lugar}, el {fecha}.

[Firma {parte_a}]                [Firma {parte_b}]
    """,
    "informe": """
INFORME: {titulo}

{contenido}
    """,
    "factura": """
FACTURA #{numero}

Emitida a: {cliente}
Fecha: {fecha}

{contenido}

Total: {total}
    """
}

LEVEL_INSTRUCTIONS = {
    'basico': "Genera un documento simple, breve (máximo 500 palabras), con estructura mínima (introducción, cuerpo, conclusión) y formato básico.",
    'medio': "Genera un documento estructurado, de longitud moderada (hasta 1000 palabras), con secciones claras (antecedentes, análisis, conclusiones) y formato limpio, incluyendo listas y tablas si es relevante.",
    'profesional': "Genera un documento extenso, altamente detallado (hasta 2000 palabras), con estructura avanzada (múltiples secciones, subsecciones, apéndices, referencias), formato profesional, tablas complejas y listas anidadas."
}