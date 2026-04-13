import pandas as pd
import json
import sys
from datetime import datetime

def postproc_data(input_file, output_file):
    """Postprocesar: agregar por año, eventos, formatear para Grafana"""
    
    try:
        # Cargar datos procesados
        df = pd.read_csv(input_file)
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date')
        print(f"✓ Datos cargados: {len(df)} registros")
        
        # Agregar por año
        df['Year'] = df['Date'].dt.year
        yearly = df.groupby('Year')['Crude_Oil_Price'].agg(['mean', 'min', 'max']).reset_index()
        yearly.columns = ['year', 'avg_price', 'min_price', 'max_price']
        print("✓ Datos agregados por año")
        
        # Eventos históricos importantes (crisis energéticas)
        events = [
            {"date": "1973-10-01", "name": "Crisis OPEC 1973", "type": "crisis"},
            {"date": "1979-01-01", "name": "Crisis Iraní 1979", "type": "crisis"},
            {"date": "1991-08-01", "name": "Guerra del Golfo 1991", "type": "crisis"},
            {"date": "2008-06-01", "name": "Máximo histórico 2008", "type": "peak"},
            {"date": "2020-04-01", "name": "Crash COVID-19 2020", "type": "crash"}
        ]
        print(f"✓ {len(events)} eventos históricos identificados")
        
        # Formatear para Grafana (timestamps ISO, JSON)
        grafana_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_months": len(df),
                "date_range": {
                    "start": df['Date'].min().strftime('%Y-%m-%d'),
                    "end": df['Date'].max().strftime('%Y-%m-%d')
                },
                "global_statistics": {
                    "min_price": float(df['Crude_Oil_Price'].min()),
                    "max_price": float(df['Crude_Oil_Price'].max()),
                    "avg_price": float(df['Crude_Oil_Price'].mean()),
                    "std_dev": float(df['Crude_Oil_Price'].std())
                },
                "current_trend": {
                    "latest_price": float(df['Crude_Oil_Price'].iloc[-1]),
                    "latest_date": df['Date'].iloc[-1].strftime('%Y-%m-%d'),
                    "ma_12m": float(df['MA_12M'].iloc[-1]) if 'MA_12M' in df else None
                }
            },
            "yearly_data": yearly.to_dict('records'),
            "historical_events": events,
            "anomalies": df[df['Is_Anomaly'] == True][['Date', 'Crude_Oil_Price', 'Z_Score']].to_dict('records') 
                        if 'Is_Anomaly' in df else []
        }
        
        # Convertir Dates en anomalies a strings
        for anomaly in grafana_data['anomalies']:
            if 'Date' in anomaly:
                anomaly['Date'] = str(anomaly['Date'])
        
        # Guardar JSON
        with open(output_file, 'w') as f:
            json.dump(grafana_data, f, indent=2)
        print(f"✓ Datos formateados para Grafana")
        print(f"✓ Guardado en {output_file}")
        
        # Resumen final
        print("\n=== RESUMEN FINAL ===")
        print(f"Período: {grafana_data['summary']['date_range']['start']} a {grafana_data['summary']['date_range']['end']}")
        print(f"Precio actual: ${grafana_data['summary']['current_trend']['latest_price']:.2f}")
        print(f"Precio medio histórico: ${grafana_data['summary']['global_statistics']['avg_price']:.2f}")
        print(f"Rango: ${grafana_data['summary']['global_statistics']['min_price']:.2f} - ${grafana_data['summary']['global_statistics']['max_price']:.2f}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    
    success = postproc_data(args.input, args.output)
    sys.exit(0 if success else 1)
