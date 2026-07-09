#include <WiFi.h>
#include <HTTPClient.h>
#include "esp_camera.h"
#include "img_converters.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"

const char* ssid     = "Hello";
const char* password = "11111111";
const char* triggerUrl = "http://10.75.189.48:5000/api/camera-trigger";
const char* serverHost = "10.75.189.48";
const int serverPort = 5000;

#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

void connectWiFi();
bool initCamera();
void captureAndUpload();

void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);
  Serial.begin(115200);
  delay(1000);
  connectWiFi();
  if (!initCamera()) {
    delay(3000);
    ESP.restart();
  }
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }
  HTTPClient http;
  http.begin(triggerUrl);
  http.setTimeout(5000);
  int httpCode = http.GET();
  if (httpCode == 200) {
    String response = http.getString();
    if (response.indexOf("true") >= 0) {
      delay(300);
      captureAndUpload();
      delay(3000);
    }
  }
  http.end();
  delay(1000);
}

void connectWiFi() {
  WiFi.begin(ssid, password);
  int retry = 0;
  while (WiFi.status() != WL_CONNECTED && retry < 20) {
    delay(500);
    retry++;
  }
  if (WiFi.status() != WL_CONNECTED) {
    delay(3000);
    ESP.restart();
  }
}

bool initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer   = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href  = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn  = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 10000000;
  config.pixel_format = PIXFORMAT_RGB565;
  config.frame_size   = FRAMESIZE_QQVGA;
  config.fb_count     = 1;
  config.grab_mode    = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location  = CAMERA_FB_IN_DRAM;
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    return false;
  }
  sensor_t * s = esp_camera_sensor_get();
  s->set_brightness(s, 1);
  s->set_saturation(s, 0);
  return true;
}

void captureAndUpload() {
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) {
    return;
  }
  uint8_t* jpg_buf = NULL;
  size_t   jpg_len = 0;
  bool converted = frame2jpg(fb, 80, &jpg_buf, &jpg_len);
  esp_camera_fb_return(fb);
  if (!converted || jpg_buf == NULL) {
    if (jpg_buf) free(jpg_buf);
    return;
  }
  WiFiClient client;
  if (!client.connect(serverHost, serverPort)) {
    free(jpg_buf);
    return;
  }
  String boundary = "----ESP32CAMBoundary";
  String head =
      "--" + boundary + "\r\n"
      "Content-Disposition: form-data; name=\"image\"; filename=\"capture.jpg\"\r\n"
      "Content-Type: image/jpeg\r\n\r
";
  String tail = "\r\n--" + boundary + "--\r\n";
  uint32_t contentLength = head.length() + jpg_len + tail.length();
  client.println("POST /api/toll-pay-image HTTP/1.1");
  client.println("Host: " + String(serverHost) + ":" + String(serverPort));
  client.println("Content-Type: multipart/form-data; boundary=" + boundary);
  client.println("Content-Length: " + String(contentLength));
  client.println("Connection: close");
  client.println();
  client.print(head);
  const size_t chunkSize = 1024;
  size_t sent = 0;
  while (sent < jpg_len) {
    size_t toSend = min(chunkSize, jpg_len - sent);
    client.write(jpg_buf + sent, toSend);
    sent += toSend;
  }
  client.print(tail);
  free(jpg_buf);
  unsigned long timeout = millis();
  while (client.available() == 0) {
    if (millis() - timeout > 10000) {
      client.stop();
      return;
    }
  }
  while (client.available()) {
    client.readStringUntil('\n');
  }
  client.stop();
}
