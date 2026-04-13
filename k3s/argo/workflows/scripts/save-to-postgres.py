import json
import psycopg2
import sys
from datetime import datetime

def save_to_postgres(json_file, db_host, db_user, db_password, db_name):
    """Guardar datos de results.json en PostgreSQL"""
    
    try:
        # Leer JSON
        with open(json_file, 'r') as f:
            data = json.load(f)
        print(f"✓ JSON cargado: {json_file}")
        
        # Conectar a PostgreSQL
        conn = psycopg2.connect(
            host=db_host,
            user=db_user,
            password=db_password,
            database=db_name
        )
        cursor = conn.cursor()
        print(f"✓ Conectado a PostgreSQL: {db_name}")
        
        # Crear tabla si no existe
        create_table_query = """
        CREATE TABLE IF NOT EXISTS fuel_analysis (
            id SERIAL PRIMARY KEY,
            timestamp TIMESTAMP DEFAULT NOW(),
            date_start DATE,
            date_end DATE,
            total_months INTEGER,
            min_price FLOAT,
            max_price FLOAT,
            avg_price FLOAT,
            std_dev FLOAT,
            latest_price FLOAT,
            latest_date DATE,
            ma_12m FLOAT,
            data_json JSONB
        )
        """
        cursor.execute(create_table_query)
        conn.commit()
        print("✓ Tabla fuel_analysis lista")
        
        # Extraer datos del JSON
        summary = data['summary']
        insert_query = """
        INSERT INTO fuel_analysis 
        (date_start, date_end, total_months, min_price, max_price, avg_price, std_dev, latest_price, latest_date, ma_12m, data_json)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        values = (
            summary['date_range']['start'],
            summary['date_range']['end'],
            summary['total_months'],
            summary['global_statistics']['min_price'],
            summary['global_statistics']['max_price'],
            summary['global_statistics']['avg_price'],
            summary['global_statistics']['std_dev'],
            summary['current_trend']['latest_price'],
            summary['current_trend']['latest_date'],
            summary['current_trend']['ma_12m'],
            json.dumps(data)
        )
        
        cursor.execute(insert_query, values)
        conn.commit()
        print("✓ Datos guardados en PostgreSQL")
        
        # Verificar
        cursor.execute("SELECT COUNT(*) FROM fuel_analysis")
        count = cursor.fetchone()[0]
        print(f"✓ Total registros en BD: {count}")
        
        cursor.close()
        conn.close()
        
        print(f"\n✓ Guardado exitoso en PostgreSQL")
        return True
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--json-file', required=True)
    parser.add_argument('--db-host', default='postgres-postgresql.postgres.svc.cluster.local')
    parser.add_argument('--db-user', default='cascade')
    parser.add_argument('--db-password', default='cascade123')
    parser.add_argument('--db-name', default='cascade_db')
    args = parser.parse_args()
    
    success = save_to_postgres(args.json_file, args.db_host, args.db_user, args.db_password, args.db_name)
    sys.exit(0 if success else 1)
