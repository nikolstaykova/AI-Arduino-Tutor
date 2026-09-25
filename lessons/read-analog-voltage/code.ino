/*
  ReadAnalogVoltage
  Reads an analog input on pin A0, converts it to voltage, and prints it to the Serial Monitor.
*/
void setup() {
  Serial.begin(9600);
}

void loop() {
  int sensorValue = analogRead(A0);
  float voltage = sensorValue * (5.0 / 1023.0);   // 0-1023 becomes 0-5 V
  Serial.println(voltage);
}
