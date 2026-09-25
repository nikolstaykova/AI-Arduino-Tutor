"""The Arduino built-in examples that can be built with parts CircuitQuest
already simulates — each as a lesson-kit description with the official sketch
(docs.arduino.cc/built-in-examples, public domain examples; comments shortened)."""
from tools.lesson_kit import Lesson

D = "https://docs.arduino.cc/built-in-examples/"


def read_analog_voltage():
    L = Lesson("read-analog-voltage", "Read Analog Voltage", "Turn a knob and read the voltage on its middle leg, from 0 V to 5 V.",
               D + "basics/ReadAnalogVoltage/", "Read Analog Voltage", requires=["analog-read-serial"], code="""
/*
  ReadAnalogVoltage
  Reads an analog input on pin A0, converts it to voltage, and prints it to the Serial Monitor.
*/
void setup() {
  Serial.begin(9600);
}

void loop() {
  int sensorValue = analogRead(A0);
  float voltage = sensorValue * (5.0 / 1023.0);   // 0-1023 becomes 0-5 V
  Serial.println(voltage);
}
""")
    L.pot("A0"); L.upload("Open the Serial Monitor (the magnifying glass, top right) and turn the knob: the voltage goes from 0.00 to 5.00.")
    return L


def fade():
    L = Lesson("fade", "Fading an LED", "Make an LED glow brighter and dimmer with analogWrite() (PWM).",
               D + "basics/Fade/", "Fade", requires=["blink"], code="""
/*
  Fade
  Fades an LED on pin 9 in and out using analogWrite().
*/
int led = 9;           // a PWM pin (marked ~)
int brightness = 0;    // how bright the LED is
int fadeAmount = 5;    // how much to change it each time

void setup() {
  pinMode(led, OUTPUT);
}

void loop() {
  analogWrite(led, brightness);
  brightness = brightness + fadeAmount;
  if (brightness <= 0 || brightness >= 255) {
    fadeAmount = -fadeAmount;     // turn round at the ends
  }
  delay(30);
}
""")
    L.led(9); L.upload("The LED slowly glows brighter, then dimmer, over and over. Pin 9 has a ~ next to it: it can 'fake' in-between brightness (PWM).")
    return L


def blink_without_delay():
    L = Lesson("blink-without-delay", "Blink Without Delay", "Blink an LED while the Arduino stays free to do other things — using millis() instead of delay().",
               D + "digital/BlinkWithoutDelay/", "Blink Without Delay", requires=["blink"], code="""
/*
  Blink without Delay
  Turns an LED on and off without using delay(), by checking the clock (millis()).
*/
const int ledPin = 13;
int ledState = LOW;
unsigned long previousMillis = 0;
const long interval = 1000;       // blink every second

void setup() {
  pinMode(ledPin, OUTPUT);
}

void loop() {
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= interval) {
    previousMillis = currentMillis;
    ledState = (ledState == LOW) ? HIGH : LOW;
    digitalWrite(ledPin, ledState);
  }
}
""")
    L.led(13); L.upload("The LED blinks once a second — but the loop never stops to wait, so you could add more jobs to it.")
    return L


def button():
    L = Lesson("button", "Button", "Turn an LED on while a pushbutton is pressed.", D + "digital/Button/", "Button",
               requires=["digital-read-serial"], code="""
/*
  Button
  Turns on an LED on pin 13 while the pushbutton on pin 2 is pressed.
*/
const int buttonPin = 2;
const int ledPin = 13;
int buttonState = 0;

void setup() {
  pinMode(ledPin, OUTPUT);
  pinMode(buttonPin, INPUT);
}

void loop() {
  buttonState = digitalRead(buttonPin);
  if (buttonState == HIGH) {
    digitalWrite(ledPin, HIGH);
  } else {
    digitalWrite(ledPin, LOW);
  }
}
""")
    L.button(2); L.led(13); L.upload("Press the button: the LED lights up. Let go: it turns off.")
    return L


