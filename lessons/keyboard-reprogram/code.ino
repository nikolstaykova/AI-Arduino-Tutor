/*
  Arduino Programs Blink (Arduino Leonardo / Micro)
  With the Arduino IDE open and in front, press the button on pin 2 (to GND): the Leonardo opens a new
  sketch, types the Blink program into it and uploads it.
*/
#include "Keyboard.h"

char ctrlKey = KEY_LEFT_GUI;     // on a Mac; use KEY_LEFT_CTRL on Windows / Linux

void setup() {
  pinMode(2, INPUT_PULLUP);
  Keyboard.begin();
}

void loop() {
  while (digitalRead(2) == HIGH) {
    delay(500);                  // wait for the button
  }
  delay(1000);
  Keyboard.press(ctrlKey);       // new sketch
  Keyboard.press('n');
  delay(100);
  Keyboard.releaseAll();
  delay(1000);
  Keyboard.press(ctrlKey);       // select all, delete
  Keyboard.press('a');
  delay(500);
  Keyboard.releaseAll();
  Keyboard.write(KEY_BACKSPACE);
  delay(500);
  Keyboard.println("void setup() {");
  Keyboard.print("pinMode");
  Keyboard.println("(13, OUTPUT);");
  Keyboard.println("}");
  Keyboard.println();
  Keyboard.println("void loop() {");
  Keyboard.print("digitalWrite");
  Keyboard.println("(13, HIGH);");
  Keyboard.println("delay(3000);");
  Keyboard.print("digitalWrite");
  Keyboard.println("(13, LOW);");
  Keyboard.println("delay(1000);");
  Keyboard.println("}");
  Keyboard.press(ctrlKey);       // tidy up the formatting
  Keyboard.press('t');
  delay(100);
  Keyboard.releaseAll();
  delay(3000);
  Keyboard.press(ctrlKey);       // upload
  Keyboard.press('u');
  delay(100);
  Keyboard.releaseAll();
  while (true) {
  }
}
