/*
  ButtonMouseControl (Arduino Leonardo / Micro)
  Buttons on pins 2-5 move the mouse up, down, left, right; the button on pin 6 clicks.
  Tip: have a way to unplug — the Arduino really moves your mouse.
*/
#include "Mouse.h"

const int upButton = 2;
const int downButton = 3;
const int leftButton = 4;
const int rightButton = 5;
const int mouseButton = 6;
int range = 5;              // how far each step moves the mouse
int responseDelay = 10;     // ms between reads

void setup() {
  pinMode(upButton, INPUT);
  pinMode(downButton, INPUT);
  pinMode(leftButton, INPUT);
  pinMode(rightButton, INPUT);
  pinMode(mouseButton, INPUT);
  Mouse.begin();
}

void loop() {
  int upState = digitalRead(upButton);
  int downState = digitalRead(downButton);
  int rightState = digitalRead(rightButton);
  int leftState = digitalRead(leftButton);
  int clickState = digitalRead(mouseButton);
  int xDistance = (leftState - rightState) * range;
  int yDistance = (upState - downState) * range;
  if ((xDistance != 0) || (yDistance != 0)) {
    Mouse.move(xDistance, yDistance, 0);
  }
  if (clickState == HIGH) {
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
