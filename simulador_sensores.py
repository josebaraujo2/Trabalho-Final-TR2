#!/usr/bin/env python3
"""
Código que gera dados simulados e envia para o servidor via HTTP
"""

import http.client
import json
import time
import random
from datetime import datetime

# Configurações
SERVIDOR_HOST = 'localhost'
SERVIDOR_PORT = 8000
INTERVALO_ENVIO = 3  

class SimuladorSensor:
    """Simula um nó sensor LoRa"""
    
    def __init__(self, sensor_id, temp_base=34, umid_base=50):
        self.sensor_id = sensor_id
        self.temp_base = temp_base
        self.umid_base = umid_base
        print(f"✓ Sensor {sensor_id} inicializado")
    
    def gerar_leitura(self):
        """Gera dados simulados com variação aleatória"""

        temperatura = self.temp_base + random.uniform(-5, 5)
        umidade = self.umid_base + random.uniform(-10, 10)
        umidade = max(0, min(100, umidade))  # Limita entre 0-100%
        
        poeira = random.uniform(10, 50)  # µg/m³
        
        return {
            'sensor_id': self.sensor_id,
            'temperatura': round(temperatura, 2),
            'umidade': round(umidade, 2),
            'poeira': round(poeira, 2),
            'timestamp_sensor': datetime.now().isoformat()
        }
    
    def enviar_dados(self, dados):
        """Envia dados via HTTP POST para o servidor"""
        try:
            conn = http.client.HTTPConnection(SERVIDOR_HOST, SERVIDOR_PORT)
            
            payload = json.dumps(dados)
            
            # Cabeçalhos HTTP
            headers = {
                'Content-Type': 'application/json',
                'Content-Length': len(payload)
            }
            
            # Envia requisição POST
            conn.request('POST', '/api/sensor', payload, headers)
            
            # Recebe resposta
            resposta = conn.getresponse()
            corpo_resposta = resposta.read().decode()
            
            if resposta.status == 200:
                print(f"✓ [{self.sensor_id}] Dados enviados: "
                      f"T={dados['temperatura']}°C, "
                      f"U={dados['umidade']}%, "
                      f"P={dados['poeira']}µg/m³")
                return True
            else:
                print(f"✗ [{self.sensor_id}] Erro {resposta.status}: {corpo_resposta}")
                return False
            
        except ConnectionRefusedError:
            print(f"✗ [{self.sensor_id}] Servidor não acessível em {SERVIDOR_HOST}:{SERVIDOR_PORT}")
            return False
        except Exception as e:
            print(f"✗ [{self.sensor_id}] Erro ao enviar: {str(e)}")
            return False
        finally:
            conn.close()

def simular_multiplos_sensores():
    """Simula múltiplos sensores enviando dados"""
    
    # Cria 3 sensores simulados em diferentes locais
    sensores = [
        SimuladorSensor('SALA_SERVIDORES_01', temp_base=28, umid_base=45),
        SimuladorSensor('SALA_SERVIDORES_02', temp_base=26, umid_base=50),
        SimuladorSensor('LABORATORIO_REDES', temp_base=24, umid_base=55)
    ]
    
    print("="*60)
    print("SIMULADOR DE SENSORES LoRa")
    print("="*60)
    print(f"Servidor destino: {SERVIDOR_HOST}:{SERVIDOR_PORT}")
    print(f"Intervalo de envio: {INTERVALO_ENVIO}s")
    print(f"Sensores ativos: {len(sensores)}")
    print("="*60)
    print("Pressione Ctrl+C para parar o simulador")
    print()
    
    contador = 0
    
    try:
        while True:
            contador += 1
            print(f"\n--- Ciclo {contador} ---")
            
            # Cada sensor gera e envia uma leitura
            for sensor in sensores:
                leitura = sensor.gerar_leitura()
                sensor.enviar_dados(leitura)
                time.sleep(0.5)  # Pequeno delay entre sensores
            
            # Aguarda antes do próximo ciclo
            print(f"\n Aguardando {INTERVALO_ENVIO}s até próximo envio...")
            time.sleep(INTERVALO_ENVIO)
            
    except KeyboardInterrupt:
        print("\n\n Simulador encerrado")
        print(f" Total de ciclos executados: {contador}")

if __name__ == '__main__':
    simular_multiplos_sensores()