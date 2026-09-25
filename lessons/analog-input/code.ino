/*
  Analog Input
  The knob on A0 sets how fast the LED on pin 13 blinks.
*/
int sensorPin = A0;
int ledPin = 13;
int sensorValue = 0;

void setup() {
  pinMode(ledPin, OUTPUT);
}

void loop() {
  sensorValue = analogRead(sensorPin);
  digitalWrite(ledPin, HIGH);
  delay(sensorValue);            // 0 to 1023 milliseconds
  digitalWrite(ledPin, LOW);
  delay(sensorValue);
}
