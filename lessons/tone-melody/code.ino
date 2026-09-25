/*
  Melody
  Plays a melody on the buzzer on pin 8 (the official example uses a small speaker).
*/
#define NOTE_B0  31
#define NOTE_C4  262
#define NOTE_D4  294
#define NOTE_E4  330
#define NOTE_F4  349
#define NOTE_G3  196
#define NOTE_A3  220
#define NOTE_B3  247
#define NOTE_G4  392
#define NOTE_A4  440
#define NOTE_C3  131
#define NOTE_C5  523

int melody[] = { NOTE_C4, NOTE_G3, NOTE_G3, NOTE_A3, NOTE_G3, 0, NOTE_B3, NOTE_C4 };
int noteDurations[] = { 4, 8, 8, 4, 4, 4, 4, 4 };   // 4 = quarter note, 8 = eighth note

void setup() {
  for (int thisNote = 0; thisNote < 8; thisNote++) {
    int noteDuration = 1000 / noteDurations[thisNote];
    tone(8, melody[thisNote], noteDuration);
    delay(noteDuration * 1.30);        // a short gap between notes
    noTone(8);
  }
}

void loop() {
  // the tune plays once — press the Arduino's reset button to hear it again
}
