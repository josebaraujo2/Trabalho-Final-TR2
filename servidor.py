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
        """Gera HTML do dashboard com gráficos, timeframe selector e alertas"""
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
                
                .timeframe-selector {
                    background: white;
                    border-radius: 12px;
                    padding: 15px 20px;
                    margin-bottom: 20px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    display: flex;
                    align-items: center;
                    gap: 10px;
                }
                .timeframe-selector label {
                    font-weight: 600;
                    color: #333;
                    font-size: 14px;
                    margin-right: 10px;
                }
                .timeframe-btn {
                    padding: 8px 20px;
                    border: 2px solid #e0e0e0;
                    background: white;
                    border-radius: 8px;
                    font-size: 13px;
                    font-weight: 600;
                    cursor: pointer;
                    transition: all 0.3s;
                    color: #666;
                }
                .timeframe-btn:hover {
                    border-color: #667eea;
                    color: #667eea;
                }
                .timeframe-btn.active {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border-color: transparent;
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
                    transition: all 0.3s;
                    position: relative;
                    overflow: hidden;
                }
                .metric-card::before {
                    content: '';
                    position: absolute;
                    top: 0;
                    left: 0;
                    right: 0;
                    height: 4px;
                    background: #667eea;
                    transition: all 0.3s;
                }
                .metric-card.alert-normal::before {
                    background: #10b981;
                }
                .metric-card.alert-warning::before {
                    background: #f59e0b;
                    height: 6px;
                }
                .metric-card.alert-danger::before {
                    background: #ef4444;
                    height: 8px;
                }
                .metric-card.alert-warning {
                    background: #fffbeb;
                    border: 2px solid #fbbf24;
                }
                .metric-card.alert-danger {
                    background: #fef2f2;
                    border: 2px solid #ef4444;
                    animation: pulse 2s infinite;
                }
                @keyframes pulse {
                    0%, 100% { box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
                    50% { box-shadow: 0 4px 20px rgba(239, 68, 68, 0.4); }
                }
                
                .alert-badge {
                    position: absolute;
                    top: 15px;
                    right: 15px;
                    padding: 4px 10px;
                    border-radius: 12px;
                    font-size: 11px;
                    font-weight: 700;
                    text-transform: uppercase;
                    letter-spacing: 0.5px;
                }
                .alert-badge.normal {
                    background: #d1fae5;
                    color: #065f46;
                }
                .alert-badge.warning {
                    background: #fef3c7;
                    color: #92400e;
                }
                .alert-badge.danger {
                    background: #fee2e2;
                    color: #991b1b;
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
                <div class="timeframe-selector">
                    <label>📊 Período:</label>
                    <button class="timeframe-btn active" onclick="setTimeframe(10)">Últimos 10</button>
                    <button class="timeframe-btn" onclick="setTimeframe(50)">Últimos 50</button>
                    <button class="timeframe-btn" onclick="setTimeframe(100)">Últimos 100</button>
                    <button class="timeframe-btn" onclick="setTimeframe(500)">Todos</button>
                </div>
                
                <!-- Painel de Controle -->
                <div class="control-panel">
                    <label for="sensorSelect">Sensor:</label>
                    <select id="sensorSelect">
                        <option value="TODOS">Todos os Sensores</option>
                        <option value="SALA_SERVIDORES_01">Sala Servidores 01</option>
                        <option value="SALA_SERVIDORES_02">Sala Servidores 02</option>
                        <option value="LABORATORIO_REDES">Laboratório de Redes</option>
                    </select>
                    
                    <button onclick="atualizarDados()">Atualizar</button>
                    <span class="loading" id="loading">Carregando...</span>
                    
                    <div class="auto-refresh">
                        <input type="checkbox" id="autoRefresh" checked>
                        <label for="autoRefresh">Atualização automática (10s)</label>
                    </div>
                </div>
                
                <!-- Cards de Métricas com Alertas -->
                <div class="metrics-grid">
                    <div class="metric-card" id="cardTemp">
                        <span class="alert-badge normal" id="badgeTemp">NORMAL</span>
                        <h3>🌡️ Temperatura</h3>
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
                    
                    <div class="metric-card" id="cardUmid">
                        <span class="alert-badge normal" id="badgeUmid">NORMAL</span>
                        <h3>💧 Umidade</h3>
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
                    
                    <div class="metric-card" id="cardPoeira">
                        <span class="alert-badge normal" id="badgePoeira">NORMAL</span>
                        <h3>💨 Concentração de Poeira</h3>
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
                let currentTimeframe = 10;
                let autoRefreshInterval;

                const ALERT_THRESHOLDS = {
                    temperatura: { min: 18, max: 25, warning_min: 20, warning_max: 23 },
                    umidade: { min: 30, max: 70, warning_min: 35, warning_max: 65 },
                    poeira: { max: 50, warning_max: 40 }
                };

                const ALERT_STATE = {
                    temperatura: { history: [], persist: 0 },
                    umidade:     { history: [], persist: 0 },
                    poeira:      { history: [], persist: 0 }
                };

                const HISTORY_LENGTH = 8;          // quantas médias recentes guardar
                const PERSISTENCIA_LIMITE = 3;     // quantas leituras seguidas em alerta

                function setTimeframe(num, el) {
                    currentTimeframe = num;

                    document.querySelectorAll(".timeframe-btn").forEach(btn => {
                        btn.classList.remove("active");
                    });

                    if (el) {
                        el.classList.add("active");
                    }

                    atualizarDados();
                }

                // ---- Funções auxiliares de análise ----
                function registrarValor(tipo, valor) {
                    const state = ALERT_STATE[tipo];
                    state.history.push(valor);
                    if (state.history.length > HISTORY_LENGTH) {
                        state.history.shift(); // mantém só os últimos N
                    }
                }

                function calcularTendencia(tipo) {
                    const h = ALERT_STATE[tipo].history;
                    if (h.length < 4) return 0; // pouco dado, ignora

                    let subindo = 0;
                    for (let i = 1; i < h.length; i++) {
                        if (h[i] > h[i - 1]) subindo++;
                    }

                    // se ~70% das médias estão subindo → tendência de alta
                    return subindo >= Math.floor(h.length * 0.7) ? 1 : 0;
                }

                function detectarSpike(tipo, multiplicador = 1.3) {
                    const h = ALERT_STATE[tipo].history;
                    if (h.length < 2) return false;

                    const penultimo = h[h.length - 2];
                    const ultimo = h[h.length - 1];

                    // evita divisão por zero / comparação furada
                    if (penultimo === 0) return false;

                    return ultimo > penultimo * multiplicador;
                }

                function verificarAlertas(valor, tipo) {
                    const threshold = ALERT_THRESHOLDS[tipo];
                    const state = ALERT_STATE[tipo];

                    // registra histórico desta métrica
                    registrarValor(tipo, valor);

                    // thresholds "hard" e "soft" em cima da média atual
                    let foraHard, foraSoft;

                    if (tipo === "poeira") {
                        foraHard = valor > threshold.max;
                        foraSoft = valor > threshold.warning_max;
                    } else {
                        foraHard = valor < threshold.min || valor > threshold.max;
                        foraSoft = valor < threshold.warning_min || valor > threshold.warning_max;
                    }

                    // persistência (quantas médias seguidas fora)
                    if (foraHard || foraSoft) state.persist++;
                    else state.persist = 0;

                    const persistente = state.persist >= PERSISTENCIA_LIMITE;
                    const tendenciaAlta = calcularTendencia(tipo);
                    const spike = detectarSpike(tipo);

                    // score de risco
                    let risco = 0;
                    if (foraHard) risco += 3;
                    if (foraSoft) risco += 1;
                    if (persistente) risco += 2;
                    if (tendenciaAlta === 1) risco += 1;
                    if (spike) risco += 2;

                    if (risco >= 5) return "danger";
                    if (risco >= 2) return "warning";
                    return "normal";
                }

                function atualizarCardAlerta(cardId, badgeId, nivel) {
                    const card = document.getElementById(cardId);
                    const badge = document.getElementById(badgeId);

                    card.className = "metric-card alert-" + nivel;
                    badge.className = "alert-badge " + nivel;

                    const textos = {
                        normal: "NORMAL",
                        warning: "⚠️ ATENÇÃO",
                        danger: "🚨 CRÍTICO"
                    };

                    badge.textContent = textos[nivel];
                }

                // Config comum dos gráficos 
                const commonOptions = {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: {
                            display: true,
                            grid: { display: false },
                            ticks: { maxTicksLimit: 8 }
                        },
                        y: {
                            display: true,
                            grid: { color: "#f0f0f0" }
                        }
                    }
                };

                function inicializarGraficos() {
                    chartTemp = new Chart(document.getElementById("chartTemp"), {
                        type: "line",
                        data: {
                            labels: [],
                            datasets: [{
                                label: "Temperatura",
                                data: [],
                                borderColor: "#ff6b6b",
                                backgroundColor: "rgba(255, 107, 107, 0.1)",
                                borderWidth: 2,
                                tension: 0.4,
                                fill: true
                            }]
                        },
                        options: commonOptions
                    });

                    chartUmid = new Chart(document.getElementById("chartUmid"), {
                        type: "line",
                        data: {
                            labels: [],
                            datasets: [{
                                label: "Umidade",
                                data: [],
                                borderColor: "#4ecdc4",
                                backgroundColor: "rgba(78, 205, 196, 0.1)",
                                borderWidth: 2,
                                tension: 0.4,
                                fill: true
                            }]
                        },
                        options: commonOptions
                    });

                    chartPoeira = new Chart(document.getElementById("chartPoeira"), {
                        type: "line",
                        data: {
                            labels: [],
                            datasets: [{
                                label: "Poeira",
                                data: [],
                                borderColor: "#95e1d3",
                                backgroundColor: "rgba(149, 225, 211, 0.1)",
                                borderWidth: 2,
                                tension: 0.4,
                                fill: true
                            }]
                        },
                        options: commonOptions
                    });
                }

                // Atualiza dados do dashboard
                async function atualizarDados() {
                    const sensor = document.getElementById("sensorSelect").value;

                    let url = `/api/leituras?limite=${currentTimeframe}`;
                    if (sensor !== "TODOS") {
                        url += `&sensor_id=${sensor}`;
                    }

                    try {
                        const resp = await fetch(url);
                        const leituras = await resp.json();

                        if (!Array.isArray(leituras) || leituras.length === 0) {
                            const tbody = document.getElementById("tabelaLeituras");
                            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:#999;">Aguardando dados...</td></tr>';
                            return;
                        }

                        // ordem cronológica
                        const dados = leituras.slice().reverse();

                        const timestamps = dados.map(l => l.timestamp.substring(11, 19));
                        const temperaturas = dados.map(l => l.temperatura);
                        const umidades = dados.map(l => l.umidade);
                        const poeiras = dados.map(l => l.poeira);

                        // estatísticas
                        const tempMin = Math.min(...temperaturas);
                        const tempMax = Math.max(...temperaturas);
                        const tempMedia = temperaturas.reduce((a, b) => a + b, 0) / temperaturas.length;

                        const umidMin = Math.min(...umidades);
                        const umidMax = Math.max(...umidades);
                        const umidMedia = umidades.reduce((a, b) => a + b, 0) / umidades.length;

                        const poeiraMin = Math.min(...poeiras);
                        const poeiraMax = Math.max(...poeiras);
                        const poeiraMedia = poeiras.reduce((a, b) => a + b, 0) / poeiras.length;

                        // atualiza cards
                        document.getElementById("tempMin").textContent = tempMin.toFixed(1);
                        document.getElementById("tempMedia").textContent = tempMedia.toFixed(1);
                        document.getElementById("tempMax").textContent = tempMax.toFixed(1);

                        document.getElementById("umidMin").textContent = umidMin.toFixed(1);
                        document.getElementById("umidMedia").textContent = umidMedia.toFixed(1);
                        document.getElementById("umidMax").textContent = umidMax.toFixed(1);

                        document.getElementById("poeiraMin").textContent = poeiraMin.toFixed(1);
                        document.getElementById("poeiraMedia").textContent = poeiraMedia.toFixed(1);
                        document.getElementById("poeiraMax").textContent = poeiraMax.toFixed(1);

                        // ALERTAS: agora usando a MÉDIA de cada métrica (igual antes)
                        const alertaTemp = verificarAlertas(tempMedia, "temperatura");
                        const alertaUmid = verificarAlertas(umidMedia, "umidade");
                        const alertaPoeira = verificarAlertas(poeiraMedia, "poeira");

                        atualizarCardAlerta("cardTemp", "badgeTemp", alertaTemp);
                        atualizarCardAlerta("cardUmid", "badgeUmid", alertaUmid);
                        atualizarCardAlerta("cardPoeira", "badgePoeira", alertaPoeira);

                        // gráficos
                        chartTemp.data.labels = timestamps;
                        chartTemp.data.datasets[0].data = temperaturas;
                        chartTemp.update();

                        chartUmid.data.labels = timestamps;
                        chartUmid.data.datasets[0].data = umidades;
                        chartUmid.update();

                        chartPoeira.data.labels = timestamps;
                        chartPoeira.data.datasets[0].data = poeiras;
                        chartPoeira.update();

                        // tabela (últimas 10)
                        const tbody = document.getElementById("tabelaLeituras");
                        tbody.innerHTML = "";

                        dados.slice(-10).reverse().forEach(l => {
                            tbody.innerHTML += `
                                <tr>
                                    <td>${l.timestamp.substring(0, 19)}</td>
                                    <td>${l.sensor_id}</td>
                                    <td>${l.temperatura.toFixed(1)} °C</td>
                                    <td>${l.umidade.toFixed(1)} %</td>
                                    <td>${l.poeira.toFixed(1)} µg/m³</td>
                                </tr>
                            `;
                        });

                    } catch (e) {
                        console.error("Erro ao carregar dados:", e);
                    }
                }

                // auto refresh
                function configurarAutoRefresh() {
                    if (autoRefreshInterval) {
                        clearInterval(autoRefreshInterval);
                    }

                    if (document.getElementById("autoRefresh").checked) {
                        autoRefreshInterval = setInterval(atualizarDados, 10000);
                    }
                }

                document.getElementById("autoRefresh").addEventListener("change", configurarAutoRefresh);
                document.getElementById("sensorSelect").addEventListener("change", atualizarDados);

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