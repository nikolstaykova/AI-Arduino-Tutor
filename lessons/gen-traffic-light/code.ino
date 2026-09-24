// Traffic Light
// Red LED on pin 12, yellow LED on pin 11, green LED on pin 10.
// Each LED has a 220 ohm resistor in series and its short leg to GND.

const int redPin = 12;     // red LED on pin 12
const int yellowPin = 11;  // yellow LED on pin 11
const int greenPin = 10;   // green LED on pin 10

void setup() {
  pinMode(redPin, OUTPUT);
  pinMode(yellowPin, OUTPUT);
  pinMode(greenPin, OUTPUT);
}

void loop() {
  // Green: go
  digitalWrite(redPin, LOW);
  digitalWrite(yellowPin, LOW);
  digitalWrite(greenPin, HIGH);
  delay(5000);

  // Yellow: get ready to stop
  digitalWrite(greenPin, LOW);
  digitalWrite(yellowPin, HIGH);
  delay(2000);

  // Red: stop
  digitalWrite(yellowPin, LOW);
  digitalWrite(redPin, HIGH);
  delay(5000);
}
