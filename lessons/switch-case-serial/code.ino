/*
  Switch statement with serial input
  Sending a, b, c, d or e lights the LED on pin 2, 3, 4, 5 or 6; anything else turns them all off.
*/
void setup() {
  Serial.begin(9600);
  for (int thisPin = 2; thisPin < 7; thisPin++) {
    pinMode(thisPin, OUTPUT);
  }
}

void loop() {
  if (Serial.available() > 0) {
    int inByte = Serial.read();
    switch (inByte) {
      case 'a': digitalWrite(2, HIGH); break;
      case 'b': digitalWrite(3, HIGH); break;
      case 'c': digitalWrite(4, HIGH); break;
      case 'd': digitalWrite(5, HIGH); break;
      case 'e': digitalWrite(6, HIGH); break;
      default:
        for (int thisPin = 2; thisPin < 7; thisPin++) {
          digitalWrite(thisPin, LOW);
        }
    }
  }
}
