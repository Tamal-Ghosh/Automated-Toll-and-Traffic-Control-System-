const int GREEN_PINS[4]  = {1, 5, 8, 11};
const int YELLOW_PINS[4] = {2, 6, 9, 12};
const int RED_PINS[4]    = {4, 7, 10, 13};

const int IR_NEAR[4] = {14, 16, 18, 38};
const int IR_FAR[4]  = {15, 17, 21, 39};

const int BASE_GREEN_TIME = 5000;
const int MAX_GREEN_TIME  = 15000;
const int YELLOW_TIME     = 1000;

void setup() {
  Serial.begin(115200);
  for (int i = 0; i < 4; i++) {
    pinMode(GREEN_PINS[i], OUTPUT);
    pinMode(YELLOW_PINS[i], OUTPUT);
    pinMode(RED_PINS[i], OUTPUT);
    pinMode(IR_NEAR[i], INPUT);
    pinMode(IR_FAR[i], INPUT);
    digitalWrite(RED_PINS[i], HIGH);
    digitalWrite(GREEN_PINS[i], LOW);
    digitalWrite(YELLOW_PINS[i], LOW);
  }
}

void loop() {
  int densityA = getPairDensity(0, 2);
  int densityB = getPairDensity(1, 3);

  int greenTimeA = calculateDuration(densityA, densityB);
  setPairState(0, 2, "GREEN");
  setPairState(1, 3, "RED");
  delay(greenTimeA);

  setAllLanesYellow();
  delay(YELLOW_TIME);

  int greenTimeB = calculateDuration(densityB, densityA);
  setPairState(0, 2, "RED");
  setPairState(1, 3, "GREEN");
  delay(greenTimeB);

  setAllLanesYellow();
  delay(YELLOW_TIME);
}

int getPairDensity(int laneX, int laneY) {
  int score = 0;
  if (digitalRead(IR_NEAR[laneX]) == LOW) score++;
  if (digitalRead(IR_FAR[laneX]) == LOW) score++;
  if (digitalRead(IR_NEAR[laneY]) == LOW) score++;
  if (digitalRead(IR_FAR[laneY]) == LOW) score++;
  return score;
}

int calculateDuration(int activeDensity, int inactiveDensity) {
  if (activeDensity == inactiveDensity) {
    return BASE_GREEN_TIME;
  }
  else if (activeDensity > inactiveDensity) {
    int extraTime = (activeDensity - inactiveDensity) * 2500;
    int totalTime = BASE_GREEN_TIME + extraTime;
    if (totalTime > MAX_GREEN_TIME) {
      totalTime = MAX_GREEN_TIME;
    }
    return totalTime;
  }
  else {
    return BASE_GREEN_TIME;
  }
}

void setPairState(int laneX, int laneY, String state) {
  int lanes[2] = {laneX, laneY};
  for (int i = 0; i < 2; i++) {
    int l = lanes[i];
    if (state == "GREEN") {
      digitalWrite(GREEN_PINS[l], HIGH);
      digitalWrite(YELLOW_PINS[l], LOW);
      digitalWrite(RED_PINS[l], LOW);
    }
    else if (state == "YELLOW") {
      digitalWrite(GREEN_PINS[l], LOW);
      digitalWrite(YELLOW_PINS[l], HIGH);
      digitalWrite(RED_PINS[l], LOW);
    }
    else {
      digitalWrite(GREEN_PINS[l], LOW);
      digitalWrite(YELLOW_PINS[l], LOW);
      digitalWrite(RED_PINS[l], HIGH);
    }
  }
}

void setAllLanesYellow() {
  for (int i = 0; i < 4; i++) {
    digitalWrite(GREEN_PINS[i], LOW);
    digitalWrite(YELLOW_PINS[i], HIGH);
    digitalWrite(RED_PINS[i], LOW);
  }
}
