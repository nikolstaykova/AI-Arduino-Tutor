/*
  Dimmer
  Reads a byte (0-255) from the Serial port and sets the LED on pin 9 to that brightness.
*/
const int ledPin = 9;

void setup() {
  Serial.begin(9600);
  pinMode(ledPin, OUTPUT);
}

void loop() {
  byte brightness;
  if (Serial.available()) {
    brightness = Serial.read();
    analogWrite(ledPin, brightness);
  }
}
