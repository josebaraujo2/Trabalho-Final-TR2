#!/usr/bin/env python3
"""
GATEWAY BRIDGE - ESP32 Serial → Servidor HTTP
Substitui o cliente.py, recebendo dados via LoRa
"""

import serial
import json
import http.client
import time
from datetime import datetime

# ===== CONFIGURAÇÕES =====
SERIAL_PORT = 'COM5'  # ajustar para porta
SERIAL_BAUD = 115200

SERVIDOR_HOST = 'localhost'
SERVIDOR_PORT = 8000

# ===== ESTATÍSTICAS =====
pacotes_recebidos = 0
pacotes_enviados = 0
erros = 0

def conectar_serial():
    """Conecta à porta serial do Gateway ESP32"""
    print("🔌 Conectando ao Gateway ESP32...")
    print(f"   Porta: {SERIAL_PORT}")
    print(f"   Baud: {SERIAL_BAUD}")
    
    try:
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1)
        time.sleep(2)  # Aguarda inicialização
        print("✓ Serial conectada!\n")
        return ser
    except serial.SerialException as e:
        print(f"❌ Erro ao abrir porta {SERIAL_PORT}")
        print(f"   Mensagem: {e}")
        print("\n💡 Dica: Verifique se:")
        print("   - O Gateway ESP32 está conectado via USB")
        print("   - A porta COM está correta")
        print("   - Nenhum Serial Monitor está aberto")
        return None
    except Exception as e:
        print(f"❌ Erro desconhecido: {e}")
        return None

def enviar_para_servidor(dados):
    """Envia dados via HTTP POST (igual ao cliente.py)"""
    global pacotes_enviados, erros
    
    try:
        # Conecta ao servidor
        conn = http.client.HTTPConnection(SERVIDOR_HOST, SERVIDOR_PORT, timeout=5)
        
        # Prepara payload (formato do cliente.py)
        payload = json.dumps(dados)
        
        # Cabeçalhos HTTP
        headers = {
            'Content-Type': 'application/json',
            'Content-Length': len(payload)
        }
        
        # Envia POST para /api/sensor (mesmo endpoint do cliente.py)
        conn.request('POST', '/api/sensor', payload, headers)
        
        # Recebe resposta
        resposta = conn.getresponse()
        corpo = resposta.read().decode()
        
        if resposta.status == 200:
            pacotes_enviados += 1
            print(f"✓ Enviado ao servidor: {dados['sensor_id']}")
            print(f"  T:{dados['temperatura']}°C, U:{dados['umidade']}%, P:{dados['poeira']}µg/m³")
            print(f"  RSSI:{dados.get('rssi', 'N/A')} dBm, SNR:{dados.get('snr', 'N/A')}")
            return True
        else:
            erros += 1
            print(f"⚠️  Servidor respondeu {resposta.status}: {corpo}")
            return False
            
    except ConnectionRefusedError:
        erros += 1
        print(f"❌ Servidor não acessível em {SERVIDOR_HOST}:{SERVIDOR_PORT}")
        print("   Certifique-se que o servidor.py está rodando!")
        return False
    except Exception as e:
        erros += 1
        print(f"❌ Erro ao enviar: {e}")
        return False
    finally:
        try:
            conn.close()
        except:
            pass

