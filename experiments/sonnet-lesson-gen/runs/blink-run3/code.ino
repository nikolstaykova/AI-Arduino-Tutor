/*
  Blink (external LED)

  Turns an LED on for one second, then off for one second, repeatedly.

  This version drives an external LED wired through a resistor on the
  breadboard, connected to pin 13, instead of the board's built-in LED.

  modified 8 May 2014
  by Scott Fitzgerald
  modified 2 Sep 2016
  by Arturo Guadalupi
  modified 8 Sep 2016
  by Colby Newman

  This example code is in the public domain.

  https://docs.arduino.cc/built-in-examples/basics/Blink/
*/

const int ledPin = 13;

// the setup function runs once when you press reset or power the board
void setup() {
  // initialize digital pin ledPin (pin 13) as an output.
  pinMode(ledPin, OUTPUT);
}

// the loop function runs over and over again forever
void loop() {
  digitalWrite(ledPin, HIGH);  // change state of the LED by setting pin 13 to the HIGH voltage level
  delay(1000);                 // wait for a second
  digitalWrite(ledPin, LOW);   // change state of the LED by setting pin 13 to the LOW voltage level
  delay(1000);                 // wait for a second
}
