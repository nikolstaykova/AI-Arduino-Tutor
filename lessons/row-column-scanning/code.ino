/*
  Row-Column Scanning an 8x8 LED matrix with X-Y input
  The knobs on A0 and A1 move a lit dot. (Arduino's example writes pins 16-19 as numbers;
  on an Uno those are A2-A5, written here by name.)
*/
const int rowPins[8] = { 2, 7, A5, 5, 13, A4, 12, A2 };   // R1-R8: the anodes (+)
const int colPins[8] = { 6, 11, 10, 3, A3, 4, 8, 9 };     // C1-C8: the cathodes (-)
int pixels[8][8];
int x = 5;
int y = 5;

void setup() {
  for (int thisPin = 0; thisPin < 8; thisPin++) {
    pinMode(colPins[thisPin], OUTPUT);
    pinMode(rowPins[thisPin], OUTPUT);
    digitalWrite(colPins[thisPin], HIGH);          // columns HIGH: all dots off
  }
  for (int i = 0; i < 8; i++) {
    for (int j = 0; j < 8; j++) {
      pixels[i][j] = HIGH;
    }
  }
}

void loop() {
  readSensors();
  refreshScreen();
}

void readSensors() {
  pixels[x][y] = HIGH;                               // clear the old dot
  x = 7 - map(analogRead(A0), 0, 1023, 0, 7);
  y = map(analogRead(A1), 0, 1023, 0, 7);
  pixels[x][y] = LOW;                                // a LOW column lights the dot
}

void refreshScreen() {
  for (int thisRow = 0; thisRow < 8; thisRow++) {
    digitalWrite(rowPins[thisRow], HIGH);            // one row at a time
    for (int thisCol = 0; thisCol < 8; thisCol++) {
      int thisPixel = pixels[thisRow][thisCol];
      digitalWrite(colPins[thisCol], thisPixel);
      if (thisPixel == LOW) {
        digitalWrite(colPins[thisCol], HIGH);
      }
    }
    digitalWrite(rowPins[thisRow], LOW);
  }
}