def processar_linha_serial(linha):
    """Processa linha recebida do Gateway ESP32"""
    global pacotes_recebidos, erros
    
    # Protocolo: DATA:{json}
    if linha.startswith('DATA:'):
        try:
            json_str = linha[5:].strip()
            
            # Parse JSON
            dados = json.loads(json_str)
            
            # ===== VALIDAÇÃO ROBUSTA (filtro anti-corrupção) =====
            # Verifica campos obrigatórios
            if 'sensor_id' not in dados or 'temperatura' not in dados:
                print(f"⚠️  Pacote incompleto, ignorando...")
                erros += 1
                return
            
            # Verifica se sensor_id é string válida (sem caracteres estranhos)
            if not isinstance(dados['sensor_id'], str) or len(dados['sensor_id']) > 50:
                print(f"⚠️  sensor_id inválido, ignorando...")
                erros += 1
                return
            
            # Verifica se há caracteres não-ASCII no sensor_id
            try:
                dados['sensor_id'].encode('ascii')
            except UnicodeEncodeError:
                print(f"⚠️  sensor_id corrompido (caracteres inválidos), ignorando...")
                erros += 1
                return
            
            # Verifica valores numéricos
            try:
                temp = float(dados['temperatura'])
                umid = float(dados['umidade'])
                poeira = float(dados['poeira'])
                
                # Validação de ranges sensatos
                if not (0 <= temp <= 60):  # Temperatura entre 0-60°C
                    print(f"⚠️  Temperatura fora do range ({temp}°C), ignorando...")
                    erros += 1
                    return
                    
                if not (0 <= umid <= 100):  # Umidade 0-100%
                    print(f"⚠️  Umidade fora do range ({umid}%), ignorando...")
                    erros += 1
                    return
                    
            except (ValueError, TypeError):
                print(f"⚠️  Valores numéricos inválidos, ignorando...")
                erros += 1
                return
            
            # ===== PACOTE VÁLIDO! =====
            pacotes_recebidos += 1
            
            print(f"\n✅ Pacote LoRa VÁLIDO #{pacotes_recebidos}")
            
            # Adiciona timestamp do servidor (igual ao cliente.py)
            dados['timestamp_sensor'] = datetime.now().isoformat()
            
            # Envia para servidor HTTP
            enviar_para_servidor(dados)
            
        except json.JSONDecodeError as e:
            print(f"⚠️  JSON corrompido, ignorando... [{str(e)[:50]}]")
            erros += 1
        except Exception as e:
            print(f"⚠️  Erro ao processar, ignorando... [{str(e)[:50]}]")
            erros += 1
    
    # Outras mensagens do Gateway (logs)
    elif linha.startswith('READY:') or linha.startswith('ERROR:'):
        print(f"[Gateway] {linha}")
    elif linha.strip():
        # Ignora linhas vazias, mostra outras
        if not linha.startswith('✓') and not linha.startswith('═'):
            print(f"[Gateway] {linha}")

def exibir_estatisticas():
    """Exibe estatísticas finais"""
    print("\n" + "="*60)
    print("📊 ESTATÍSTICAS FINAIS")
    print("="*60)
    print(f"Pacotes LoRa recebidos:     {pacotes_recebidos}")
    print(f"Pacotes enviados ao servidor: {pacotes_enviados}")
    print(f"Erros:                      {erros}")
    if pacotes_recebidos > 0:
        taxa_sucesso = (pacotes_enviados / pacotes_recebidos) * 100
        print(f"Taxa de sucesso:            {taxa_sucesso:.1f}%")
    print("="*60)

def main():
    """Função principal"""
    print("\n" + "="*60)
    print("  GATEWAY BRIDGE - LoRa → Servidor HTTP")
    print("="*60)
    print()
    
    # Conecta à serial
    ser = conectar_serial()
    if not ser:
        print("\n❌ Não foi possível conectar. Encerrando.")
        return
    
    print("="*60)
    print("✓ Bridge ativo!")
    print(f"Servidor destino: http://{SERVIDOR_HOST}:{SERVIDOR_PORT}/api/sensor")
    print("Aguardando dados LoRa...")
    print("Pressione Ctrl+C para parar")
    print("="*60)
    print()
    
    try:
        while True:
            # lê linha da serial
            if ser.in_waiting:
                try:
                    linha = ser.readline().decode('utf-8', errors='ignore').strip()
                    
                    if linha:
                        processar_linha_serial(linha)
                        
                except UnicodeDecodeError:
                    pass  # Ignora caracteres inválidos
                except Exception as e:
                    print(f"⚠️  Erro ao ler serial: {e}")
            
            time.sleep(0.01)  # Pequeno delay
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Parando bridge...")
    except Exception as e:
        print(f"\n❌ Erro fatal: {e}")
    finally:
        ser.close()
        exibir_estatisticas()
        print("✓ Bridge encerrado\n")

if __name__ == '__main__':
    main()