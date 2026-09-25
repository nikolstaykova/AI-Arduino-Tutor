/*
  Arrays
  Lights LEDs on the pins listed in an array, forwards then backwards.
*/
int timer = 100;
int ledPins[] = { 2, 7, 4, 6, 5, 3 };   // an array of pin numbers, in any order
int pinCount = 6;

void setup() {
  for (int thisPin = 0; thisPin < pinCount; thisPin++) {
    pinMode(ledPins[thisPin], OUTPUT);
  }
}

void loop() {
  for (int thisPin = 0; thisPin < pinCount; thisPin++) {
    digitalWrite(ledPins[thisPin], HIGH);
    delay(timer);
    digitalWrite(ledPins[thisPin], LOW);
  }
  for (int thisPin = pinCount - 1; thisPin >= 0; thisPin--) {
    digitalWrite(ledPins[thisPin], HIGH);
    delay(timer);
    digitalWrite(ledPins[thisPin], LOW);
  }
}
