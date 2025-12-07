/*
 * ESP32 GATEWAY LoRa - RECEPTOR
 * Recebe dados via LoRa e envia para PC via Serial
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
#define FREQUENCY 915E6

// ===== LED DE STATUS =====
#define LED 2

void setup() {
  Serial.begin(115200);
  while (!Serial);
  
  pinMode(LED, OUTPUT);
  
  Serial.println("\n╔════════════════════════════════════╗");
  Serial.println("║  ESP32 GATEWAY LoRa - RECEPTOR    ║");
  Serial.println("╚════════════════════════════════════╝");
  
  // Inicializa SPI e LoRa
  SPI.begin(SCK, MISO, MOSI, SS);
  LoRa.setPins(SS, RST, DIO0);
  
  if (!LoRa.begin(FREQUENCY)) {
    Serial.println("ERROR:LoRa_init_failed");
    while (1) {
      digitalWrite(LED, !digitalRead(LED));
      delay(200);
    }
  }
  
  // Configurações LoRa (iguais ao cliente)
  LoRa.setSpreadingFactor(12);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(5);
  
  Serial.println("✓ LoRa inicializado!");
  Serial.print("✓ Frequência: ");
  Serial.print(FREQUENCY / 1E6);
  Serial.println(" MHz");
  Serial.println("\n Aguardando pacotes LoRa...\n");
  Serial.println("READY:Gateway_Online");
}

void loop() {
  int tamanho_pacote = LoRa.parsePacket();
  
  if (tamanho_pacote) {
    receberPacote();
  }
  
  delay(10);
}

void receberPacote() {
  digitalWrite(LED, HIGH);
  
  // ===== LÊ PACOTE LORA =====
  String dados_recebidos = "";
  
  while (LoRa.available()) {
    dados_recebidos += (char)LoRa.read();
  }
  
  // ===== OBTÉM METADADOS =====
  int rssi = LoRa.packetRssi();
  float snr = LoRa.packetSnr();
  
  // ===== ADICIONA RSSI E SNR AO JSON =====
  // Remove o } final
  dados_recebidos.trim();
  if (dados_recebidos.endsWith("}")) {
    dados_recebidos.remove(dados_recebidos.length() - 1);
  }
  
  // Adiciona metadados
  dados_recebidos += ",\"rssi\":" + String(rssi);
  dados_recebidos += ",\"snr\":" + String(snr, 1);
  dados_recebidos += "}";
  
  // ===== ENVIA PARA PYTHON VIA SERIAL =====
  // Protocolo: DATA:{json completo}
  Serial.print("DATA:");
  Serial.println(dados_recebidos);
  
  digitalWrite(LED, LOW);
}