def debounce():
    L = Lesson("debounce", "Debounce", "Each press toggles the LED — ignoring the tiny 'bounces' a real button makes.", D + "digital/Debounce/", "Debounce",
               requires=["button"], code="""
/*
  Debounce
  Each press of the button on pin 2 toggles the LED on pin 13, ignoring bounce.
*/
const int buttonPin = 2;
const int ledPin = 13;
int ledState = HIGH;
int buttonState;
int lastButtonState = LOW;
unsigned long lastDebounceTime = 0;
unsigned long debounceDelay = 50;    // ms the reading must stay the same

void setup() {
  pinMode(buttonPin, INPUT);
  pinMode(ledPin, OUTPUT);
  digitalWrite(ledPin, ledState);
}

void loop() {
  int reading = digitalRead(buttonPin);
  if (reading != lastButtonState) {
    lastDebounceTime = millis();
  }
  if ((millis() - lastDebounceTime) > debounceDelay) {
    if (reading != buttonState) {
      buttonState = reading;
      if (buttonState == HIGH) {
        ledState = !ledState;
      }
    }
  }
  digitalWrite(ledPin, ledState);
  lastButtonState = reading;
}
""")
    L.button(2); L.led(13); L.upload("Each press switches the LED: on, off, on … even if the button's metal contacts bounce.")
    return L


def input_pullup():
    L = Lesson("input-pullup-serial", "Input Pullup Serial", "Read a button with no resistor at all — using the Arduino's built-in pull-up.",
               D + "digital/InputPullupSerial/", "Input Pullup Serial", requires=["digital-read-serial"], code="""
/*
  Input Pull-up Serial
  Reads a pushbutton on pin 2 using the internal pull-up, prints it, and lights the LED on 13 while pressed.
*/
void setup() {
  Serial.begin(9600);
  pinMode(2, INPUT_PULLUP);
  pinMode(13, OUTPUT);
}

void loop() {
  int sensorVal = digitalRead(2);
  Serial.println(sensorVal);
  // with a pull-up the logic is backwards: HIGH when open, LOW when pressed
  if (sensorVal == HIGH) {
    digitalWrite(13, LOW);
  } else {
    digitalWrite(13, HIGH);
  }
}
""")
    L.button(2, pulldown=False); L.led(13); L.upload("The Serial Monitor shows 1 — press the button and it shows 0 while the LED lights.")
    return L


def state_change():
    L = Lesson("state-change-detection", "State Change Detection", "Count button presses — noticing the moment it changes, not how long it's held.",
               D + "digital/StateChangeDetection/", "State Change Detection", requires=["button"], code="""
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
""")
    L.button(2); L.led(13); L.upload("Open the Serial Monitor and press the button: it counts every press, and the LED lights on every fourth one.")
    return L


PITCHES = """#define NOTE_B0  31
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
#define NOTE_C5  523"""


def tone_melody():
    L = Lesson("tone-melody", "Tone Melody", "Play a little tune on a piezo buzzer with tone().", D + "digital/toneMelody/", "Tone Melody",
               requires=["blink"], code=f"""
/*
  Melody
  Plays a melody on the buzzer on pin 8 (the official example uses a small speaker).
*/
{PITCHES}

int melody[] = {{ NOTE_C4, NOTE_G3, NOTE_G3, NOTE_A3, NOTE_G3, 0, NOTE_B3, NOTE_C4 }};
int noteDurations[] = {{ 4, 8, 8, 4, 4, 4, 4, 4 }};   // 4 = quarter note, 8 = eighth note

void setup() {{
  for (int thisNote = 0; thisNote < 8; thisNote++) {{
    int noteDuration = 1000 / noteDurations[thisNote];
    tone(8, melody[thisNote], noteDuration);
    delay(noteDuration * 1.30);        // a short gap between notes
    noTone(8);
  }}
}}

void loop() {{
  // the tune plays once — press the Arduino's reset button to hear it again
}}
""")
    L.buzzer(8); L.upload("The buzzer plays 'shave and a haircut'. Press the Arduino's reset button to hear it again.")
    return L


def tone_multiple():
    L = Lesson("tone-multiple", "Tone on Multiple Speakers", "Play notes on three buzzers, one after another.", D + "digital/toneMultiple/",
               "Tone Multiple", requires=["tone-melody"], code="""
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
""")
    for pin in (6, 7, 8):
        L.buzzer(pin)
    L.upload("The three buzzers take turns: A, B, C — over and over.")
    return L


def analog_in_out():
    L = Lesson("analog-in-out-serial", "Analog In, Out Serial", "A knob controls how bright an LED is — and the numbers show on the Serial Monitor.",
               D + "analog/AnalogInOutSerial/", "Analog In Out Serial", requires=["analog-read-serial", "fade"], code="""
/*
  Analog input, analog output, serial output
  Reads the knob on A0, maps it to 0-255 and sets the LED on pin 9's brightness.
*/
const int analogInPin = A0;
const int analogOutPin = 9;
int sensorValue = 0;
int outputValue = 0;

void setup() {
  Serial.begin(9600);
}

void loop() {
  sensorValue = analogRead(analogInPin);
  outputValue = map(sensorValue, 0, 1023, 0, 255);
  analogWrite(analogOutPin, outputValue);
  Serial.print("sensor = ");
  Serial.print(sensorValue);
  Serial.print("\\t output = ");
  Serial.println(outputValue);
  delay(2);
}
""")
    L.pot("A0"); L.led(9); L.upload("Turn the knob: the LED gets brighter and dimmer, and the Serial Monitor shows both numbers.")
    return L


