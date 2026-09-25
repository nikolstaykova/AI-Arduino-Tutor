/*
  Fading
  Fades the LED on pin 9 up and down with two for loops.
*/
int ledPin = 9;

void setup() {
}

void loop() {
  for (int fadeValue = 0; fadeValue <= 255; fadeValue += 5) {
    analogWrite(ledPin, fadeValue);
    delay(30);
  }
  for (int fadeValue = 255; fadeValue >= 0; fadeValue -= 5) {
    analogWrite(ledPin, fadeValue);
    delay(30);
  }
}
