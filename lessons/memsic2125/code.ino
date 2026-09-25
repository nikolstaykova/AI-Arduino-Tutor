/*
  Memsic2125
  Reads the X and Y pulse outputs of a Memsic 2125 (pins 2 and 3) and prints the acceleration in milli-g.
*/
const int xPin = 2;
const int yPin = 3;

void setup() {
  Serial.begin(9600);
  pinMode(xPin, INPUT);
  pinMode(yPin, INPUT);
}

void loop() {
  int pulseX, pulseY;
  int accelerationX, accelerationY;
  pulseX = pulseIn(xPin, HIGH);
  pulseY = pulseIn(yPin, HIGH);
  // 5000 µs pulses mean level; each 12.5 µs more or less is 1 milli-g
  accelerationX = ((pulseX / 10) - 500) * 8;
  accelerationY = ((pulseY / 10) - 500) * 8;
  Serial.print(accelerationX);
  Serial.print("\t");
  Serial.print(accelerationY);
  Serial.println();
  delay(100);
}
