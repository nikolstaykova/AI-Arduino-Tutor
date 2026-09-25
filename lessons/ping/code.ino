/*
  Ping))) Sensor
  Sends a ping from the sensor on pin 7, times the echo and prints the distance.
*/
const int pingPin = 7;

void setup() {
  Serial.begin(9600);
}

void loop() {
  long duration, inches, cm;
  // a short HIGH pulse starts a ping
  pinMode(pingPin, OUTPUT);
  digitalWrite(pingPin, LOW);
  delayMicroseconds(2);
  digitalWrite(pingPin, HIGH);
  delayMicroseconds(5);
  digitalWrite(pingPin, LOW);
  // the same pin then listens: the echo pulse is as long as the sound took to come back
  pinMode(pingPin, INPUT);
  duration = pulseIn(pingPin, HIGH);
  inches = microsecondsToInches(duration);
  cm = microsecondsToCentimeters(duration);
  Serial.print(inches);
  Serial.print("in, ");
  Serial.print(cm);
  Serial.print("cm");
  Serial.println();
  delay(100);
}

long microsecondsToInches(long microseconds) {
  return microseconds / 74 / 2;      // sound: 74 µs per inch, there and back
}

long microsecondsToCentimeters(long microseconds) {
  return microseconds / 29 / 2;      // 29 µs per cm, there and back
}
