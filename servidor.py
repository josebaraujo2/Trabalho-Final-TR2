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
    
    def obter_ultimas_leituras(self, limite=20, sensor_id=None):
        """Retorna as últimas N leituras, opcionalmente filtradas por sensor_id"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        if sensor_id and sensor_id != 'TODOS':
            cursor.execute('''
                SELECT timestamp, sensor_id, temperatura, umidade, poeira
                FROM leituras
                WHERE sensor_id = ?
                ORDER BY id DESC
                LIMIT ?
            ''', (sensor_id, limite))
        else:
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

class ReusableTCPServer(socketserver.TCPServer):
    """TCPServer que permite reutilizar endereço (resolve problemas no WSL)"""
    allow_reuse_address = True

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
        
        # API JSON para obter dados com parâmetros de limite e sensor_id
        elif parsed_path.path == '/api/leituras':
            query_params = parse_qs(parsed_path.query)
            limite = int(query_params.get('limite', [50])[0])
            sensor_id = query_params.get('sensor_id', [None])[0]
            
            # Limita entre 1 e 500 para evitar sobrecarga
            limite = max(1, min(limite, 500))
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            leituras = db.obter_ultimas_leituras(limite, sensor_id)
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
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Dashboard - Monitoramento Ambiental</title>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
            <style>
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }
                body {
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    padding: 20px;
                    min-height: 100vh;
                }
                .header {
                    text-align: center;
                    color: white;
                    margin-bottom: 30px;
                }
                .header h1 {
                    font-size: 32px;
                    font-weight: 600;
                    margin-bottom: 5px;
                }
                .header p {
                    font-size: 14px;
                    opacity: 0.9;
                }
                .container {
                    max-width: 1400px;
                    margin: 0 auto;
                }
                .control-panel {
                    background: white;
                    border-radius: 12px;
                    padding: 20px;
                    margin-bottom: 20px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    display: flex;
                    align-items: center;
                    gap: 15px;
                    flex-wrap: wrap;
                }
                .control-panel label {
                    font-weight: 600;
                    color: #333;
                    font-size: 14px;
                }
                .control-panel input,
                .control-panel select {
                    padding: 10px 15px;
                    border: 2px solid #e0e0e0;
                    border-radius: 8px;
                    font-size: 14px;
                    transition: border-color 0.3s;
                }
                .control-panel input {
                    width: 120px;
                }
                .control-panel select {
                    width: 200px;
                    cursor: pointer;
                }
                .control-panel input:focus,
                .control-panel select:focus {
                    outline: none;
                    border-color: #667eea;
                }
                .control-panel button {
                    padding: 10px 25px;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: transform 0.2s, box-shadow 0.2s;
                }
                .control-panel button:hover {
                    transform: translateY(-2px);
                    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
                }
                .control-panel button:active {
                    transform: translateY(0);
                }
                .control-panel .auto-refresh {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    margin-left: auto;
                }
                .control-panel .auto-refresh input[type="checkbox"] {
                    width: auto;
                    cursor: pointer;
                }
                .metrics-grid {
                    display: grid;
                    grid-template-columns: repeat(3, 1fr);
                    gap: 20px;
                    margin-bottom: 30px;
                }
                .metric-card {
                    background: white;
                    border-radius: 12px;
                    padding: 20px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }
                .metric-card h3 {
                    color: #333;
                    font-size: 14px;
                    font-weight: 600;
                    margin-bottom: 15px;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }
                .metric-stats {
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 10px;
                }
                .metric-stats div {
                    text-align: center;
                }
                .metric-stats label {
                    display: block;
                    font-size: 11px;
                    color: #888;
                    margin-bottom: 5px;
                }
                .metric-stats span {
                    font-size: 18px;
                    font-weight: 600;
                    color: #333;
                }
                .graphs-grid {
                    display: grid;
                    grid-template-columns: repeat(3, 1fr);
                    gap: 20px;
                    margin-bottom: 30px;
                }
                .graph-card {
                    background: white;
                    border-radius: 12px;
                    padding: 25px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }
                .graph-card h3 {
                    color: #333;
                    font-size: 16px;
                    font-weight: 600;
                    margin-bottom: 20px;
                }
                .chart-container {
                    position: relative;
                    height: 250px;
                }
                .table-card {
                    background: white;
                    border-radius: 12px;
                    padding: 25px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }
                .table-card h3 {
                    color: #333;
                    font-size: 18px;
                    font-weight: 600;
                    margin-bottom: 20px;
                }
                table {
                    width: 100%;
                    border-collapse: collapse;
                }
                th {
                    background-color: #f8f9fa;
                    padding: 12px;
                    text-align: left;
                    font-size: 12px;
                    font-weight: 600;
                    color: #666;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                    border-bottom: 2px solid #e9ecef;
                }
                td {
                    padding: 12px;
                    border-bottom: 1px solid #e9ecef;
                    font-size: 14px;
                    color: #333;
                }
                tr:hover {
                    background-color: #f8f9fa;
                }
                .footer {
                    text-align: center;
                    color: white;
                    margin-top: 30px;
                    font-size: 13px;
                    opacity: 0.9;
                }
                .loading {
                    display: none;
                    color: #667eea;
                    font-size: 14px;
                    font-weight: 600;
                }
                .loading.active {
                    display: inline-block;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Sistema de Monitoramento Ambiental</h1>
                <p>CIC0236 - Teleinformática e Redes 2</p>
            </div>
            
            <div class="container">
                <!-- Painel de Controle -->
                <div class="control-panel">
                    <label for="sensorSelect">Sensor:</label>
                    <select id="sensorSelect">
                        <option value="TODOS">Todos os Sensores</option>
                        <option value="SALA_SERVIDORES_01">Sala Servidores 01</option>
                        <option value="SALA_SERVIDORES_02">Sala Servidores 02</option>
                        <option value="LABORATORIO_REDES">Laboratório de Redes</option>
                    </select>
                    
                    <label for="numLeituras">Número de leituras:</label>
                    <input type="number" id="numLeituras" value="50" min="1" max="500">
                    
                    <button onclick="atualizarDados()">Atualizar</button>
                    <span class="loading" id="loading">Carregando...</span>
                    
                    <div class="auto-refresh">
                        <input type="checkbox" id="autoRefresh" checked>
                        <label for="autoRefresh">Atualização automática (10s)</label>
                    </div>
                </div>
                
                <!-- Cards de Métricas -->
                <div class="metrics-grid">
                    <div class="metric-card">
                        <h3>Temperatura</h3>
                        <div class="metric-stats">
                            <div>
                                <label>Mínima</label>
                                <span id="tempMin">--</span>
                            </div>
                            <div>
                                <label>Média</label>
                                <span style="font-size: 24px; color: #667eea;" id="tempMedia">--</span>
                            </div>
                            <div>
                                <label>Máxima</label>
                                <span id="tempMax">--</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="metric-card">
                        <h3>Umidade</h3>
                        <div class="metric-stats">
                            <div>
                                <label>Mínima</label>
                                <span id="umidMin">--</span>
                            </div>
                            <div>
                                <label>Média</label>
                                <span style="font-size: 24px; color: #667eea;" id="umidMedia">--</span>
                            </div>
                            <div>
                                <label>Máxima</label>
                                <span id="umidMax">--</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="metric-card">
                        <h3>Concentração de Poeira</h3>
                        <div class="metric-stats">
                            <div>
                                <label>Mínima</label>
                                <span id="poeiraMin">--</span>
                            </div>
                            <div>
                                <label>Média</label>
                                <span style="font-size: 24px; color: #667eea;" id="poeiraMedia">--</span>
                            </div>
                            <div>
                                <label>Máxima</label>
                                <span id="poeiraMax">--</span>
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
                        <tbody id="tabelaLeituras">
                            <tr><td colspan="5" style="text-align:center; color: #999;">Carregando dados...</td></tr>
                        </tbody>
                    </table>
                </div>
                
                <div class="footer">
                    <p>Total de leituras exibidas: <span id="totalLeituras">0</span> | Sistema operacional</p>
                </div>
            </div>
            
            <script>
                let chartTemp, chartUmid, chartPoeira;
                let autoRefreshInterval;
                
                // Configuração comum dos gráficos
                const commonOptions = {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        x: {
                            display: true,
                            grid: {
                                display: false
                            },
                            ticks: {
                                maxTicksLimit: 8
                            }
                        },
                        y: {
                            display: true,
                            grid: {
                                color: '#f0f0f0'
                            }
                        }
                    }
                };
                
                // Inicializa os gráficos
                function inicializarGraficos() {
                    chartTemp = new Chart(document.getElementById('chartTemp'), {
                        type: 'line',
                        data: {
                            labels: [],
                            datasets: [{
                                label: 'Temperatura',
                                data: [],
                                borderColor: '#ff6b6b',
                                backgroundColor: 'rgba(255, 107, 107, 0.1)',
                                borderWidth: 2,
                                tension: 0.4,
                                fill: true
                            }]
                        },
                        options: commonOptions
                    });
                    
                    chartUmid = new Chart(document.getElementById('chartUmid'), {
                        type: 'line',
                        data: {
                            labels: [],
                            datasets: [{
                                label: 'Umidade',
                                data: [],
                                borderColor: '#4ecdc4',
                                backgroundColor: 'rgba(78, 205, 196, 0.1)',
                                borderWidth: 2,
                                tension: 0.4,
                                fill: true
                            }]
                        },
                        options: commonOptions
                    });
                    
                    chartPoeira = new Chart(document.getElementById('chartPoeira'), {
                        type: 'line',
                        data: {
                            labels: [],
                            datasets: [{
                                label: 'Poeira',
                                data: [],
                                borderColor: '#95e1d3',
                                backgroundColor: 'rgba(149, 225, 211, 0.1)',
                                borderWidth: 2,
                                tension: 0.4,
                                fill: true
                            }]
                        },
                        options: commonOptions
                    });
                }
                
                // Atualiza os dados do dashboard
                async function atualizarDados() {
                    const numLeituras = document.getElementById('numLeituras').value;
                    const sensorId = document.getElementById('sensorSelect').value;
                    const loading = document.getElementById('loading');
                    
                    loading.classList.add('active');
                    
                    try {
                        let url = `/api/leituras?limite=${numLeituras}`;
                        if (sensorId !== 'TODOS') {
                            url += `&sensor_id=${sensorId}`;
                        }
                        
                        const response = await fetch(url);
                        const leituras = await response.json();
                        
                        if (leituras.length === 0) {
                            document.getElementById('tabelaLeituras').innerHTML = 
                                '<tr><td colspan="5" style="text-align:center; color: #999;">Aguardando dados dos sensores...</td></tr>';
                            return;
                        }
                        
                        // Inverte para ordem cronológica
                        const leiturasOrdenadas = leituras.reverse();
                        
                        // Extrai dados
                        const timestamps = leiturasOrdenadas.map(l => l.timestamp.substring(11, 19));
                        const temperaturas = leiturasOrdenadas.map(l => l.temperatura);
                        const umidades = leiturasOrdenadas.map(l => l.umidade);
                        const poeiras = leiturasOrdenadas.map(l => l.poeira);
                        
                        // Calcula estatísticas
                        const tempMedia = (temperaturas.reduce((a, b) => a + b, 0) / temperaturas.length).toFixed(1);
                        const tempMin = Math.min(...temperaturas).toFixed(1);
                        const tempMax = Math.max(...temperaturas).toFixed(1);
                        
                        const umidMedia = (umidades.reduce((a, b) => a + b, 0) / umidades.length).toFixed(1);
                        const umidMin = Math.min(...umidades).toFixed(1);
                        const umidMax = Math.max(...umidades).toFixed(1);
                        
                        const poeiraMedia = (poeiras.reduce((a, b) => a + b, 0) / poeiras.length).toFixed(1);
                        const poeiraMin = Math.min(...poeiras).toFixed(1);
                        const poeiraMax = Math.max(...poeiras).toFixed(1);
                        
                        // Atualiza métricas
                        document.getElementById('tempMin').textContent = tempMin + '°C';
                        document.getElementById('tempMedia').textContent = tempMedia + '°C';
                        document.getElementById('tempMax').textContent = tempMax + '°C';
                        
                        document.getElementById('umidMin').textContent = umidMin + '%';
                        document.getElementById('umidMedia').textContent = umidMedia + '%';
                        document.getElementById('umidMax').textContent = umidMax + '%';
                        
                        document.getElementById('poeiraMin').textContent = poeiraMin;
                        document.getElementById('poeiraMedia').textContent = poeiraMedia;
                        document.getElementById('poeiraMax').textContent = poeiraMax;
                        
                        // Atualiza gráficos
                        chartTemp.data.labels = timestamps;
                        chartTemp.data.datasets[0].data = temperaturas;
                        chartTemp.update();
                        
                        chartUmid.data.labels = timestamps;
                        chartUmid.data.datasets[0].data = umidades;
                        chartUmid.update();
                        
                        chartPoeira.data.labels = timestamps;
                        chartPoeira.data.datasets[0].data = poeiras;
                        chartPoeira.update();
                        
                        // Atualiza tabela (primeiras 10)
                        const tbody = document.getElementById('tabelaLeituras');
                        tbody.innerHTML = '';
                        leituras.reverse().slice(0, 10).forEach(leitura => {
                            const row = `
                                <tr>
                                    <td>${leitura.timestamp.substring(0, 19)}</td>
                                    <td>${leitura.sensor_id}</td>
                                    <td>${leitura.temperatura.toFixed(1)} °C</td>
                                    <td>${leitura.umidade.toFixed(1)} %</td>
                                    <td>${leitura.poeira.toFixed(1)} µg/m³</td>
                                </tr>
                            `;
                            tbody.innerHTML += row;
                        });
                        
                        document.getElementById('totalLeituras').textContent = leituras.length;
                        
                    } catch (error) {
                        console.error('Erro ao carregar dados:', error);
                    } finally {
                        loading.classList.remove('active');
                    }
                }
                
                // Configurar atualização automática
                function configurarAutoRefresh() {
                    if (autoRefreshInterval) {
                        clearInterval(autoRefreshInterval);
                    }
                    
                    if (document.getElementById('autoRefresh').checked) {
                        autoRefreshInterval = setInterval(atualizarDados, 10000);
                    }
                }
                
                // Event listeners
                document.getElementById('autoRefresh').addEventListener('change', configurarAutoRefresh);
                document.getElementById('sensorSelect').addEventListener('change', atualizarDados);
                document.getElementById('numLeituras').addEventListener('keypress', (e) => {
                    if (e.key === 'Enter') {
                        atualizarDados();
                    }
                });
                
                // Inicialização
                inicializarGraficos();
                atualizarDados();
                configurarAutoRefresh();
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
    with ReusableTCPServer(("", PORT), MonitoringHandler) as httpd:
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