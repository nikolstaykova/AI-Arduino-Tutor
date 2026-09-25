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


# ---- light sensor (photoresistor) and force sensor (FSR) --------------------------------------
def pitch_follower():
    L = Lesson("pitch-follower", "Pitch Follower", "A light sensor sets the pitch of a buzzer: brighter light, higher note.", D + "digital/tonePitchFollower/",
               "Pitch Follower", requires=["tone-melody", "analog-read-serial"], code="""
/*
  Pitch follower
  Plays a pitch that changes with the light on the photoresistor (A0), on the buzzer on pin 9.
*/
void setup() {
  Serial.begin(9600);
}

void loop() {
  int sensorReading = analogRead(A0);
  Serial.println(sensorReading);                        // see your own light range here
  int thisPitch = map(sensorReading, 400, 1000, 120, 1500);
  tone(9, thisPitch, 10);
  delay(1);
}
""")
    L.sensor("ldr", "A0", ohms=4700); L.buzzer(9)
    L.upload("Wave your hand over the light sensor: the note goes down when it's darker and up when it's brighter.")
    return L


def calibration():
    L = Lesson("calibration", "Calibration", "For the first five seconds the Arduino learns the darkest and brightest light, then dims an LED to match.",
               D + "analog/Calibration/", "Calibration", requires=["analog-in-out-serial"], code="""
/*
  Calibration
  For 5 seconds after starting, records the lowest and highest readings of the light sensor on A0
  (the LED on pin 13 is on while it learns), then maps the light to the LED on pin 9's brightness.
*/
const int sensorPin = A0;
const int ledPin = 9;
const int indicatorPin = 13;
int sensorValue = 0;
int sensorMin = 1023;
int sensorMax = 0;

void setup() {
  pinMode(indicatorPin, OUTPUT);
  digitalWrite(indicatorPin, HIGH);          // learning…
  while (millis() < 5000) {
    sensorValue = analogRead(sensorPin);
    if (sensorValue > sensorMax) {
      sensorMax = sensorValue;
    }
    if (sensorValue < sensorMin) {
      sensorMin = sensorValue;
    }
  }
  digitalWrite(indicatorPin, LOW);           // done
}

void loop() {
  sensorValue = analogRead(sensorPin);
  sensorValue = constrain(sensorValue, sensorMin, sensorMax);
  sensorValue = map(sensorValue, sensorMin, sensorMax, 0, 255);
  analogWrite(ledPin, sensorValue);
}
""")
    L.sensor("ldr", "A0"); L.led(9); L.led(13, label="the second LED")
    L.upload("While the second LED is on (5 seconds), cover and uncover the light sensor. After that, the first LED follows the light.")
    return L


def switch_case_sensor():
    L = Lesson("switch-case-sensor", "Switch Case (sensor)", "Sort a light reading into dark, dim, medium or bright — with switch/case.", D + "control-structures/SwitchCase/",
               "Switch Case", requires=["if-statement"], code="""
/*
  Switch statement
  Reads the light sensor on A0 and prints dark, dim, medium or bright.
*/
const int sensorMin = 0;
const int sensorMax = 600;

void setup() {
  Serial.begin(9600);
}

void loop() {
  int sensorReading = analogRead(A0);
  int range = map(sensorReading, sensorMin, sensorMax, 0, 3);
  switch (range) {
    case 0: Serial.println("dark"); break;
    case 1: Serial.println("dim"); break;
    case 2: Serial.println("medium"); break;
    case 3: Serial.println("bright"); break;
  }
  delay(1);
}
""")
    L.sensor("ldr", "A0")
    L.upload("Open the Serial Monitor and cover the light sensor bit by bit: it goes from bright to medium, dim and dark.")
    return L


