/*
  Pitch follower
  Plays a pitch that changes with the light on the photoresistor (A0), on the buzzer on pin 9.
*/
void setup() {
  Serial.begin(9600);
}

void loop() {
  int sensorReading = analogRead(A0);
  Serial.println(sensorReading);                        // see your own light range here
  int thisPitch = map(sensorReading, 400, 1000, 120, 1500);
  tone(9, thisPitch, 10);
  delay(1);
}
