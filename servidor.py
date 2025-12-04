#!/usr/bin/env python3
"""
Código do servidor
"""

import http.server
import socketserver
import json
import sqlite3
from datetime import datetime
from urllib.parse import parse_qs, urlparse

# Configurações
PORT = 8000
DB_FILE = 'monitoramento.db'

class MonitoringDatabase:
    """Gerencia o banco de dados SQLite"""
    
    def __init__(self, db_file):
        self.db_file = db_file
        self.init_database()
    
    def init_database(self):
        """Cria tabela se não existir"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS leituras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                sensor_id TEXT NOT NULL,
                temperatura REAL,
                umidade REAL,
                poeira REAL
            )
        ''')
        conn.commit()
        conn.close()
        print(f"✓ Banco de dados iniciado: {self.db_file}")
    
    def inserir_leitura(self, sensor_id, temperatura, umidade, poeira):
        """Insere nova leitura no banco"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        timestamp = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO leituras (timestamp, sensor_id, temperatura, umidade, poeira)
            VALUES (?, ?, ?, ?, ?)
        ''', (timestamp, sensor_id, temperatura, umidade, poeira))
        conn.commit()
        conn.close()
        print(f"✓ Leitura armazenada: {sensor_id} - T:{temperatura}°C U:{umidade}% P:{poeira}µg/m³")
    
    def obter_ultimas_leituras(self, limite=20):
        """Retorna as últimas N leituras"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT timestamp, sensor_id, temperatura, umidade, poeira
            FROM leituras
            ORDER BY id DESC
            LIMIT ?
        ''', (limite,))
        resultados = cursor.fetchall()
        conn.close()
        
        leituras = []
        for row in resultados:
            leituras.append({
                'timestamp': row[0],
                'sensor_id': row[1],
                'temperatura': row[2],
                'umidade': row[3],
                'poeira': row[4]
            })
        return leituras

# Instância global do banco de dados
db = MonitoringDatabase(DB_FILE)