def while_loop():
    L = Lesson("while-loop", "While Loop", "Hold a button to re-calibrate a light sensor — the code stays in a while loop as long as you press.",
               D + "control-structures/WhileStatementConditional/", "While Statement Conditional", requires=["calibration", "button"], code="""
/*
  Conditionals - while statement
  While the button on pin 2 is pressed, the sketch calibrates the light sensor (the LED on 13 lights).
  Otherwise it sets the LED on pin 9 from the light.
*/
const int sensorPin = A0;
const int ledPin = 9;
const int indicatorLedPin = 13;
const int buttonPin = 2;
int sensorMin = 1023;
int sensorMax = 0;
int sensorValue = 0;

void setup() {
  pinMode(indicatorLedPin, OUTPUT);
  pinMode(ledPin, OUTPUT);
  pinMode(buttonPin, INPUT);
}

void loop() {
  while (digitalRead(buttonPin) == HIGH) {
    calibrate();
  }
  digitalWrite(indicatorLedPin, LOW);
  sensorValue = analogRead(sensorPin);
  sensorValue = map(sensorValue, sensorMin, sensorMax, 0, 255);
  sensorValue = constrain(sensorValue, 0, 255);
  analogWrite(ledPin, sensorValue);
}

void calibrate() {
  digitalWrite(indicatorLedPin, HIGH);
  sensorValue = analogRead(sensorPin);
  if (sensorValue > sensorMax) {
    sensorMax = sensorValue;
  }
  if (sensorValue < sensorMin) {
    sensorMin = sensorValue;
  }
}
""")
    L.sensor("ldr", "A0"); L.button(2); L.led(9); L.led(13, label="the second LED")
    L.upload("Hold the button and cover and uncover the light sensor (the second LED is on while you hold). Let go: the first LED follows the light.")
    return L


def tone_keyboard():
    L = Lesson("tone-keyboard", "Tone Keyboard", "Three force sensors are keys: press one and the buzzer plays its note.", D + "digital/toneKeyboard/",
               "Tone Keyboard", requires=["tone-melody"], fixed_pins=True, code="""
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
""")
    for pin in ("A0", "A1", "A2"):
        L.sensor("fsr", pin)
    L.buzzer(8)
    L.upload("Press each force sensor: each one plays its own note.")
    return L


LESSONS += [pitch_follower, calibration, switch_case_sensor, while_loop, tone_keyboard]


# ---- sensors world + RGB ------------------------------------------------------------------------
def knock():
    L = Lesson("knock", "Knock", "A piezo feels a knock on the table: each knock toggles an LED and prints “Knock!”.", D + "sensors/Knock/", "Knock",
               requires=["analog-read-serial"], code="""
/*
  Knock Sensor
  Reads the piezo on A0; a reading above the threshold counts as a knock and toggles the LED on pin 13.
*/
const int ledPin = 13;
const int knockSensor = A0;
const int threshold = 100;
int sensorReading = 0;
int ledState = LOW;

void setup() {
  pinMode(ledPin, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  sensorReading = analogRead(knockSensor);
  if (sensorReading >= threshold) {
    ledState = !ledState;
    digitalWrite(ledPin, ledState);
    Serial.println("Knock!");
  }
  delay(100);          // don't count one knock twice
}
""")
    L.knock("A0"); L.led(13)
    L.upload("Knock on the table next to the piezo: the LED switches and the Serial Monitor says Knock!")
    return L


def ping():
    L = Lesson("ping", "Ping Range Finder", "Measure how far away things are with an ultrasonic sensor — it pings and times the echo.", D + "sensors/Ping/",
               "Ping", requires=["digital-read-serial"], code="""
/*
  Ping))) Sensor
  Sends a ping from the sensor on pin 7, times the echo and prints the distance.
*/
const int pingPin = 7;

void setup() {
  Serial.begin(9600);
}

void loop() {
  long duration, inches, cm;
  // a short HIGH pulse starts a ping
  pinMode(pingPin, OUTPUT);
  digitalWrite(pingPin, LOW);
  delayMicroseconds(2);
  digitalWrite(pingPin, HIGH);
  delayMicroseconds(5);
  digitalWrite(pingPin, LOW);
  // the same pin then listens: the echo pulse is as long as the sound took to come back
  pinMode(pingPin, INPUT);
  duration = pulseIn(pingPin, HIGH);
  inches = microsecondsToInches(duration);
  cm = microsecondsToCentimeters(duration);
  Serial.print(inches);
  Serial.print("in, ");
  Serial.print(cm);
  Serial.print("cm");
  Serial.println();
  delay(100);
}

long microsecondsToInches(long microseconds) {
  return microseconds / 74 / 2;      // sound: 74 µs per inch, there and back
}

long microsecondsToCentimeters(long microseconds) {
  return microseconds / 29 / 2;      // 29 µs per cm, there and back
}
""")
    L.module("cq-ping", "ping-sensor", "ping", "Ping sensor", {"GND": "gnd", "5V": "5v", "SIG": "7"},
             place_note=", its three pins in three columns (the “eyes” facing you)", pin_words={"SIG": "SIG"})
    L.upload("Open the Serial Monitor and move your hand in front of the sensor: the distance changes.")
    return L


