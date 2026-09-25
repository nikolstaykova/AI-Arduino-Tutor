/*
  ADXL3xx
  Reads the X, Y and Z outputs of an ADXL3xx accelerometer (A3, A2, A1) and prints them.
  (Arduino's example plugs the board straight into A0-A5 and powers it from A4/A5 set as outputs;
  here it's wired to 3.3V and GND with jumper wires instead.)
*/
const int xpin = A3;
const int ypin = A2;
const int zpin = A1;

void setup() {
  Serial.begin(9600);
}

void loop() {
  Serial.print(analogRead(xpin));
  Serial.print("\t");
  Serial.print(analogRead(ypin));
  Serial.print("\t");
  Serial.print(analogRead(zpin));
  Serial.println();
  delay(100);
}
