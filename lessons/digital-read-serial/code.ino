/*
  DigitalReadSerial
  Reads a digital input on pin 2, prints the result to the Serial Monitor.
  Source: https://docs.arduino.cc/built-in-examples/basics/DigitalReadSerial/
*/

void setup() {
  Serial.begin(9600);
  pinMode(2, INPUT);
}

void loop() {
  int sensorValue = digitalRead(2);
  Serial.println(sensorValue);
  delay(1);
}
