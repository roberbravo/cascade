import yaml
from datetime import datetime

class WorkflowGenerator:
    def __init__(self, workflow_name, dataset_url, dataset_file, steps):
        self.workflow_name = workflow_name
        self.dataset_url = dataset_url
        self.dataset_file = dataset_file
        self.steps = steps  # lista de {name, script_b64, script_filename}
        self.save_postgres = False

    def add_postgres_save(self):
        self.save_postgres = True

    def generate(self):
        # Parámetros base
        parameters = [
            {"name": "dataset-url", "value": self.dataset_url},
            {"name": "dataset-file", "value": self.dataset_file},
        ]

        # Añadir cada script como parámetro b64
        for i, step in enumerate(self.steps):
            parameters.append({
                "name": f"script-b64-{i+1}",
                "value": step['script_b64']
            })

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
                "arguments": {"parameters": parameters},
                "volumeClaimTemplates": [{
                    "metadata": {"name": "workdir"},
                    "spec": {
                        "accessModes": ["ReadWriteOnce"],
                        "resources": {"requests": {"storage": "2Gi"}}
                    }
                }],
                "templates": []
            }
        }

        # Template principal
        steps_list = []

        # Paso de descarga
        steps_list.append([{
            "name": "download",
            "template": "download-step",
            "arguments": {
                "parameters": [
                    {"name": "url", "value": "{{workflow.parameters.dataset-url}}"},
                    {"name": "filename", "value": "{{workflow.parameters.dataset-file}}"}
                ]
            }
        }])

        # Pasos dinámicos
        prev_output = self.dataset_file
        for i, step in enumerate(self.steps):
            is_last = (i == len(self.steps) - 1)
            output = "results.json" if is_last else f"output_{i+1}.csv"
            steps_list.append([{
                "name": step['name'],
                "template": "python-step",
                "arguments": {
                    "parameters": [
                        {"name": "script-b64", "value": f"{{{{workflow.parameters.script-b64-{i+1}}}}}"},
                        {"name": "script-name", "value": step['script_filename']},
                        {"name": "input", "value": prev_output},
                        {"name": "output", "value": output}
                    ]
                }
            }])
            prev_output = output

        # Paso PostgreSQL
        if self.save_postgres:
            steps_list.append([{
                "name": "save-to-postgres",
                "template": "save-postgres-step"
            }])

        # Paso summary
        steps_list.append([{
            "name": "summary",
            "template": "show-summary"
        }])

        workflow["spec"]["templates"].append({
            "name": "cascade",
            "steps": steps_list
        })

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
                "parameters": [
                    {"name": "url"},
                    {"name": "filename"}
                ]
            },
            "container": {
                "image": "curlimages/curl:latest",
                "command": ["sh", "-c"],
                "args": [
                    "cd /workdir && "
                    "echo '📥 Descargando dataset...' && "
                    "curl -L -o dataset.zip '{{inputs.parameters.url}}' && "
                    "echo '📂 Extrayendo...' && "
                    "unzip -o dataset.zip && "
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
                    {"name": "script-b64"},
                    {"name": "script-name"},
                    {"name": "input"},
                    {"name": "output"}
                ]
            },
            "container": {
                "image": "python:3.11-slim",
                "command": ["sh", "-c"],
                "args": [
                    "cd /workdir\n"
                    "echo '{{inputs.parameters.script-b64}}' | base64 -d > {{inputs.parameters.script-name}}\n"
                    "pip install pandas numpy -q\n"
                    "echo '⚙️ Ejecutando {{inputs.parameters.script-name}}...'\n"
                    "python {{inputs.parameters.script-name}} --input {{inputs.parameters.input}} --output {{inputs.parameters.output}}\n"
                    "echo '✓ Completado'"
                ],
                "volumeMounts": [{"name": "workdir", "mountPath": "/workdir"}]
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
                    "python -c \"\n"
                    "import json, psycopg2\n"
                    "conn = psycopg2.connect(host='postgres-postgresql.postgres.svc.cluster.local', user='cascade', password='cascade123', database='cascade_db')\n"
                    "cur = conn.cursor()\n"
                    "cur.execute('CREATE TABLE IF NOT EXISTS pipeline_results (id SERIAL PRIMARY KEY, timestamp TIMESTAMP DEFAULT NOW(), data JSONB)')\n"
                    "data = open('results.json').read()\n"
                    "cur.execute('INSERT INTO pipeline_results (data) VALUES (%s)', (data,))\n"
                    "conn.commit()\n"
                    "print('✓ Guardado en PostgreSQL')\n"
                    "\""
                ],
                "volumeMounts": [{"name": "workdir", "mountPath": "/workdir"}]
            }
        }

    def _summary_template(self):
    	num_steps = len(self.steps)
    	return {
        	"name": "show-summary",
        	"container": {
            		"image": "alpine:latest",
            		"command": ["sh", "-c"],
            		"args": [
                		f"echo '===========================================' && "
                		f"echo '✓ PIPELINE CASCADE COMPLETADO' && "
                		f"echo '===========================================' && "
                		f"echo 'Pasos ejecutados: {num_steps}' && "
               			 f"echo '==========================================='",
            		],
            		"volumeMounts": [{"name": "workdir", "mountPath": "/workdir"}]
        }
    }

