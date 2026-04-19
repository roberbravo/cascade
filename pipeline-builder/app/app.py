from flask import Flask, render_template, request, jsonify
from workflow_generator import WorkflowGenerator
import subprocess
import json
import os
import base64
import tempfile
import zipfile

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/detect-csv', methods=['POST'])
def detect_csv():
    try:
        data = request.json
        url = data.get('url')
        if not url:
            return jsonify({'error': 'URL requerida'}), 400

        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
            result = subprocess.run(
                ['curl', '-L', '-o', tmp.name, url],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0:
                return jsonify({'error': 'No se pudo descargar el ZIP'}), 400

            try:
                with zipfile.ZipFile(tmp.name, 'r') as z:
                    csv_files = [f for f in z.namelist() if f.endswith('.csv')]
                    if not csv_files:
                        return jsonify({'error': 'No se encontró CSV en el ZIP'}), 400
                    return jsonify({'csv_file': csv_files[0], 'available_files': csv_files})
            finally:
                os.unlink(tmp.name)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/detect-csv-local', methods=['POST'])
def detect_csv_local():
    try:
        if 'zip_file' not in request.files:
            return jsonify({'error': 'No se subió ZIP'}), 400

        zip_file = request.files['zip_file']
        if zip_file.filename == '':
            return jsonify({'error': 'Archivo vacío'}), 400

        try:
            with zipfile.ZipFile(zip_file, 'r') as z:
                csv_files = [f for f in z.namelist() if f.endswith('.csv')]
                if not csv_files:
                    return jsonify({'error': 'No se encontró CSV en el ZIP'}), 400
                return jsonify({'csv_file': csv_files[0], 'available_files': csv_files})
        except zipfile.BadZipFile:
            return jsonify({'error': 'El archivo no es un ZIP válido'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate', methods=['POST'])
def generate_workflow():
    try:
        workflow_name = request.form.get('workflow_name')
        dataset_file = request.form.get('dataset_file')
        source_type = request.form.get('source_type', 'url')
        step_count = int(request.form.get('step_count', 0))

        if not workflow_name:
            return jsonify({'status': 'error', 'message': 'Falta workflow_name'}), 400

        if step_count == 0:
            return jsonify({'status': 'error', 'message': 'Añade al menos un paso'}), 400

        # Dataset
        if source_type == 'url':
            dataset_url = request.form.get('dataset_url')
            if not dataset_url or not dataset_file:
                return jsonify({'status': 'error', 'message': 'URL y nombre de archivo requeridos'}), 400
        elif source_type == 'local':
            if 'dataset_zip' not in request.files:
                return jsonify({'status': 'error', 'message': 'Falta archivo ZIP'}), 400
            zip_file = request.files['dataset_zip']
            dataset_dir = os.path.join(app.config['UPLOAD_FOLDER'], workflow_name)
            os.makedirs(dataset_dir, exist_ok=True)
            zip_path = os.path.join(dataset_dir, 'dataset.zip')
            zip_file.save(zip_path)
            with zipfile.ZipFile(zip_path, 'r') as z:
                z.extractall(dataset_dir)
            dataset_url = f"file://{os.path.abspath(dataset_dir)}"
        else:
            return jsonify({'status': 'error', 'message': 'Tipo de fuente inválido'}), 400

        # Recoger pasos dinámicos
        steps = []
        for i in range(1, step_count + 1):
            step_name = request.form.get(f'step_name_{i}')
            step_file = request.files.get(f'step_script_{i}')

            if not step_name or not step_file or step_file.filename == '':
                return jsonify({'status': 'error', 'message': f'Paso {i} incompleto'}), 400

            script_b64 = base64.b64encode(step_file.read()).decode('utf-8')
            steps.append({
                'name': step_name,
                'script_b64': script_b64,
                'script_filename': f'step_{i}.py'
            })

        print(f"✓ {len(steps)} pasos recibidos")

        # Generar workflow
        gen = WorkflowGenerator(
            workflow_name=workflow_name,
            dataset_url=dataset_url,
            dataset_file=dataset_file,
            steps=steps
        )

        if 'save_postgres' in request.form:
            gen.add_postgres_save()

        yaml_content = gen.generate()

        yaml_file = f"/tmp/{workflow_name}.yaml"
        with open(yaml_file, 'w') as f:
            f.write(yaml_content)

        print(f"✓ YAML generado: {yaml_file}")

        result = subprocess.run(
            ['kubectl', 'apply', '-f', yaml_file],
            capture_output=True, text=True
        )

        if result.returncode == 0:
            return jsonify({
                'status': 'success',
                'message': f"Workflow '{workflow_name}' creado con {len(steps)} pasos"
            })
        else:
            return jsonify({'status': 'error', 'message': f"Error kubectl: {result.stderr}"}), 400

    except Exception as e:
        print(f"✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/workflows', methods=['GET'])
def list_workflows():
    try:
        result = subprocess.run(
            ['kubectl', 'get', 'workflows', '-n', 'argo', '-o', 'json'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return jsonify(json.loads(result.stdout))
        else:
            return jsonify({'error': result.stderr}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8888)
