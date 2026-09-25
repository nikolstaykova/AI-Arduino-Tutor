/*
  Fade
  Fades an LED on pin 9 in and out using analogWrite().
*/
int led = 9;           // a PWM pin (marked ~)
int brightness = 0;    // how bright the LED is
int fadeAmount = 5;    // how much to change it each time

void setup() {
  pinMode(led, OUTPUT);
}

void loop() {
  analogWrite(led, brightness);
  brightness = brightness + fadeAmount;
  if (brightness <= 0 || brightness >= 255) {
    fadeAmount = -fadeAmount;     // turn round at the ends
  }
  delay(30);
}
