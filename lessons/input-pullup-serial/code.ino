/*
  Input Pull-up Serial
  Reads a pushbutton on pin 2 using the internal pull-up, prints it, and lights the LED on 13 while pressed.
*/
void setup() {
  Serial.begin(9600);
  pinMode(2, INPUT_PULLUP);
  pinMode(13, OUTPUT);
}

void loop() {
  int sensorVal = digitalRead(2);
  Serial.println(sensorVal);
  // with a pull-up the logic is backwards: HIGH when open, LOW when pressed
  if (sensorVal == HIGH) {
    digitalWrite(13, LOW);
  } else {
    digitalWrite(13, HIGH);
  }
}