def analog_input():
    L = Lesson("analog-input", "Analog Input", "A knob sets how fast an LED blinks.", D + "analog/AnalogInput/", "Analog Input",
               requires=["analog-read-serial"], code="""
/*
  Analog Input
  The knob on A0 sets how fast the LED on pin 13 blinks.
*/
int sensorPin = A0;
int ledPin = 13;
int sensorValue = 0;

void setup() {
  pinMode(ledPin, OUTPUT);
}

void loop() {
  sensorValue = analogRead(sensorPin);
  digitalWrite(ledPin, HIGH);
  delay(sensorValue);            // 0 to 1023 milliseconds
  digitalWrite(ledPin, LOW);
  delay(sensorValue);
}
""")
    L.pot("A0"); L.led(13); L.upload("Turn the knob: the LED blinks faster or slower.")
    return L


def fading():
    L = Lesson("fading", "Fading", "Fade an LED up and down with a for loop and analogWrite().", D + "analog/Fading/", "Fading",
               requires=["fade"], code="""
/*
  Fading
  Fades the LED on pin 9 up and down with two for loops.
*/
int ledPin = 9;

void setup() {
}

void loop() {
  for (int fadeValue = 0; fadeValue <= 255; fadeValue += 5) {
    analogWrite(ledPin, fadeValue);
    delay(30);
  }
  for (int fadeValue = 255; fadeValue >= 0; fadeValue -= 5) {
    analogWrite(ledPin, fadeValue);
    delay(30);
  }
}
""")
    L.led(9); L.upload("The LED smoothly fades up to full, then back down.")
    return L


def smoothing():
    L = Lesson("smoothing", "Smoothing", "Average the last 10 readings of a knob so the number stops jumping about.", D + "analog/Smoothing/", "Smoothing",
               requires=["analog-read-serial"], code="""
/*
  Smoothing
  Keeps the last 10 readings of A0 and prints their average.
*/
const int numReadings = 10;
int readings[numReadings];
int readIndex = 0;
int total = 0;
int average = 0;
int inputPin = A0;

void setup() {
  Serial.begin(9600);
  for (int thisReading = 0; thisReading < numReadings; thisReading++) {
    readings[thisReading] = 0;
  }
}

void loop() {
  total = total - readings[readIndex];
  readings[readIndex] = analogRead(inputPin);
  total = total + readings[readIndex];
  readIndex = readIndex + 1;
  if (readIndex >= numReadings) {
    readIndex = 0;
  }
  average = total / numReadings;
  Serial.println(average);
  delay(1);
}
""")
    L.pot("A0"); L.upload("Turn the knob and watch the Serial Monitor (or Serial Plotter): the number moves smoothly.")
    return L


def dimmer():
    L = Lesson("dimmer", "Dimmer", "Send a number from your computer to set an LED's brightness.", D + "communication/Dimmer/", "Dimmer",
               requires=["fade"], code="""
/*
  Dimmer
  Reads a byte (0-255) from the Serial port and sets the LED on pin 9 to that brightness.
*/
const int ledPin = 9;

void setup() {
  Serial.begin(9600);
  pinMode(ledPin, OUTPUT);
}

void loop() {
  byte brightness;
  if (Serial.available()) {
    brightness = Serial.read();
    analogWrite(ledPin, brightness);
  }
}
""")
    L.led(9); L.upload("Each character you send in the Serial Monitor sets the brightness by its code: 'A' (65) is dim, 'z' (122) is brighter.")
    return L


def graph():
    L = Lesson("graph", "Graph", "Send a knob's reading to your computer and draw it as a graph.", D + "communication/Graph/", "Graph",
               requires=["analog-read-serial"], code="""
/*
  Graph
  Sends the reading of A0 over the Serial port — open Tools > Serial Plotter to see the graph.
*/
void setup() {
  Serial.begin(9600);
}

void loop() {
  Serial.println(analogRead(A0));
  delay(2);          // let the converter settle
}
""")
    L.pot("A0"); L.upload("Open Tools → Serial Plotter and turn the knob: the line goes up and down.")
    return L


