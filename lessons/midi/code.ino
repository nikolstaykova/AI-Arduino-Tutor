/*
  MIDI note player
  Plays MIDI notes from F#-0 (0x1E) to F#-5 (0x5A) on the MIDI socket (TX, pin 1).
  Unplug the MIDI cable while uploading.
*/
void setup() {
  Serial.begin(31250);          // the MIDI speed
}

void loop() {
  for (int note = 0x1E; note < 0x5A; note++) {
    noteOn(0x90, note, 0x45);   // note on, channel 1, middle velocity
    delay(100);
    noteOn(0x90, note, 0x00);   // velocity 0: note off
    delay(100);
  }
}

// a MIDI message: command, pitch, velocity
void noteOn(int cmd, int pitch, int velocity) {
  Serial.write(cmd);
  Serial.write(pitch);
  Serial.write(velocity);
}
