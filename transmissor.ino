/*
 * ESP32 LoRa Node — Ultra Low Power
 * Acorda → mede → envia se mudou → envia a cada 60 ciclos sem mudança → deep sleep
 */

#include <SPI.h>
#include <LoRa.h>
#include "esp_sleep.h"

// ===== PINOS LORA =====
#define SCK 18
#define MISO 19
#define MOSI 23
#define SS 5
#define RST 14
#define DIO0 26
#define FREQUENCY 915E6

// ===== CONFIGURAÇÕES =====
#define SENSOR_ID "SALA_SERVIDORES_01"

#define TEMPO_SLEEP 30           // Segundos de deep sleep
#define LIMITE_TEMP 0.5          // Envia se variar ±0.5°C
#define LIMITE_UMI 2.0           // Envia se variar ±2%
#define LIMITE_POEIRA 5.0        // Envia se variar ±5 µg/m³

// ===== SIMULAÇÃO =====
float temp_base = 28.0;
float umid_base = 45.0;

// ===== MEMÓRIA RTC (persiste entre deep sleep) =====
RTC_DATA_ATTR float lastTemp = -1000;
RTC_DATA_ATTR float lastUmi = -1000;
RTC_DATA_ATTR float lastPoeira = -1000;
RTC_DATA_ATTR int skipSendCount = 0;

// ===== Deep Sleep =====
void dormir() {
  Serial.println("😴 Entrando em deep sleep...");
  delay(100);

  esp_sleep_enable_timer_wakeup(TEMPO_SLEEP * 1000000ULL);
  esp_deep_sleep_start();
}

void setup() {
  setCpuFrequencyMhz(80);
  Serial.begin(115200);
  delay(200);

  Serial.println("\n===== ULTRA LOW POWER LoRa NODE =====");
  Serial.println("Wakeup! Medindo...\n");

  // Garantir aleatoriedade na simulação:
  randomSeed(esp_timer_get_time());

  // ===== Simula sensores =====
  float temperatura = temp_base + random(-50, 50) / 10.0;
  float umidade = umid_base + random(-100, 100) / 10.0;
  float poeira = random(100, 500) / 10.0;

  umidade = constrain(umidade, 0, 100);

  // ===== Detecta mudanças =====
  bool mudouTemp = abs(temperatura - lastTemp) >= LIMITE_TEMP;
  bool mudouUmi = abs(umidade - lastUmi) >= LIMITE_UMI;
  bool mudouPoeira = abs(poeira - lastPoeira) >= LIMITE_POEIRA;
  bool mudouAlgo = mudouTemp || mudouUmi || mudouPoeira;

  // ===== Caso NÃO tenha mudado nada =====
  if (!mudouAlgo) {
    skipSendCount++;

    Serial.print("→ Sem mudanças significativas. Ciclos silenciosos = ");
    Serial.println(skipSendCount);

    // Se ainda não completou 60 ciclos → dorme SEM enviar
    if (skipSendCount < 60) {
      dormir();
      return;
    }

    Serial.println("⚠ 60 ciclos sem envio — envio forçado ativado!");
  }

  // ===== Aqui: mudouAlgo == true OU skipSendCount == 60 =====
  skipSendCount = 0;  // Reseta o contador

  // Atualiza valores persistentes
  lastTemp = temperatura;
  lastUmi = umidade;
  lastPoeira = poeira;

  // ===== Inicializa LoRa =====
  SPI.begin(SCK, MISO, MOSI, SS);
  LoRa.setPins(SS, RST, DIO0);

  if (!LoRa.begin(FREQUENCY)) {
    Serial.println("❌ Erro LoRa!");
    dormir();
  }

  // LoRa otimizado para baixo consumo
  LoRa.setSpreadingFactor(10);       // mais rápido que SF12
  LoRa.setSignalBandwidth(250E3);    // tempo no ar menor
  LoRa.setCodingRate4(5);
  LoRa.setTxPower(14);               // potência reduzida
  LoRa.enableCrc();

  // ===== Monta JSON =====
  String json = "{";
  json += "\"sensor_id\":\"" + String(SENSOR_ID) + "\",";
  json += "\"temperatura\":" + String(temperatura, 2) + ",";
  json += "\"umidade\":" + String(umidade, 2) + ",";
  json += "\"poeira\":" + String(poeira, 2);
  json += "}";

  Serial.println("📡 Enviando pacote LoRa:");
  Serial.println(json);

  LoRa.beginPacket();
  LoRa.print(json);
  LoRa.endPacket();

  Serial.println("✓ Enviado com sucesso!");

  // Dorme após transmitir
  dormir();
}

void loop() {
  // Nunca é executado — o ESP32 usa ciclos de deep sleep
}
