import pandas as pd
import sys
import json
from datetime import datetime

def prep_data(input_file, output_file):
    """Preparar y limpiar datos de precios de petróleo"""
    
    try:
        # Cargar CSV
        df = pd.read_csv(input_file)
        print(f"✓ Datos cargados: {len(df)} registros")
        
        # Convertir Date a datetime
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date')
        print(f"✓ Fechas validadas: {df['Date'].min()} a {df['Date'].max()}")
        
        # Convertir precio a float
        df['Crude_Oil_Price'] = pd.to_numeric(df['Crude_Oil_Price'], errors='coerce')
        
        # Limpiar NaN
        initial_rows = len(df)
        df = df.dropna()
        print(f"✓ NaN removidos: {initial_rows - len(df)} filas")
        
        # Detectar y remover outliers extremos (valores > 3 desv. estándar)
        mean = df['Crude_Oil_Price'].mean()
        std = df['Crude_Oil_Price'].std()
        df = df[(df['Crude_Oil_Price'] >= mean - 3*std) & 
                (df['Crude_Oil_Price'] <= mean + 3*std)]
        print(f"✓ Outliers removidos: {len(df)} registros finales")
        
        # Guardar datos limpios
        df.to_csv(output_file, index=False)
        print(f"✓ Datos guardados en {output_file}")
        
        # Resumen
        summary = {
            "status": "success",
            "records": len(df),
            "date_range": {
                "start": df['Date'].min().strftime('%Y-%m-%d'),
                "end": df['Date'].max().strftime('%Y-%m-%d')
            },
            "price_stats": {
                "min": float(df['Crude_Oil_Price'].min()),
                "max": float(df['Crude_Oil_Price'].max()),
                "mean": float(df['Crude_Oil_Price'].mean())
            }
        }
        
        print(json.dumps(summary, indent=2))
        return True
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    
    success = prep_data(args.input, args.output)
    sys.exit(0 if success else 1)
