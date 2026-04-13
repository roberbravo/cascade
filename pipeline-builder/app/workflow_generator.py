import yaml
import json
from datetime import datetime
import base64

class WorkflowGenerator:
    def __init__(self, workflow_name, dataset_url, dataset_file, 
                 prep_script_b64=None, process_script_b64=None, postproc_script_b64=None):
        self.workflow_name = workflow_name
        self.dataset_url = dataset_url
        self.dataset_file = dataset_file
        self.prep_script_b64 = prep_script_b64
        self.process_script_b64 = process_script_b64
        self.postproc_script_b64 = postproc_script_b64
        self.steps = []
        self.save_postgres = False
    
    def add_step(self, name, script_name, input_file, output_file):
        """Añade un paso de procesado"""
        self.steps.append({
            "name": name,
            "script": script_name,
            "input": input_file,
            "output": output_file
        })
    
    def add_postgres_save(self):
        """Marca que hay que guardar en PostgreSQL"""
        self.save_postgres = True
    
    def generate(self):
        """Genera el YAML del workflow"""
        
        workflow = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Workflow",
            "metadata": {
                "name": self.workflow_name,
                "namespace": "argo"
            },
            "spec": {
                "serviceAccountName": "argo-workflow-sa",
                "entrypoint": "cascade",
                "arguments": {
                    "parameters": [
                        {"name": "dataset-url", "value": self.dataset_url},
                        {"name": "dataset-file", "value": self.dataset_file},
                        {"name": "prep-script-b64", "value": self.prep_script_b64 or ""},
                        {"name": "process-script-b64", "value": self.process_script_b64 or ""},
                        {"name": "postproc-script-b64", "value": self.postproc_script_b64 or ""}
                    ]
                },
                "volumeClaimTemplates": [
                    {
                        "metadata": {"name": "workdir"},
                        "spec": {
                            "accessModes": ["ReadWriteOnce"],
                            "resources": {"requests": {"storage": "2Gi"}}
                        }
                    }
                ],
                "volumes": [
                    {
                        "name": "scripts",
                        "configMap": {"name": "cascade-scripts"}
                    }
                ],
                "templates": []
            }
        }
        
        # Template principal (orquestador)
        steps_list = []
        
        # Paso de descarga
        steps_list.append([{
            "name": "download",
            "template": "download-step",
            "arguments": {
                "parameters": [
                    {"name": "url", "value": "{{workflow.parameters.dataset-url}}"}
                ]
            }
        }])
        
        # Pasos de procesado
        for step in self.steps:
            steps_list.append([{
                "name": step["name"],
                "template": "python-step",
                "arguments": {
                    "parameters": [
                        {"name": "script", "value": step["script"]},
                        {"name": "input", "value": step["input"]},
                        {"name": "output", "value": step["output"]}
                    ]
                }
            }])
        
        # Paso de guardar en PostgreSQL si está habilitado
        if self.save_postgres:
            steps_list.append([{
                "name": "save-to-postgres",
                "template": "save-postgres-step"
            }])
        
        # Paso final de resumen
        steps_list.append([{
            "name": "summary",
            "template": "show-summary"
        }])
        
        cascade_template = {
            "name": "cascade",
            "steps": steps_list
        }
        workflow["spec"]["templates"].append(cascade_template)
        
        # Templates de ejecución
        workflow["spec"]["templates"].append(self._download_template())
        workflow["spec"]["templates"].append(self._python_template())
        if self.save_postgres:
            workflow["spec"]["templates"].append(self._postgres_template())
        workflow["spec"]["templates"].append(self._summary_template())
        
        return yaml.dump(workflow, default_flow_style=False, sort_keys=False)
    
    def _download_template(self):
        return {
            "name": "download-step",
            "inputs": {
                "parameters": [{"name": "url"}]
            },
            "container": {
                "image": "curlimages/curl:latest",
                "command": ["sh", "-c"],
                "args": [
                    "cd /workdir\n"
                    "echo '📥 Descargando dataset...'\n"
                    "curl -L -o fuel.zip '{{inputs.parameters.url}}'\n"
                    "echo '📂 Extrayendo archivo...'\n"
                    "unzip -o fuel.zip\n"
                    "ls -lh"
                ],
                "volumeMounts": [{"name": "workdir", "mountPath": "/workdir"}]
            }
        }
    
    def _python_template(self):
        return {
            "name": "python-step",
            "inputs": {
                "parameters": [
                    {"name": "script"},
                    {"name": "input"},
                    {"name": "output"}
                ]
            },
            "container": {
                "image": "python:3.11-slim",
                "command": ["sh", "-c"],
                "args": [
                    "cd /workdir\n"
                    "cat > /tmp/prep_b64.txt << 'BASE64END'\n"
                    "{{workflow.parameters.prep-script-b64}}\n"
                    "BASE64END\n"
                    "cat > /tmp/process_b64.txt << 'BASE64END'\n"
                    "{{workflow.parameters.process-script-b64}}\n"
                    "BASE64END\n"
                    "cat > /tmp/postproc_b64.txt << 'BASE64END'\n"
                    "{{workflow.parameters.postproc-script-b64}}\n"
                    "BASE64END\n"
                    "base64 -d /tmp/prep_b64.txt > prep.py\n"
                    "base64 -d /tmp/process_b64.txt > process.py\n"
                    "base64 -d /tmp/postproc_b64.txt > postproc.py\n"
                    "pip install pandas numpy -q\n"
                    "echo '⚙️  Ejecutando {{inputs.parameters.script}}...'\n"
                    "python {{inputs.parameters.script}} --input {{inputs.parameters.input}} --output {{inputs.parameters.output}}\n"
                    "echo '✓ {{inputs.parameters.script}} completado'"
                ],
                "volumeMounts": [
                    {"name": "workdir", "mountPath": "/workdir"},
                    {"name": "scripts", "mountPath": "/scripts"}
                ]
            }
        }
    
    def _postgres_template(self):
        return {
            "name": "save-postgres-step",
            "container": {
                "image": "python:3.11-slim",
                "command": ["sh", "-c"],
                "args": [
                    "cd /workdir\n"
                    "pip install psycopg2-binary -q\n"
                    "echo '💾 Guardando en PostgreSQL...'\n"
                    "python /scripts/save-to-postgres.py --json-file results.json --db-host postgres-postgresql.postgres.svc.cluster.local --db-user cascade --db-password cascade123 --db-name cascade_db\n"
                    "echo '✓ Datos guardados en PostgreSQL'"
                ],
                "volumeMounts": [
                    {"name": "workdir", "mountPath": "/workdir"},
                    {"name": "scripts", "mountPath": "/scripts"}
                ]
            }
        }
    
    def _summary_template(self):
        return {
            "name": "show-summary",
            "container": {
                "image": "alpine:latest",
                "command": ["sh", "-c"],
                "args": [
                    "echo '==========================================' && "
                    "echo '✓ PIPELINE CASCADE COMPLETADO' && "
                    "echo '==========================================' && "
                    "echo 'Pasos ejecutados:' && "
                    "echo '  1. ✓ Descarga de dataset' && "
                    "echo '  2. ✓ Preparación de datos' && "
                    "echo '  3. ✓ Procesamiento' && "
                    "echo '  4. ✓ Postprocesamiento' && "
                    "echo '  5. ✓ Guardado en PostgreSQL' && "
                    "echo '==========================================' "
                ],
                "volumeMounts": [{"name": "workdir", "mountPath": "/workdir"}]
            }
        }
