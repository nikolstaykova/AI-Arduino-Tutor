/*
  Blink
  Turns an LED on for one second, then off for one second, repeatedly.
  Source: https://docs.arduino.cc/built-in-examples/basics/Blink/
*/

void setup() {
  pinMode(13, OUTPUT);
}

void loop() {
  digitalWrite(13, HIGH);
  delay(1000);
  digitalWrite(13, LOW);
  delay(1000);
}
