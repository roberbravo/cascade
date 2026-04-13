import pandas as pd
import numpy as np
import json
import sys
from datetime import datetime

def process_data(input_file, output_file):
    """Procesar datos: media móvil, anomalías, volatilidad, etc"""
    
    try:
        # Cargar datos limpios
        df = pd.read_csv(input_file)
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date')
        print(f"✓ Datos cargados: {len(df)} registros")
        
        # Media móvil 12 meses (anual)
        df['MA_12M'] = df['Crude_Oil_Price'].rolling(window=12, min_periods=1).mean()
        print("✓ Media móvil 12M calculada")
        
        # Detección de anomalías (Z-score)
        df['Z_Score'] = np.abs((df['Crude_Oil_Price'] - df['Crude_Oil_Price'].mean()) / 
                               df['Crude_Oil_Price'].std())
        df['Is_Anomaly'] = df['Z_Score'] > 2.5
        anomalies = df[df['Is_Anomaly']].shape[0]
        print(f"✓ Anomalías detectadas: {anomalies}")
        
        # Tasa de cambio MoM (mes a mes)
        df['MoM_Change'] = df['Crude_Oil_Price'].pct_change() * 100
        print("✓ Tasa de cambio MoM calculada")
        
        # Volatilidad por década
        df['Year'] = df['Date'].dt.year
        df['Decade'] = (df['Year'] // 10) * 10
        volatility = df.groupby('Decade')['Crude_Oil_Price'].std()
        print(f"✓ Volatilidad por década calculada")
        
        # Máximos y mínimos por año
        yearly_stats = df.groupby('Year')['Crude_Oil_Price'].agg(['min', 'max', 'mean'])
        print(f"✓ Estadísticas anuales calculadas")
        
        # Guardar datos procesados
        df.to_csv(output_file, index=False)
        print(f"✓ Datos procesados guardados")
        
        # Resumen en JSON
        summary = {
            "status": "success",
            "total_records": len(df),
            "anomalies_detected": int(anomalies),
            "price_statistics": {
                "min": float(df['Crude_Oil_Price'].min()),
                "max": float(df['Crude_Oil_Price'].max()),
                "mean": float(df['Crude_Oil_Price'].mean()),
                "std": float(df['Crude_Oil_Price'].std())
            },
            "volatility_by_decade": {str(int(k)): float(v) for k, v in volatility.items()},
            "largest_monthly_change": {
                "date": df.loc[df['MoM_Change'].abs().idxmax(), 'Date'].strftime('%Y-%m-%d'),
                "change_percent": float(df['MoM_Change'].max() if abs(df['MoM_Change'].max()) > abs(df['MoM_Change'].min()) 
                                       else df['MoM_Change'].min())
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
    
    success = process_data(args.input, args.output)
    sys.exit(0 if success else 1)