def physical_pixel():
    L = Lesson("physical-pixel", "Physical Pixel", "Turn an LED on and off by typing H or L on your computer.", D + "communication/PhysicalPixel/",
               "Physical Pixel", requires=["blink"], code="""
/*
  Physical Pixel
  Turns the LED on pin 13 on when it receives 'H' over Serial, off with 'L'.
*/
const int ledPin = 13;
int incomingByte;

void setup() {
  Serial.begin(9600);
  pinMode(ledPin, OUTPUT);
}

void loop() {
  if (Serial.available() > 0) {
    incomingByte = Serial.read();
    if (incomingByte == 'H') {
      digitalWrite(ledPin, HIGH);
    }
    if (incomingByte == 'L') {
      digitalWrite(ledPin, LOW);
    }
  }
}
""")
    L.led(13); L.upload("In the Serial Monitor type H and press Enter: the LED turns on. Type L: it turns off.")
    return L


def virtual_color_mixer():
    L = Lesson("virtual-color-mixer", "Virtual Color Mixer", "Three knobs send red, green and blue values to your computer to mix a colour.",
               D + "communication/VirtualColorMixer/", "Virtual Color Mixer", requires=["analog-read-serial"], code="""
/*
  Virtual Color Mixer
  Sends three analog readings (A0, A1, A2) as comma-separated values for a computer program to mix a colour.
*/
const int redPin = A0;
const int greenPin = A1;
const int bluePin = A2;

void setup() {
  Serial.begin(9600);
}

void loop() {
  Serial.print(analogRead(redPin));
  Serial.print(",");
  Serial.print(analogRead(greenPin));
  Serial.print(",");
  Serial.println(analogRead(bluePin));
}
""")
    for pin in ("A0", "A1", "A2"):
        L.pot(pin)
    L.upload("The Serial Monitor shows three numbers, one per knob. (The official example then mixes them into a colour on your computer with Processing.)")
    return L


def serial_call_response(ascii_version):
    lid = "serial-call-response-ascii" if ascii_version else "serial-call-response"
    title = "Serial Call and Response ASCII" if ascii_version else "Serial Call and Response"
    url = D + ("communication/SerialCallResponseASCII/" if ascii_version else "communication/SerialCallResponse/")
    send = """    Serial.print(firstSensor);
    Serial.print(",");
    Serial.print(secondSensor);
    Serial.print(",");
    Serial.println(thirdSensor);""" if ascii_version else """    Serial.write(firstSensor);
    Serial.write(secondSensor);
    Serial.write(thirdSensor);"""
    L = Lesson(lid, title, "Wait for the computer to ask, then answer with two knob readings and a button's state.", url, title,
               requires=["digital-read-serial", "analog-read-serial"], code=f"""
/*
  {title}
  Sends three values (A0, A1 and the button on pin 2) every time the computer sends a byte.
*/
int firstSensor = 0;
int secondSensor = 0;
int thirdSensor = 0;
int inByte = 0;

void setup() {{
  Serial.begin(9600);
  while (!Serial) {{
  }}
  pinMode(2, INPUT);
  establishContact();
}}

void loop() {{
  if (Serial.available() > 0) {{
    inByte = Serial.read();
    firstSensor = analogRead(A0){'' if ascii_version else ' / 4'};
    delay(10);
    secondSensor = analogRead(A1){'' if ascii_version else ' / 4'};
    thirdSensor = {'digitalRead(2)' if ascii_version else 'map(digitalRead(2), 0, 1, 0, 255)'};
{send}
  }}
}}

void establishContact() {{
  while (Serial.available() <= 0) {{
    Serial.{'println("0,0,0")' if ascii_version else "print('A')"};
    delay(300);
  }}
}}
""")
    L.pot("A0"); L.pot("A1"); L.button(2)
    L.upload("The Arduino says hello until the computer answers. Type any letter in the Serial Monitor and it replies with the two knobs and the button.")
    return L


