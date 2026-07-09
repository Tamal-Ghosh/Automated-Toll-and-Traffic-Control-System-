#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include "HX711.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <ESP32Servo.h>

#define SERVO_PIN 32
#define TRIG_PIN  27
#define ECHO_PIN  33
#define DT_PIN    25
#define SCK_PIN   26

const char* ssid           = "Hello";
const char* password       = "11111111";
const char* carDetectedUrl = "http://10.75.189.48:5000/api/car-detected";
const char* statusUrl      = "http://10.75.189.48:5000/api/latest-scan";

LiquidCrystal_I2C lcd(0x27, 16, 2);
HX711 scale;
Servo myServo;

bool barrierOpen             = true;
unsigned long lastCheckTime  = 0;
unsigned long gateClosedAt   = 0;
unsigned long lastWiFiCheck  = 0;
unsigned long lastWeightTime = 0;

const float WEIGHT_OFFSET = 112.0;
float calibration_factor  = 228000;

float getDistance() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  long dur = pulseIn(ECHO_PIN, HIGH, 30000);
  return (dur == 0) ? -1 : dur * 0.034 / 2;
}

void keepWiFiAlive() {
  if (WiFi.status() != WL_CONNECTED) {
    if (millis() - lastWiFiCheck > 5000) {
      lastWiFiCheck = millis();
      WiFi.disconnect();
      WiFi.begin(ssid, password);
    }
  }
}

void notifyCarDetected() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }
  HTTPClient http;
  http.begin(carDetectedUrl);
  http.setTimeout(5000);
  http.addHeader("Content-Type", "application/json");
  http.POST("{}");
  http.end();
}

String checkServerResult() {
  if (WiFi.status() != WL_CONNECTED) return "NO_WIFI";
  HTTPClient http;
  http.begin(statusUrl);
  http.setTimeout(5000);
  int code = http.GET();
  String result = "PENDING";
  if (code == 200) {
    String body = http.getString();
    if (body.indexOf("\"status\":\"SUCCESS\"") >= 0 ||
        body.indexOf("\"status\": \"SUCCESS\"") >= 0) {
      result = "SUCCESS";
    } else if (body.indexOf("\"status\":\"FAILED\"") >= 0 ||
               body.indexOf("\"status\": \"FAILED\"") >= 0) {
      result = "FAILED";
    }
  } else {
    result = "ERROR";
  }
  http.end();
  return result;
}

void setup() {
  Serial.begin(115200);
  delay(500);

  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  ESP32PWM::allocateTimer(2);
  ESP32PWM::allocateTimer(3);
  myServo.setPeriodHertz(50);
  myServo.attach(SERVO_PIN, 500, 2400);
  myServo.write(0);
  barrierOpen = true;

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  Wire.begin(21, 22);
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("Connecting WiFi.");

  WiFi.begin(ssid, password);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 20) {
    delay(500); tries++;
  }

  scale.begin(DT_PIN, SCK_PIN);
  scale.set_scale(calibration_factor);
  delay(1000);
  scale.tare();

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print(WiFi.status() == WL_CONNECTED ? "WiFi OK!        " : "WiFi Failed!    ");
  delay(1500);
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("System Ready");
}

void loop() {
  keepWiFiAlive();

  if (millis() - lastWeightTime > 500) {
    lastWeightTime = millis();
    float raw_g = scale.get_units(3) * 1000.0;
    float weight_g = raw_g - WEIGHT_OFFSET;
    if (weight_g < 0)    weight_g = 0;
    if (weight_g < 10.0) weight_g = 0;
    lcd.setCursor(0, 0);
    lcd.print("Wt:");
    lcd.print((int)weight_g);
    lcd.print("g        ");
  }

  if (barrierOpen) {
    float dist = getDistance();
    if (dist > 0 && dist < 20.0) {
      myServo.write(90);
      barrierOpen  = false;
      gateClosedAt = millis();
      lastCheckTime= millis();
      lcd.setCursor(0, 1);
      lcd.print("Car Detected!   ");
      notifyCarDetected();
      lcd.setCursor(0, 1);
      lcd.print("Processing...   ");
    } else {
      lcd.setCursor(0, 1);
      if (dist > 0) {
        lcd.print("Dist:");
        lcd.print((int)dist);
        lcd.print("cm      ");
      } else {
        lcd.print("Waiting...      ");
      }
    }
  } else {
    if (millis() - gateClosedAt  > 4000 &&
        millis() - lastCheckTime > 3000) {
      lastCheckTime = millis();
      String result = checkServerResult();
      if (result == "SUCCESS") {
        lcd.setCursor(0, 1);
        lcd.print("Toll Success!   ");
        delay(800);
        myServo.write(0);
        lcd.setCursor(0, 1);
        lcd.print("Car passing...  ");
        unsigned long passStart = millis();
        while (millis() - passStart < 10000) {
          float d = getDistance();
          if (d < 0 || d >= 20.0) break;
          delay(200);
        }
        delay(1500);
        barrierOpen = true;
        scale.tare();
        lcd.setCursor(0, 1);
        lcd.print("System Ready    ");
      } else if (result == "FAILED") {
        lcd.setCursor(0, 1);
        lcd.print("Toll Failed!    ");
        delay(2000);
        lcd.setCursor(0, 1);
        lcd.print("Retrying...     ");
        notifyCarDetected();
        gateClosedAt = millis();
      } else {
        lcd.setCursor(0, 1);
        lcd.print("Processing...   ");
      }
    }
  }
  delay(100);
}
