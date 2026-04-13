from flask import Flask, render_template, request, jsonify
from workflow_generator import WorkflowGenerator
import subprocess
import json
import os
import base64
import tempfile
import zipfile
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/detect-csv', methods=['POST'])
def detect_csv():
    """Detecta automáticamente el CSV dentro del ZIP"""
    try:
        data = request.json
        url = data.get('url')
        
        if not url:
            return jsonify({'error': 'URL requerida'}), 400
        
        # Descargar ZIP temporalmente
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
            result = subprocess.run(
                ['curl', '-L', '-o', tmp.name, url],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                return jsonify({'error': 'No se pudo descargar el ZIP'}), 400
            
            # Listar archivos
            try:
                with zipfile.ZipFile(tmp.name, 'r') as z:
                    csv_files = [f for f in z.namelist() if f.endswith('.csv')]
                    
                    if not csv_files:
                        return jsonify({'error': 'No se encontró CSV en el ZIP'}), 400
                    
                    # Retornar el primero
                    return jsonify({
                        'csv_file': csv_files[0],
                        'available_files': csv_files
                    })
            finally:
                os.unlink(tmp.name)
    
    except Exception as e:
        print(f"✗ Error detectando CSV: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/detect-csv-local', methods=['POST'])
def detect_csv_local():
    """Detecta CSV en un ZIP subido localmente"""
    try:
        if 'zip_file' not in request.files:
            return jsonify({'error': 'No se subió ZIP'}), 400
        
        zip_file = request.files['zip_file']
        
        if zip_file.filename == '':
            return jsonify({'error': 'Archivo vacío'}), 400
        
        # Leer ZIP
        try:
            with zipfile.ZipFile(zip_file, 'r') as z:
                csv_files = [f for f in z.namelist() if f.endswith('.csv')]
                
                if not csv_files:
                    return jsonify({'error': 'No se encontró CSV en el ZIP'}), 400
                
                return jsonify({
                    'csv_file': csv_files[0],
                    'available_files': csv_files
                })
        except zipfile.BadZipFile:
            return jsonify({'error': 'El archivo no es un ZIP válido'}), 400
    
    except Exception as e:
        print(f"✗ Error detectando CSV local: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate', methods=['POST'])
def generate_workflow():
    """Genera y ejecuta un workflow con scripts del usuario"""
    try:
        # Validar que los campos requeridos existan
        if 'workflow_name' not in request.form:
            return jsonify({'status': 'error', 'message': 'Falta workflow_name'}), 400
        
        workflow_name = request.form['workflow_name']
        dataset_file = request.form['dataset_file']
        source_type = request.form.get('source_type', 'url')  # 'url' o 'local'
        
        # Preparar dataset según fuente
        if source_type == 'url':
            dataset_url = request.form['dataset_url']
            if not dataset_url or not dataset_file:
                return jsonify({'status': 'error', 'message': 'URL y nombre de archivo requeridos'}), 400
        elif source_type == 'local':
            if 'dataset_zip' not in request.files:
                return jsonify({'status': 'error', 'message': 'Falta archivo ZIP'}), 400
            
            zip_file = request.files['dataset_zip']
            if zip_file.filename == '':
                return jsonify({'status': 'error', 'message': 'Archivo ZIP vacío'}), 400
            
            # Guardar ZIP localmente
            dataset_dir = os.path.join(app.config['UPLOAD_FOLDER'], workflow_name)
            os.makedirs(dataset_dir, exist_ok=True)
            zip_path = os.path.join(dataset_dir, 'dataset.zip')
            zip_file.save(zip_path)
            
            # Extraer
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(dataset_dir)
            
            dataset_url = f"file://{os.path.abspath(dataset_dir)}"
            print(f"✓ ZIP extraído en {dataset_dir}")
        else:
            return jsonify({'status': 'error', 'message': 'Tipo de fuente inválido'}), 400
        
        # Validar scripts
        if 'prep_script' not in request.files:
            return jsonify({'status': 'error', 'message': 'Falta script de preparación'}), 400
        if 'process_script' not in request.files:
            return jsonify({'status': 'error', 'message': 'Falta script de procesamiento'}), 400
        if 'postproc_script' not in request.files:
            return jsonify({'status': 'error', 'message': 'Falta script de postprocesamiento'}), 400
        
        # Obtener archivos
        prep_file = request.files['prep_script']
        process_file = request.files['process_script']
        postproc_file = request.files['postproc_script']
        
        if prep_file.filename == '' or process_file.filename == '' or postproc_file.filename == '':
            return jsonify({'status': 'error', 'message': 'Archivos vacíos'}), 400
        
        # Leer contenido
        prep_bytes = prep_file.read()
        process_bytes = process_file.read()
        postproc_bytes = postproc_file.read()
        
        # Encodear en Base64
        prep_content = base64.b64encode(prep_bytes).decode('utf-8')
        process_content = base64.b64encode(process_bytes).decode('utf-8')
        postproc_content = base64.b64encode(postproc_bytes).decode('utf-8')
        
        print(f"✓ prep_content length: {len(prep_content)}")
        print(f"✓ process_content length: {len(process_content)}")
        print(f"✓ postproc_content length: {len(postproc_content)}")
        print(f"✓ Scripts encodeados en Base64")
        
        # Crear generador de workflow
        gen = WorkflowGenerator(
            workflow_name=workflow_name,
            dataset_url=dataset_url,
            dataset_file=dataset_file,
            prep_script_b64=prep_content,
            process_script_b64=process_content,
            postproc_script_b64=postproc_content
        )
        
        # Siempre añadir los 3 pasos
        gen.add_step('prepare', 'prep.py', dataset_file, 'prepared.csv')
        gen.add_step('process', 'process.py', 'prepared.csv', 'processed.csv')
        gen.add_step('postprocess', 'postproc.py', 'processed.csv', 'results.json')
        
        # Guardar en PostgreSQL si está marcado
        if 'save_postgres' in request.form:
            gen.add_postgres_save()
        
        # Generar YAML
        yaml_content = gen.generate()
        
        # Guardar YAML
        yaml_file = f"/tmp/{workflow_name}.yaml"
        with open(yaml_file, 'w') as f:
            f.write(yaml_content)
        
        print(f"✓ YAML generado: {yaml_file}")
        
        # Ejecutar con kubectl
        result = subprocess.run(
            ['kubectl', 'apply', '-f', yaml_file],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            return jsonify({
                'status': 'success',
                'message': f"Workflow {workflow_name} creado exitosamente",
                'workflow_name': workflow_name
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f"Error en kubectl: {result.stderr}"
            }), 400
    
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/workflows', methods=['GET'])
def list_workflows():
    """Lista workflows en Argo"""
    try:
        result = subprocess.run(
            ['kubectl', 'get', 'workflows', '-n', 'argo', '-o', 'json'],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            workflows = json.loads(result.stdout)
            return jsonify(workflows)
        else:
            return jsonify({'error': result.stderr}), 400
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8888)
