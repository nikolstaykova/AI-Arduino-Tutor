/*
  For Loop Iteration
  Lights the LEDs on pins 2 to 7 in turn, up and then back down.
*/
int timer = 100;

void setup() {
  for (int thisPin = 2; thisPin < 8; thisPin++) {
    pinMode(thisPin, OUTPUT);
  }
}

void loop() {
  for (int thisPin = 2; thisPin < 8; thisPin++) {
    digitalWrite(thisPin, HIGH);
    delay(timer);
    digitalWrite(thisPin, LOW);
  }
  for (int thisPin = 7; thisPin >= 2; thisPin--) {
    digitalWrite(thisPin, HIGH);
    delay(timer);
    digitalWrite(thisPin, LOW);
  }
}