class MonitoringHandler(http.server.SimpleHTTPRequestHandler):
    """Handler HTTP para requisições do servidor"""
    
    def do_GET(self):
        """Responde requisições GET"""
        parsed_path = urlparse(self.path)
        
        # Dashboard HTML
        if parsed_path.path == '/' or parsed_path.path == '/dashboard':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            html = self.gerar_dashboard()
            self.wfile.write(html.encode())
        
        # API JSON para obter dados
        elif parsed_path.path == '/api/leituras':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            leituras = db.obter_ultimas_leituras(20)
            self.wfile.write(json.dumps(leituras, indent=2).encode())
        
        else:
            self.send_error(404)
    
    def do_POST(self):
        """Recebe dados dos sensores via POST"""
        if self.path == '/api/sensor':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                dados = json.loads(post_data.decode())
                
                # Valida campos obrigatórios
                sensor_id = dados.get('sensor_id', 'desconhecido')
                temperatura = float(dados.get('temperatura', 0))
                umidade = float(dados.get('umidade', 0))
                poeira = float(dados.get('poeira', 0))
                
                # Armazena no banco
                db.inserir_leitura(sensor_id, temperatura, umidade, poeira)
                
                # Responde sucesso
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                resposta = {'status': 'sucesso', 'mensagem': 'Dados recebidos'}
                self.wfile.write(json.dumps(resposta).encode())
                
            except Exception as e:
                self.send_error(400, f'Erro ao processar dados: {str(e)}')
        else:
            self.send_error(404)
    
    def gerar_dashboard(self):
        """Gera HTML do dashboard com gráficos"""
        leituras = db.obter_ultimas_leituras(50)  # Aumentado para 50 para gráficos melhores
        
        # Prepara dados para os gráficos
        if leituras:
            # Inverte para ordem cronológica
            leituras_ordenadas = list(reversed(leituras))
            
            # Extrai dados para gráficos
            timestamps = [l['timestamp'][11:19] for l in leituras_ordenadas]  # Apenas hora
            temperaturas = [l['temperatura'] for l in leituras_ordenadas]
            umidades = [l['umidade'] for l in leituras_ordenadas]
            poeiras = [l['poeira'] for l in leituras_ordenadas]
            
            # Calcula estatísticas
            temp_media = sum(temperaturas) / len(temperaturas)
            temp_min = min(temperaturas)
            temp_max = max(temperaturas)
            
            umid_media = sum(umidades) / len(umidades)
            umid_min = min(umidades)
            umid_max = max(umidades)
            
            poeira_media = sum(poeiras) / len(poeiras)
            poeira_min = min(poeiras)
            poeira_max = max(poeiras)
        else:
            timestamps = []
            temperaturas = []
            umidades = []
            poeiras = []
            temp_media = temp_min = temp_max = 0
            umid_media = umid_min = umid_max = 0
            poeira_media = poeira_min = poeira_max = 0
        
        # Prepara dados para JavaScript
        import json
        dados_js = json.dumps({
            'timestamps': timestamps,
            'temperaturas': temperaturas,
            'umidades': umidades,
            'poeiras': poeiras
        })
        
        # Tabela com últimas 10 leituras
        linhas_tabela = ""
        for leitura in leituras[:10]:
            linhas_tabela += f"""
            <tr>
                <td>{leitura['timestamp'][:19]}</td>
                <td>{leitura['sensor_id']}</td>
                <td>{leitura['temperatura']:.1f} °C</td>
                <td>{leitura['umidade']:.1f} %</td>
                <td>{leitura['poeira']:.1f} µg/m³</td>
            </tr>
            """
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta http-equiv="refresh" content="10">
            <title>Dashboard - Monitoramento Ambiental</title>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 20px;
                    min-height: 100vh;
                }}
                .header {{
                    text-align: center;
                    color: white;
                    margin-bottom: 30px;
                }}
                .header h1 {{
                    font-size: 32px;
                    font-weight: 600;
                    margin-bottom: 5px;
                }}
                .header p {{
                    font-size: 14px;
                    opacity: 0.9;
                }}
                .container {{
                    max-width: 1400px;
                    margin: 0 auto;
                }}
                .metrics-grid {{
                    display: grid;
                    grid-template-columns: repeat(3, 1fr);
                    gap: 20px;
                    margin-bottom: 30px;
                }}
                .metric-card {{
                    background: white;
                    border-radius: 12px;
                    padding: 20px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }}
                .metric-card h3 {{
                    color: #333;
                    font-size: 14px;
                    font-weight: 600;
                    margin-bottom: 15px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }}
                .metric-stats {{
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 10px;
                }}
                .metric-stats div {{
                    text-align: center;
                }}
                .metric-stats label {{
                    display: block;
                    font-size: 11px;
                    color: #888;
                    margin-bottom: 5px;
                }}
                .metric-stats span {{
                    font-size: 18px;
                    font-weight: 600;
                    color: #333;
                }}
                .graphs-grid {{
                    display: grid;
                    grid-template-columns: repeat(3, 1fr);
                    gap: 20px;
                    margin-bottom: 30px;
                }}
                .graph-card {{
                    background: white;
                    border-radius: 12px;
                    padding: 25px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }}
                .graph-card h3 {{
                    color: #333;
                    font-size: 16px;
                    font-weight: 600;
                    margin-bottom: 20px;
                }}
                .chart-container {{
                    position: relative;
                    height: 250px;
                }}
                .table-card {{
                    background: white;
                    border-radius: 12px;
                    padding: 25px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }}
                .table-card h3 {{
                    color: #333;
                    font-size: 18px;
                    font-weight: 600;
                    margin-bottom: 20px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                }}
                th {{
                    background-color: #f8f9fa;
                    padding: 12px;
                    text-align: left;
                    font-size: 12px;
                    font-weight: 600;
                    color: #666;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    border-bottom: 2px solid #e9ecef;
                }}
                td {{
                    padding: 12px;
                    border-bottom: 1px solid #e9ecef;
                    font-size: 14px;
                    color: #333;
                }}
                tr:hover {{
                    background-color: #f8f9fa;
                }}
                .footer {{
                    text-align: center;
                    color: white;
                    margin-top: 30px;
                    font-size: 13px;
                    opacity: 0.9;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Sistema de Monitoramento Ambiental</h1>
                <p>CIC0236 - Teleinformática e Redes 2 | Atualização automática a cada 10 segundos</p>
            </div>
            
            <div class="container">
                <!-- Cards de Métricas -->
                <div class="metrics-grid">
                    <div class="metric-card">
                        <h3>Temperatura</h3>
                        <div class="metric-stats">
                            <div>
                                <label>Mínima</label>
                                <span>{temp_min:.1f}°C</span>
                            </div>
                            <div>
                                <label>Média</label>
                                <span style="font-size: 24px; color: #667eea;">{temp_media:.1f}°C</span>
                            </div>
                            <div>
                                <label>Máxima</label>
                                <span>{temp_max:.1f}°C</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="metric-card">
                        <h3>Umidade</h3>
                        <div class="metric-stats">
                            <div>
                                <label>Mínima</label>
                                <span>{umid_min:.1f}%</span>
                            </div>
                            <div>
                                <label>Média</label>
                                <span style="font-size: 24px; color: #667eea;">{umid_media:.1f}%</span>
                            </div>
                            <div>
                                <label>Máxima</label>
                                <span>{umid_max:.1f}%</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="metric-card">
                        <h3>Concentração de Poeira</h3>
                        <div class="metric-stats">
                            <div>
                                <label>Mínima</label>
                                <span>{poeira_min:.1f}</span>
                            </div>
                            <div>
                                <label>Média</label>
                                <span style="font-size: 24px; color: #667eea;">{poeira_media:.1f}</span>
                            </div>
                            <div>
                                <label>Máxima</label>
                                <span>{poeira_max:.1f}</span>
                            </div>
                        </div>
                        <p style="font-size: 11px; color: #888; margin-top: 10px; text-align: center;">µg/m³</p>
                    </div>
                </div>
                
                <!-- Gráficos -->
                <div class="graphs-grid">
                    <div class="graph-card">
                        <h3>Temperatura ao Longo do Tempo</h3>
                        <div class="chart-container">
                            <canvas id="chartTemp"></canvas>
                        </div>
                    </div>
                    
                    <div class="graph-card">
                        <h3>Umidade ao Longo do Tempo</h3>
                        <div class="chart-container">
                            <canvas id="chartUmid"></canvas>
                        </div>
                    </div>
                    
                    <div class="graph-card">
                        <h3>Poeira ao Longo do Tempo</h3>
                        <div class="chart-container">
                            <canvas id="chartPoeira"></canvas>
                        </div>
                    </div>
                </div>
                
                <!-- Tabela de Dados -->
                <div class="table-card">
                    <h3>Últimas Leituras Registradas</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Sensor ID</th>
                                <th>Temperatura</th>
                                <th>Umidade</th>
                                <th>Poeira</th>
                            </tr>
                        </thead>
                        <tbody>
                            {linhas_tabela if linhas_tabela else '<tr><td colspan="5" style="text-align:center; color: #999;">Aguardando dados dos sensores...</td></tr>'}
                        </tbody>
                    </table>
                </div>
                
                <div class="footer">
                    <p>Total de leituras armazenadas: {len(leituras)} | Sistema operacional</p>
                </div>
            </div>
            
            <script>
                const dados = {dados_js};
                
                // Configuração comum dos gráficos
                const commonOptions = {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            display: false
                        }}
                    }},
                    scales: {{
                        x: {{
                            display: true,
                            grid: {{
                                display: false
                            }},
                            ticks: {{
                                maxTicksLimit: 8
                            }}
                        }},
                        y: {{
                            display: true,
                            grid: {{
                                color: '#f0f0f0'
                            }}
                        }}
                    }}
                }};
                
                // Gráfico de Temperatura
                new Chart(document.getElementById('chartTemp'), {{
                    type: 'line',
                    data: {{
                        labels: dados.timestamps,
                        datasets: [{{
                            label: 'Temperatura',
                            data: dados.temperaturas,
                            borderColor: '#ff6b6b',
                            backgroundColor: 'rgba(255, 107, 107, 0.1)',
                            borderWidth: 2,
                            tension: 0.4,
                            fill: true
                        }}]
                    }},
                    options: commonOptions
                }});
                
                // Gráfico de Umidade
                new Chart(document.getElementById('chartUmid'), {{
                    type: 'line',
                    data: {{
                        labels: dados.timestamps,
                        datasets: [{{
                            label: 'Umidade',
                            data: dados.umidades,
                            borderColor: '#4ecdc4',
                            backgroundColor: 'rgba(78, 205, 196, 0.1)',
                            borderWidth: 2,
                            tension: 0.4,
                            fill: true
                        }}]
                    }},
                    options: commonOptions
                }});
                
                // Gráfico de Poeira
                new Chart(document.getElementById('chartPoeira'), {{
                    type: 'line',
                    data: {{
                        labels: dados.timestamps,
                        datasets: [{{
                            label: 'Poeira',
                            data: dados.poeiras,
                            borderColor: '#95e1d3',
                            backgroundColor: 'rgba(149, 225, 211, 0.1)',
                            borderWidth: 2,
                            tension: 0.4,
                            fill: true
                        }}]
                    }},
                    options: commonOptions
                }});
            </script>
        </body>
        </html>
        """
        return html
    
    def log_message(self, format, *args):
        """Sobrescreve log padrão para mensagens mais limpas"""
        return

def iniciar_servidor():
    """Inicia o servidor HTTP"""
    with socketserver.TCPServer(("", PORT), MonitoringHandler) as httpd:
        print("="*60)
        print(" SERVIDOR DE MONITORAMENTO INICIADO")
        print("="*60)
        print(f" Porta: {PORT}")
        print(f" Dashboard: http://localhost:{PORT}/dashboard")
        print(f" API: http://localhost:{PORT}/api/leituras")
        print(f" Endpoint sensores: POST http://localhost:{PORT}/api/sensor")
        print("="*60)
        print("Pressione Ctrl+C para parar o servidor")
        print()
        
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n  Servidor encerrado")

if __name__ == '__main__':
    iniciar_servidor()