/*
  JoystickMouseControl (Arduino Leonardo / Micro)
  The joystick (A0, A1) moves the mouse while it's switched on with the button on pin 2
  (the LED on pin 5 shows it's on); the button on pin 3 is the mouse button.
*/
#include "Mouse.h"

const int switchPin = 2;
const int mouseButton = 3;
const int xAxis = A0;
const int yAxis = A1;
const int ledPin = 5;
int range = 12;
int responseDelay = 5;
int threshold = range / 4;
int center = range / 2;
bool mouseIsActive = false;
int lastSwitchState = LOW;

void setup() {
  pinMode(switchPin, INPUT);
  pinMode(mouseButton, INPUT);
  pinMode(ledPin, OUTPUT);
  Mouse.begin();
}

void loop() {
  int switchState = digitalRead(switchPin);
  if (switchState != lastSwitchState) {
    if (switchState == HIGH) {
      mouseIsActive = !mouseIsActive;
      digitalWrite(ledPin, mouseIsActive);
    }
  }
  lastSwitchState = switchState;
  int xReading = readAxis(xAxis);
  int yReading = readAxis(yAxis);
  if (mouseIsActive) {
    Mouse.move(xReading, yReading, 0);
  }
  if (digitalRead(mouseButton) == HIGH) {
    if (!Mouse.isPressed(MOUSE_LEFT)) {
      Mouse.press(MOUSE_LEFT);
    }
  } else {
    if (Mouse.isPressed(MOUSE_LEFT)) {
      Mouse.release(MOUSE_LEFT);
    }
  }
  delay(responseDelay);
}

int readAxis(int thisAxis) {
  int reading = analogRead(thisAxis);
  reading = map(reading, 0, 1023, 0, range);
  int distance = reading - center;
  if (abs(distance) < threshold) {
    distance = 0;          // a dead zone round the middle
  }
  return distance;
}
