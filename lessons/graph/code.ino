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
