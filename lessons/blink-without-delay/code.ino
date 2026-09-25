/*
  Blink without Delay
  Turns an LED on and off without using delay(), by checking the clock (millis()).
*/
const int ledPin = 13;
int ledState = LOW;
unsigned long previousMillis = 0;
const long interval = 1000;       // blink every second

void setup() {
  pinMode(ledPin, OUTPUT);
}

void loop() {
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;
    ledState = (ledState == LOW) ? HIGH : LOW;
    digitalWrite(ledPin, ledState);
  }
}
