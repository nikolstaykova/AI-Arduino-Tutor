/*
  Serial Call and Response ASCII
  Sends three values (A0, A1 and the button on pin 2) every time the computer sends a byte.
*/
int firstSensor = 0;
int secondSensor = 0;
int thirdSensor = 0;
int inByte = 0;

void setup() {
  Serial.begin(9600);
  while (!Serial) {
  }
  pinMode(2, INPUT);
  establishContact();
}

void loop() {
  if (Serial.available() > 0) {
    inByte = Serial.read();
    firstSensor = analogRead(A0);
    delay(10);
    secondSensor = analogRead(A1);
    thirdSensor = digitalRead(2);
    Serial.print(firstSensor);
    Serial.print(",");
    Serial.print(secondSensor);
    Serial.print(",");
    Serial.println(thirdSensor);
  }
}

void establishContact() {
  while (Serial.available() <= 0) {
    Serial.println("0,0,0");
    delay(300);
  }
}
