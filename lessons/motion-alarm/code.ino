/*
  Motion Alarm
  When the PIR sensor sees movement, the LED lights up.
  The sensor's OUT pin is HIGH while it senses motion and LOW when all is still.
*/

const int sensorPin = 2;   // the PIR's OUT pin
const int ledPin = 13;     // the LED (through its resistor)

void setup() {
  pinMode(sensorPin, INPUT);
  pinMode(ledPin, OUTPUT);
}

void loop() {
  int motion = digitalRead(sensorPin);   // HIGH = something moved
  digitalWrite(ledPin, motion);          // light the LED while there's motion
}
