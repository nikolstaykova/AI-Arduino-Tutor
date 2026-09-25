/*
  Blink — running on the ATmega328P on the breadboard (it got this sketch in the
  last level, with Sketch > Upload Using Programmer).
  Arduino pin 13 is the chip's leg 19.
*/
void setup() {
  pinMode(13, OUTPUT);
}

void loop() {
  digitalWrite(13, HIGH);   // LED on
  delay(1000);
  digitalWrite(13, LOW);    // LED off
  delay(1000);
}
