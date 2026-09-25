/*
  Calibration
  For 5 seconds after starting, records the lowest and highest readings of the light sensor on A0
  (the LED on pin 13 is on while it learns), then maps the light to the LED on pin 9's brightness.
*/
const int sensorPin = A0;
const int ledPin = 9;
const int indicatorPin = 13;
int sensorValue = 0;
int sensorMin = 1023;
int sensorMax = 0;

void setup() {
  pinMode(indicatorPin, OUTPUT);
  digitalWrite(indicatorPin, HIGH);          // learning…
  while (millis() < 5000) {
    sensorValue = analogRead(sensorPin);
    if (sensorValue > sensorMax) {
      sensorMax = sensorValue;
    }
    if (sensorValue < sensorMin) {
      sensorMin = sensorValue;
    }
  }
  digitalWrite(indicatorPin, LOW);           // done
}

void loop() {
  sensorValue = analogRead(sensorPin);
  sensorValue = constrain(sensorValue, sensorMin, sensorMax);
  sensorValue = map(sensorValue, sensorMin, sensorMax, 0, 255);
  analogWrite(ledPin, sensorValue);
}
