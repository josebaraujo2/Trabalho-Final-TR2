/*
 * ESP32 CLIENTE LoRa - TRANSMISSOR
 * Envia: temperatura, umidade, poeira
 */

#include <SPI.h>
#include <LoRa.h>

// ===== CONFIGURAÇÕES LORA =====
#define SCK 18
#define MISO 19
#define MOSI 23
#define SS 5
#define RST 14
#define DIO0 26
#define FREQUENCY 915E6  // 915 MHz (Brasil)

// ===== CONFIGURAÇÕES SENSOR =====
#define SENSOR_ID "SALA_SERVIDORES_01"  
#define INTERVALO_ENVIO 3000  // 3 segundos 

// ===== BASES PARA SIMULAÇÃO =====
float temp_base = 28.0;   // Temperatura base
float umid_base = 45.0;   // Umidade base

// ===== CONTROLE =====
unsigned long ultimo_envio = 0;
#define LED 2

void setup() {
  Serial.begin(115200);
  while (!Serial);
  
  pinMode(LED, OUTPUT);
  
  Serial.println("\n╔════════════════════════════════════╗");
  Serial.println("║  ESP32 CLIENTE LoRa - TRANSMISSOR ║");
  Serial.println("╚════════════════════════════════════╝");
  Serial.print("Sensor ID: ");
  Serial.println(SENSOR_ID);
  
  // Inicializa SPI e LoRa
  SPI.begin(SCK, MISO, MOSI, SS);
  LoRa.setPins(SS, RST, DIO0);
  
  if (!LoRa.begin(FREQUENCY)) {
    Serial.println("❌ ERRO: LoRa falhou!");
    while (1) {
      digitalWrite(LED, !digitalRead(LED));
      delay(200);
    }
  }
  
  // Configurações LoRa (máximo alcance)
  LoRa.setSpreadingFactor(12);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(5);
  LoRa.setTxPower(20);
  
  Serial.println("✓ LoRa inicializado!");
  Serial.print("✓ Frequência: ");
  Serial.print(FREQUENCY / 1E6);
  Serial.println(" MHz");
  Serial.print("✓ Intervalo de envio: ");
  Serial.print(INTERVALO_ENVIO / 1000);
  Serial.println("s");
  Serial.println("\n Iniciando transmissão...\n");
}

void loop() {
  unsigned long agora = millis();
  
  if (agora - ultimo_envio >= INTERVALO_ENVIO) {
    ultimo_envio = agora;
    enviarLeitura();
  }
  
  delay(100);
}

void enviarLeitura() {
  // ===== GERA DADOS SIMULADOS =====
  float temperatura = temp_base + random(-50, 50) / 10.0;  // ±5°C
  float umidade = umid_base + random(-100, 100) / 10.0;    // ±10%
  float poeira = random(100, 500) / 10.0;                  // 10-50 µg/m³
  
  // Limita umidade entre 0-100%
  umidade = constrain(umidade, 0, 100);
  
  // ===== CRIA JSON  =====
  String json = "{";
  json += "\"sensor_id\":\"" + String(SENSOR_ID) + "\",";
  json += "\"temperatura\":" + String(temperatura, 2) + ",";
  json += "\"umidade\":" + String(umidade, 2) + ",";
  json += "\"poeira\":" + String(poeira, 2);
  json += "}";
  
  // ===== TRANSMITE VIA LORA =====
  Serial.println("📡 Enviando via LoRa:");
  Serial.println("   " + json);
  
  digitalWrite(LED, HIGH);
  
  LoRa.beginPacket();
  LoRa.print(json);
  LoRa.endPacket();
  
  digitalWrite(LED, LOW);
  
  Serial.print("✓ Transmitido! [T:");
  Serial.print(temperatura, 1);
  Serial.print("°C U:");
  Serial.print(umidade, 1);
  Serial.print("% P:");
  Serial.print(poeira, 1);
  Serial.println("µg/m³]\n");
}