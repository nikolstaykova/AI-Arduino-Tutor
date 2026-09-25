/*
  Keyboard
  Plays a note on the buzzer (pin 8) while one of the three force sensors (A0, A1, A2) is pressed.
*/
#define NOTE_A4  440
#define NOTE_B4  494
#define NOTE_C3  131

const int threshold = 10;              // a reading above this counts as a press
int notes[] = { NOTE_A4, NOTE_B4, NOTE_C3 };

void setup() {
}

void loop() {
  for (int thisSensor = 0; thisSensor < 3; thisSensor++) {
    int sensorReading = analogRead(thisSensor);     // A0, A1, A2 in turn
    if (sensorReading > threshold) {
      tone(8, notes[thisSensor], 20);
    }
  }
}
