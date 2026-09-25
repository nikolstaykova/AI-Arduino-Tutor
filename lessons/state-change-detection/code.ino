/*
  State change detection (edge detection)
  Counts presses of the button on pin 2; the LED on 13 lights on every fourth press.
*/
const int buttonPin = 2;
const int ledPin = 13;
int buttonPushCounter = 0;
int buttonState = 0;
int lastButtonState = 0;

void setup() {
  pinMode(buttonPin, INPUT);
  pinMode(ledPin, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  buttonState = digitalRead(buttonPin);
  if (buttonState != lastButtonState) {
    if (buttonState == HIGH) {
      buttonPushCounter++;
      Serial.print("number of button pushes: ");
      Serial.println(buttonPushCounter);
    }
    delay(50);
  }
  lastButtonState = buttonState;
  if (buttonPushCounter % 4 == 0) {
    digitalWrite(ledPin, HIGH);
  } else {
    digitalWrite(ledPin, LOW);
  }
}
