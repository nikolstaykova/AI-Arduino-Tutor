/*
  Multiple tone player
  Plays a note on each of three buzzers (pins 6, 7 and 8) in turn.
*/
void setup() {
}

void loop() {
  noTone(8);            // only one pin can play a tone at a time
  tone(6, 440, 200);
  delay(200);

  noTone(6);
  tone(7, 494, 500);
  delay(500);

  noTone(7);
  tone(8, 523, 300);
  delay(300);
}
