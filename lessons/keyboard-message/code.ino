/*
  Keyboard Message test (Arduino Leonardo / Micro)
  Each press of the button on pin 4 types "You pressed the button N times."
*/
#include "Keyboard.h"

const int buttonPin = 4;
int previousButtonState = HIGH;
int counter = 0;

void setup() {
  pinMode(buttonPin, INPUT);
  Keyboard.begin();
}

void loop() {
  int buttonState = digitalRead(buttonPin);
  if ((buttonState != previousButtonState) && (buttonState == HIGH)) {
    counter++;
    Keyboard.print("You pressed the button ");
    Keyboard.print(counter);
    Keyboard.println(" times.");
  }
  previousButtonState = buttonState;
}