def adxl3xx():
    L = Lesson("adxl3xx", "ADXL3xx Accelerometer", "Read tilt in three directions from an analog accelerometer.", D + "sensors/ADXL3xx/", "ADXL3xx",
               requires=["analog-read-serial"], code="""
/*
  ADXL3xx
  Reads the X, Y and Z outputs of an ADXL3xx accelerometer (A3, A2, A1) and prints them.
  (Arduino's example plugs the board straight into A0-A5 and powers it from A4/A5 set as outputs;
  here it's wired to 3.3V and GND with jumper wires instead.)
*/
const int xpin = A3;
const int ypin = A2;
const int zpin = A1;

void setup() {
  Serial.begin(9600);
}

void loop() {
  Serial.print(analogRead(xpin));
  Serial.print("\\t");
  Serial.print(analogRead(ypin));
  Serial.print("\\t");
  Serial.print(analogRead(zpin));
  Serial.println();
  delay(100);
}
""")
    L.module("cq-adxl335", "adxl335", "acc", "accelerometer", {"VCC": "3v3", "GND": "gnd", "X": "A3", "Y": "A2", "Z": "A1", "ST": None},
             place_note=", its six pins in six columns")
    L.upload("Open the Serial Monitor and tilt the breadboard: the three numbers change.")
    return L


def memsic2125():
    L = Lesson("memsic2125", "Memsic 2125 Accelerometer", "A tilt sensor that talks in pulses — measure them with pulseIn().", D + "sensors/Memsic2125/",
               "Memsic 2125", requires=["digital-read-serial"], code="""
/*
  Memsic2125
  Reads the X and Y pulse outputs of a Memsic 2125 (pins 2 and 3) and prints the acceleration in milli-g.
*/
const int xPin = 2;
const int yPin = 3;

void setup() {
  Serial.begin(9600);
  pinMode(xPin, INPUT);
  pinMode(yPin, INPUT);
}

void loop() {
  int pulseX, pulseY;
  int accelerationX, accelerationY;
  pulseX = pulseIn(xPin, HIGH);
  pulseY = pulseIn(yPin, HIGH);
  // 5000 µs pulses mean level; each 12.5 µs more or less is 1 milli-g
  accelerationX = ((pulseX / 10) - 500) * 8;
  accelerationY = ((pulseY / 10) - 500) * 8;
  Serial.print(accelerationX);
  Serial.print("\\t");
  Serial.print(accelerationY);
  Serial.println();
  delay(100);
}
""")
    L.module("cq-memsic2125", "memsic2125", "acc", "Memsic 2125", {"VDD": "5v", "GND.1": "gnd", "GND.2": "gnd", "XOUT": "2", "YOUT": "3", "TOUT": None},
             place_note=" across the middle gap, like a chip: three pins above, three below", straddle=True,
             pin_words={"XOUT": "Xout", "YOUT": "Yout", "VDD": "Vdd", "GND.1": "first GND", "GND.2": "second GND"})
    L.upload("Open the Serial Monitor and tilt the breadboard: the two numbers show the tilt in milli-g.")
    return L


