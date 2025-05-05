from flask import Flask, request, jsonify, render_template, send_file, session, g
from dotenv import load_dotenv
import os
import logging
import sqlite3
import markdown
from cachetools import TTLCache
from config import VALID_DOC_TYPES, VALID_TEMPLATES, VALID_LEVELS, VALID_LANGUAGES, MAX_PROMPT_LENGTH, MAX_FIELD_LENGTH, TEMPLATES
from utils import generate_file_name, sanitize_fields
from history_manager import init_db, save_history, get_history, clear_history, save_template, get_templates
from document_generator import DocumentGenerator

app = Flask(__name__)
load_dotenv()
app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    logging.error("Clave secreta de Flask no encontrada")
    raise ValueError("Clave secreta de Flask no configurada")

logging.basicConfig(level=logging.INFO, filename='app.log', format='%(asctime)s - %(levelname)s - %(message)s')

generator = DocumentGenerator(api_key=os.getenv("OPENAI_API_KEY"))
file_storage = TTLCache(maxsize=100, ttl=3600)

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect('history.db')
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.commit()
        db.close()

init_db()

def validate_input(data: dict) -> tuple:
    prompt = data.get('prompt', '').strip()
    doc_type = data.get('doc_type', 'texto').lower()
    template = data.get('template', '').lower()
    fields = sanitize_fields(data.get('fields', {}))
    level = data.get('level', 'basico').lower()
    language = data.get('language', 'es').lower()
    custom_file_name = data.get('file_name', '').strip()
    logo_path = data.get('logo_path', None)

    if not prompt:
        raise ValueError('El prompt está vacío.')
    if len(prompt) > MAX_PROMPT_LENGTH:
        raise ValueError(f'El prompt excede el límite de {MAX_PROMPT_LENGTH} caracteres.')
    if doc_type not in VALID_DOC_TYPES:
        raise ValueError(f'Tipo de documento inválido: {", ".join(VALID_DOC_TYPES)}')
    if template and template not in VALID_TEMPLATES:
        raise ValueError(f'Plantilla inválida: {", ".join(VALID_TEMPLATES)}')
    if level not in VALID_LEVELS:
        raise ValueError(f'Nivel inválido: {", ".join(VALID_LEVELS)}')
    if language not in VALID_LANGUAGES:
        raise ValueError(f'Idioma inválido: {", ".join(VALID_LANGUAGES)}')
    for key, value in fields.items():
        if len(str(value)) > MAX_FIELD_LENGTH:
            raise ValueError(f'El campo {key} excede el límite de {MAX_FIELD_LENGTH} caracteres.')
    return prompt, doc_type, template, fields, level, language, custom_file_name, logo_path

@app.route('/')
def index():
    if 'session_id' not in session:
        session['session_id'] = os.urandom(16).hex()
    return render_template('index.html')

@app.route('/get_history', methods=['GET'])
def get_history_route():
    session_id = session.get('session_id', os.urandom(16).hex())
    db = get_db()
    history = get_history(db, session_id)
    return jsonify({'history': history})

@app.route('/clear_history', methods=['POST'])
def clear_history_route():
    session_id = session.get('session_id', os.urandom(16).hex())
    db = get_db()
    clear_history(db, session_id)
    generator.reset_context(session_id)
    logging.info("Historial y contexto de conversación limpiados")
    return jsonify({'status': 'success'})

@app.route('/reset_context', methods=['POST'])
def reset_context_route():
    session_id = session.get('session_id', os.urandom(16).hex())
    generator.reset_context(session_id)
    logging.info(f"Contexto reiniciado para session_id: {session_id}")
    return jsonify({'status': 'success'})

@app.route('/get_prompt_suggestions', methods=['POST'])
def get_prompt_suggestions_route():
    try:
        data = request.json
        doc_type = data.get('doc_type', 'texto').lower()
        template = data.get('template', '').lower()
        suggestions = generator.get_prompt_suggestions(doc_type, template)
        return jsonify({'suggestions': suggestions})
    except Exception as e:
        logging.error(f"Error al obtener sugerencias de prompts: {str(e)}")
        return jsonify({'error': f'Error al obtener sugerencias: {str(e)}'}), 500

@app.route('/suggest_fields', methods=['POST'])
def suggest_fields_route():
    try:
        data = request.json
        template_content = data.get('template_content', '')
        fields = generator.suggest_fields(template_content)
        return jsonify({'fields': fields})
    except Exception as e:
        logging.error(f"Error al sugerir campos dinámicos: {str(e)}")
        return jsonify({'error': f'Error al sugerir campos: {str(e)}'}), 500

@app.route('/save_template', methods=['POST'])
def save_template_route():
    try:
        data = request.json
        name = data.get('name', '').strip()
        content = data.get('content', '').strip()
        if not name or not content:
            return jsonify({'error': 'Nombre o contenido de la plantilla vacío.'}), 400
        db = get_db()
        save_template(db, name, content)
        return jsonify({'status': 'success'})
    except Exception as e:
        logging.error(f"Error al guardar plantilla: {str(e)}")
        return jsonify({'error': f'Error al guardar plantilla: {str(e)}'}), 500