def arrays():
    L = Lesson("arrays", "Arrays", "Light six LEDs one after another, using a list (array) of pin numbers.", D + "control-structures/Arrays/", "Arrays",
               requires=["for-loop"], full_board=True, code="""
/*
  Arrays
  Lights LEDs on the pins listed in an array, forwards then backwards.
*/
int timer = 100;
int ledPins[] = { 2, 7, 4, 6, 5, 3 };   // an array of pin numbers, in any order
int pinCount = 6;

void setup() {
  for (int thisPin = 0; thisPin < pinCount; thisPin++) {
    pinMode(ledPins[thisPin], OUTPUT);
  }
}

void loop() {
  for (int thisPin = 0; thisPin < pinCount; thisPin++) {
    digitalWrite(ledPins[thisPin], HIGH);
    delay(timer);
    digitalWrite(ledPins[thisPin], LOW);
  }
  for (int thisPin = pinCount - 1; thisPin >= 0; thisPin--) {
    digitalWrite(ledPins[thisPin], HIGH);
    delay(timer);
    digitalWrite(ledPins[thisPin], LOW);
  }
}
""")
    for pin in (2, 3, 4, 5, 6, 7):
        L.led(pin)
    L.upload("The LEDs light one at a time in the order the array lists their pins — then back again.")
    return L


def for_loop():
    L = Lesson("for-loop", "For Loop (Knight Rider)", "Six LEDs light up one after another, back and forth — with a for loop.", D + "control-structures/ForLoopIteration/",
               "For Loop Iteration", requires=["blink"], full_board=True, fixed_pins=True, code="""
/*
  For Loop Iteration
  Lights the LEDs on pins 2 to 7 in turn, up and then back down.
*/
int timer = 100;

void setup() {
  for (int thisPin = 2; thisPin < 8; thisPin++) {
    pinMode(thisPin, OUTPUT);
  }
}

void loop() {
  for (int thisPin = 2; thisPin < 8; thisPin++) {
    digitalWrite(thisPin, HIGH);
    delay(timer);
    digitalWrite(thisPin, LOW);
  }
  for (int thisPin = 7; thisPin >= 2; thisPin--) {
    digitalWrite(thisPin, HIGH);
    delay(timer);
    digitalWrite(thisPin, LOW);
  }
}
""")
    for pin in (2, 3, 4, 5, 6, 7):
        L.led(pin)
    L.upload("A light runs back and forth along the LEDs, like the car in Knight Rider.")
    return L


def switch_case_serial():
    L = Lesson("switch-case-serial", "Switch Case (serial)", "Type a letter a–e to light one of five LEDs — using switch/case.", D + "control-structures/SwitchCase2/",
               "Switch Case 2", requires=["physical-pixel"], full_board=True, fixed_pins=True, code="""
/*
  Switch statement with serial input
  Sending a, b, c, d or e lights the LED on pin 2, 3, 4, 5 or 6; anything else turns them all off.
*/
void setup() {
  Serial.begin(9600);
  for (int thisPin = 2; thisPin < 7; thisPin++) {
    pinMode(thisPin, OUTPUT);
  }
}

void loop() {
  if (Serial.available() > 0) {
    int inByte = Serial.read();
    switch (inByte) {
      case 'a': digitalWrite(2, HIGH); break;
      case 'b': digitalWrite(3, HIGH); break;
      case 'c': digitalWrite(4, HIGH); break;
      case 'd': digitalWrite(5, HIGH); break;
      case 'e': digitalWrite(6, HIGH); break;
      default:
        for (int thisPin = 2; thisPin < 7; thisPin++) {
          digitalWrite(thisPin, LOW);
        }
    }
  }
}
""")
    for pin in (2, 3, 4, 5, 6):
        L.led(pin)
    L.upload("In the Serial Monitor type a, b, c, d or e: that LED lights. Any other letter turns them all off.")
    return L


def if_statement():
    L = Lesson("if-statement", "If Statement", "Light an LED only when a knob is turned past halfway — with if.", D + "control-structures/ifStatementConditional/",
               "If Statement (Conditional)", requires=["analog-read-serial"], code="""
/*
  Conditionals - If statement
  Lights the LED on pin 13 when the reading on A0 is above a threshold.
*/
const int analogPin = A0;
const int ledPin = 13;
const int threshold = 400;

void setup() {
  pinMode(ledPin, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  int analogValue = analogRead(analogPin);
  if (analogValue > threshold) {
    digitalWrite(ledPin, HIGH);
  } else {
    digitalWrite(ledPin, LOW);
  }
  Serial.println(analogValue);
  delay(1);
}
""")
    L.pot("A0"); L.led(13); L.upload("Turn the knob: once the reading passes 400 the LED turns on.")
    return L


LESSONS = [read_analog_voltage, fade, blink_without_delay, button, debounce, input_pullup, state_change, tone_melody, tone_multiple,
           analog_in_out, analog_input, fading, smoothing, dimmer, graph, physical_pixel, virtual_color_mixer,
           lambda: serial_call_response(False), lambda: serial_call_response(True), arrays, for_loop, switch_case_serial, if_statement]