def read_ascii_string():
    L = Lesson("read-ascii-string", "Read ASCII String", "Type three numbers to mix a colour on an RGB LED.", D + "communication/ReadASCIIString/",
               "Read ASCII String", requires=["fade", "physical-pixel"], code="""
/*
  Reading a serial ASCII-encoded string
  Reads three comma-separated numbers (0-255) and sets a common-anode RGB LED's colour on pins 3, 5, 6.
*/
const int redPin = 3;
const int greenPin = 5;
const int bluePin = 6;

void setup() {
  Serial.begin(9600);
  pinMode(redPin, OUTPUT);
  pinMode(greenPin, OUTPUT);
  pinMode(bluePin, OUTPUT);
}

void loop() {
  while (Serial.available() > 0) {
    int red = Serial.parseInt();
    int green = Serial.parseInt();
    int blue = Serial.parseInt();
    if (Serial.read() == '\\n') {
      // common anode: 0 is full brightness, 255 is off
      red = 255 - constrain(red, 0, 255);
      green = 255 - constrain(green, 0, 255);
      blue = 255 - constrain(blue, 0, 255);
      analogWrite(redPin, red);
      analogWrite(greenPin, green);
      analogWrite(bluePin, blue);
      Serial.print(red, HEX);
      Serial.print(green, HEX);
      Serial.println(blue, HEX);
    }
  }
}
""")
    L.rgb(3, 5, 6)
    L.upload("In the Serial Monitor (set to 'Newline') type three numbers like 255,0,128 and press Enter: the LED mixes that colour.")
    return L


LESSONS += [knock, ping, adxl3xx, memsic2125, read_ascii_string]


# ---- display world ------------------------------------------------------------------------------
def led_bar_graph():
    L = Lesson("led-bar-graph", "LED Bar Graph", "Turn a knob and watch a 10-segment bar graph fill up like a level meter.", D + "display/BarGraph/",
               "LED Bar Graph", requires=["arrays", "analog-input"], code="""
/*
  LED bar graph
  Turns on a series of LEDs based on the value of the knob on A0 — a level meter.
*/
const int analogPin = A0;
const int ledCount = 10;
int ledPins[] = { 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 };

void setup() {
  for (int thisLed = 0; thisLed < ledCount; thisLed++) {
    pinMode(ledPins[thisLed], OUTPUT);
  }
}

void loop() {
  int sensorReading = analogRead(analogPin);
  int ledLevel = map(sensorReading, 0, 1023, 0, ledCount);
  for (int thisLed = 0; thisLed < ledCount; thisLed++) {
    if (thisLed < ledLevel) {
      digitalWrite(ledPins[thisLed], HIGH);
    } else {
      digitalWrite(ledPins[thisLed], LOW);
    }
  }
}
""")
    L.bargraph([2, 3, 4, 5, 6, 7, 8, 9, 10, 11]); L.pot("A0")
    L.upload("Turn the knob: the bar fills up from one end to the other.")
    return L


LESSONS += [led_bar_graph]


def row_column_scanning():
    L = Lesson("row-column-scanning", "8x8 LED Matrix", "Two knobs move a dot around an 8×8 LED matrix — lit by scanning its rows fast.",
               D + "display/RowColumnScanning/", "Row-Column Scanning", requires=["led-bar-graph", "arrays"], code="""
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
""", full_board=True)
    L.matrix([2, 7, "A5", 5, 13, "A4", 12, "A2"], [6, 11, 10, 3, "A3", 4, 8, 9]); L.pot("A0"); L.pot("A1")
    L.upload("Turn the two knobs: the lit dot moves around the matrix — one knob left–right, the other up–down.")
    return L


LESSONS += [row_column_scanning]


def midi():
    L = Lesson("midi", "MIDI Note Player", "Play a run of notes on a keyboard or synth over a MIDI cable.", D + "communication/Midi/", "MIDI Note Player",
               requires=["tone-melody"], code="""
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
""")
    L.midi()
    L.upload("Plug a MIDI cable from the socket into a keyboard or a USB-MIDI adapter: it plays a rising run of notes.")
    return L


LESSONS += [midi]
