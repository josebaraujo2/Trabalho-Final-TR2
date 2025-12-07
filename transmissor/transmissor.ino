/*
 * ESP32 LoRa Node — Ultra Low Power
 * Adicionado: tempos de cada estado, tempo desde último envio, tempos acumulados,
 * correção do overflow no primeiro boot.
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

#define TEMPO_SLEEP 1
#define LIMITE_TEMP 0.5
#define LIMITE_UMI 2.0
#define LIMITE_POEIRA 5.0

// ===== SIMULAÇÃO =====
float temp_base = 28.0;
float umid_base = 45.0;

// ===== MEMÓRIA RTC =====
RTC_DATA_ATTR float lastTemp = -1000;
RTC_DATA_ATTR float lastUmi = -1000;
RTC_DATA_ATTR float lastPoeira = -1000;
RTC_DATA_ATTR int skipSendCount = 0;

RTC_DATA_ATTR uint64_t totalUptimeMicros = 0;   // tempo acumulado entre ciclos
RTC_DATA_ATTR uint64_t lastSendTimestamp = 0;   // timestamp global

// ===== Função para medir tempos =====
uint64_t now() { return esp_timer_get_time(); }

// ===== Deep Sleep =====
void dormir(uint64_t startMicros)
{
  uint64_t activeMicros = now() - startMicros;

  totalUptimeMicros += activeMicros + (TEMPO_SLEEP * 1000000ULL);

  Serial.print("⏱ Tempo ativo do ciclo: ");
  Serial.print(activeMicros / 1000.0, 2);
  Serial.println(" ms");

  Serial.print("⏱ Tempo total acumulado: ");
  Serial.print(totalUptimeMicros / 1000000.0, 2);
  Serial.println(" s");

  Serial.println("😴 Entrando em deep sleep...");
  delay(150);

  esp_sleep_enable_timer_wakeup(TEMPO_SLEEP * 1000000ULL);
  esp_deep_sleep_start();
}

void setup() {
  uint64_t startMicros = now();

  setCpuFrequencyMhz(80);
  Serial.begin(115200);
  delay(150);

  Serial.println("\n===== ULTRA LOW POWER LoRa NODE =====");
  Serial.println("Wakeup! Medindo...\n");

  // ===== Tempo desde último envio (corrigido) =====
  if (lastSendTimestamp == 0)
  {
    Serial.println("⏳ Primeiro boot → nenhum envio anterior.");
  }
  else
  {
    uint64_t diff = totalUptimeMicros - lastSendTimestamp;

    Serial.print("⏳ Tempo desde último envio: ");
    Serial.print(diff / 1000000.0, 2);
    Serial.println(" s");
  }

  // ===== Estado 1 — Medição =====
  uint64_t t0 = now();

  randomSeed(now());

  float temperatura = temp_base + random(-50, 50) / 10.0;
  float umidade = umid_base + random(-100, 100) / 10.0;
  float poeira = random(100, 500) / 10.0;
  umidade = constrain(umidade, 0, 100);

  Serial.print("⏱ Tempo de medição: ");
  Serial.print((now() - t0) / 1000.0, 2);
  Serial.println(" ms");

  // ===== Estado 2 — Verificação =====
  uint64_t t1 = now();

  bool mudouTemp = abs(temperatura - lastTemp) >= LIMITE_TEMP;
  bool mudouUmi = abs(umidade - lastUmi) >= LIMITE_UMI;
  bool mudouPoeira = abs(poeira - lastPoeira) >= LIMITE_POEIRA;
  bool mudouAlgo = mudouTemp || mudouUmi || mudouPoeira;

  Serial.print("⏱ Tempo verificação: ");
  Serial.print((now() - t1) / 1000.0, 2);
  Serial.println(" ms");

  // ===== Estado 3 — Skip silencioso =====
  if (!mudouAlgo)
  {
    skipSendCount++;

    Serial.print("→ Sem mudanças (");
    Serial.print(skipSendCount);
    Serial.println(" ciclos).");

    if (skipSendCount < 60)
    {
      dormir(startMicros);
      return;
    }

    Serial.println("⚠ Forçando envio após 60 ciclos.");
  }

  skipSendCount = 0;

  lastTemp = temperatura;
  lastUmi = umidade;
  lastPoeira = poeira;

  // ===== Estado 4 — Inicialização LoRa =====
  uint64_t t2 = now();

  SPI.begin(SCK, MISO, MOSI, SS);
  LoRa.setPins(SS, RST, DIO0);

  if (!LoRa.begin(FREQUENCY)) {
    Serial.println("❌ Erro LoRa!");
    dormir(startMicros);
  }

  LoRa.setSpreadingFactor(12);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(5);
  LoRa.setTxPower(20);

  Serial.print("⏱ Tempo init LoRa: ");
  Serial.print((now() - t2) / 1000.0, 2);
  Serial.println(" ms");

  // ===== Estado 5 — Envio LoRa =====
  String json = "{";
  json += "\"sensor_id\":\"" + String(SENSOR_ID) + "\",";
  json += "\"temperatura\":" + String(temperatura, 2) + ",";
  json += "\"umidade\":" + String(umidade, 2) + ",";
  json += "\"poeira\":" + String(poeira, 2);
  json += "}";

  Serial.println("📡 Enviando pacote LoRa:");
  Serial.println(json);

  uint64_t txStart = now();

  LoRa.beginPacket();
  LoRa.print(json);
  LoRa.endPacket();

  uint64_t txTime = now() - txStart;

  Serial.print("⏱ Tempo TX LoRa: ");
  Serial.print(txTime / 1000.0, 2);
  Serial.println(" ms");

  // Atualiza timestamp global
  lastSendTimestamp = totalUptimeMicros;

  // Dormir
  dormir(startMicros);
}

void loop() {}