@app.route('/get_templates', methods=['GET'])
def get_templates_route():
    try:
        db = get_db()
        templates = get_templates(db)
        return jsonify({'templates': templates})
    except Exception as e:
        logging.error(f"Error al obtener plantillas: {str(e)}")
        return jsonify({'error': f'Error al obtener plantillas: {str(e)}'}), 500

@app.route('/preview', methods=['POST'])
def preview_document():
    try:
        data = request.json
        text = data.get('text', '').strip()
        doc_type = data.get('doc_type', 'texto').lower()
        if not text:
            return jsonify({'error': 'El texto está vacío.'}), 400
        if doc_type not in VALID_DOC_TYPES:
            return jsonify({'error': f'Tipo de documento inválido: {", ".join(VALID_DOC_TYPES)}'}), 400

        response, file_id, buffer, mime_type, file_name, preview_content = generator.render(
            text, doc_type, "es", "preview"
        )

        if file_id:
            file_storage[file_id] = {
                'buffer': buffer,
                'file_name': file_name,
                'mime_type': mime_type
            }

        preview_text = preview_content if preview_content else response
        if doc_type == 'docx' and preview_text:
            preview_text = preview_text.replace('\n\n', '\n').strip()

        return jsonify({
            'preview': preview_text,
            'file_id': file_id
        })

    except Exception as e:
        logging.error(f"Error al generar vista previa: {str(e)}")
        return jsonify({'error': f'Error al generar vista previa: {str(e)}'}), 500

@app.route('/download/<file_id>', methods=['GET'])
def download_file(file_id):
    try:
        if file_id not in file_storage:
            return jsonify({'error': 'Archivo no encontrado.'}), 404
        file_info = file_storage[file_id]
        buffer = file_info['buffer']
        buffer.seek(0)
        return send_file(
            buffer,
            as_attachment=True,
            download_name=file_info['file_name'],
            mimetype=file_info['mime_type']
        )
    except Exception as e:
        logging.error(f"Error al descargar archivo con file_id {file_id}: {str(e)}")
        return jsonify({'error': f'Error al descargar archivo: {str(e)}'}), 500

@app.route('/upload_logo', methods=['POST'])
def upload_logo():
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No se proporcionó archivo'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Nombre de archivo vacío'}), 400
        upload_dir = 'uploads'
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, file.filename)
        file.save(file_path)
        return jsonify({'path': file_path})
    except Exception as e:
        logging.error(f"Error al subir logotipo: {str(e)}")
        return jsonify({'error': f'Error al subir logotipo: {str(e)}'}), 500

@app.route('/generate', methods=['POST'])
def generate_document():
    try:
        data = request.json
        if not data:
            raise ValueError("No se proporcionaron datos en la solicitud.")
        
        prompt, doc_type, template, fields, level, language, custom_file_name, logo_path = validate_input(data)
        session_id = session.get('session_id', os.urandom(16).hex())
        db = get_db()

        if template in TEMPLATES:
            required_fields = re.findall(r'\{(\w+)\}', TEMPLATES[template])
            missing_fields = [f for f in required_fields if f not in fields or not fields[f]]
            if missing_fields:
                return jsonify({'error': f'Faltan campos: {", ".join(missing_fields)}'}), 400

        history = get_history(db, session_id)
        generated_text, is_conversational = generator.generate(prompt, doc_type, template, fields, level, language, history, session_id)

        if not generated_text:
            raise ValueError("El texto generado está vacío.")

        if template in TEMPLATES and fields and not is_conversational:
            try:
                generated_text = TEMPLATES[template].format(**fields, contenido=generated_text)
            except KeyError as e:
                raise ValueError(f"Error al aplicar la plantilla: campo faltante {str(e)}")

        save_history(db, session_id, 'user', prompt)
        save_history(db, session_id, 'assistant', generated_text)
        save_history(db, session_id, 'system', f"Documento generado: tipo={doc_type}, nivel={level}, idioma={language}")

        response_data = {
            'response': generated_text,
            'doc_type': doc_type,
            'is_document': not is_conversational
        }

        if is_conversational:
            preview_text = generated_text
            response_data['preview_content'] = preview_text
        else:
            file_name = custom_file_name if custom_file_name else generate_file_name(prompt, template, doc_type, level)
            response, file_id, buffer, mime_type, full_file_name, preview_content = generator.render(
                generated_text, doc_type, language, file_name, logo_path
            )

            if not response:
                raise ValueError("La respuesta renderizada está vacía.")

            preview_text = preview_content if preview_content else response
            if doc_type == 'docx' and preview_text:
                preview_text = preview_text.replace('\n\n', '\n').strip()

            response_data.update({
                'file_name': full_file_name,
                'file_id': file_id,
                'preview_content': preview_text
            })

            if file_id:
                file_storage[file_id] = {
                    'buffer': buffer,
                    'file_name': full_file_name,
                    'mime_type': mime_type
                }

        return jsonify(response_data)

    except ValueError as e:
        logging.error(f"Error de validación en /generate: {str(e)}")
        return jsonify({'error': f'Error de validación: {str(e)}'}), 400
    except Exception as e:
        logging.error(f"Error inesperado en /generate: {str(e)}")
        return jsonify({'error': f'Error al generar el documento: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)