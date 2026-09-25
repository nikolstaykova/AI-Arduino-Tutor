/*
  Virtual Color Mixer
  Sends three analog readings (A0, A1, A2) as comma-separated values for a computer program to mix a colour.
*/
const int redPin = A0;
const int greenPin = A1;
const int bluePin = A2;

void setup() {
  Serial.begin(9600);
}

void loop() {
  Serial.print(analogRead(redPin));
  Serial.print(",");
  Serial.print(analogRead(greenPin));
  Serial.print(",");
  Serial.println(analogRead(bluePin));
}
