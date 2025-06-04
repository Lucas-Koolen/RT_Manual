#include <Wire.h>
#include <Adafruit_PWMServoDriver.h>

Adafruit_PWMServoDriver pwm = Adafruit_PWMServoDriver();

// --- Stopwaarden per servo ---
#define SERVO_STOP_DEFAULT  365 // standaard
#define SERVO_STOP_SERVO5   367  // Lopende Band 2
#define SERVO_STOP_SERVO6   366  // Pusher 2
#define SERVO_STOP_SERVO7   368  // Draaitafel 2

#define SERVO_PWM_MOVE      200
#define POS_MIN             90
#define POS_MAX             530

// --- Sensor pinmapping ---
#define PUSHER1_ENDSTOP_PIN 8    // NC
#define PUSHER2_ENDSTOP_PIN 9    // NC
#define BEAM_SENSOR1_PIN    4    // NO (LOW = gebroken)
#define BEAM_SENSOR2_PIN    5    // NO

// --- PWM stopwaarden per servo-index ---
int custom_pwm[9] = {
  SERVO_STOP_DEFAULT,  // 0 - Lopende Band 1
  SERVO_STOP_DEFAULT,  // 1 - Draaitafel 1
  SERVO_STOP_DEFAULT,  // 2 - Pusher 1
  SERVO_STOP_DEFAULT,  // 3 - L1 (positioneel)
  SERVO_STOP_DEFAULT,  // 4 - L2 (positioneel)
  SERVO_STOP_SERVO5,   // 5 - Lopende Band 2 (gekalibreerd)
  SERVO_STOP_SERVO6,   // 6 - Pusher 2 (gekalibreerd)
  SERVO_STOP_SERVO7,   // 7 - Draaitafel 2 (aparte waarde)
  SERVO_STOP_DEFAULT   // 8 - Reserve / toekomstig gebruik
};



String inputString = "";
bool lastEndstop1 = false;
bool lastEndstop2 = false;
bool lastBeam1 = false;
bool lastBeam2 = false;

void setup() {
  Serial.begin(9600);
  pwm.begin();
  pwm.setPWMFreq(60);

  pinMode(PUSHER1_ENDSTOP_PIN, INPUT_PULLUP);
  pinMode(PUSHER2_ENDSTOP_PIN, INPUT_PULLUP);
  pinMode(BEAM_SENSOR1_PIN, INPUT_PULLUP);
  pinMode(BEAM_SENSOR2_PIN, INPUT_PULLUP);

  lastEndstop1 = digitalRead(PUSHER1_ENDSTOP_PIN) == HIGH;
  lastEndstop2 = digitalRead(PUSHER2_ENDSTOP_PIN) == HIGH;
  lastBeam1 = digitalRead(BEAM_SENSOR1_PIN) == LOW;
  lastBeam2 = digitalRead(BEAM_SENSOR2_PIN) == LOW;

  Serial.println("READY");
}

void loop() {
  checkBeamSensors();
  checkEndstops();
  handleSerial();
  delay(50);
}

void checkBeamSensors() {
  bool currentBeam1 = digitalRead(BEAM_SENSOR1_PIN) == LOW;
  bool currentBeam2 = digitalRead(BEAM_SENSOR2_PIN) == LOW;

  if (currentBeam1 != lastBeam1) {
    lastBeam1 = currentBeam1;
    Serial.println(currentBeam1 ? "b11" : "b10");
  }
  if (currentBeam2 != lastBeam2) {
    lastBeam2 = currentBeam2;
    Serial.println(currentBeam2 ? "b21" : "b20");
  }
}

void checkEndstops() {
  bool current1 = digitalRead(PUSHER1_ENDSTOP_PIN) == HIGH;
  bool current2 = digitalRead(PUSHER2_ENDSTOP_PIN) == HIGH;

  if (!lastEndstop1 && current1) {
    pwm.setPWM(2, 0, custom_pwm[2]);
    Serial.println("STOP2");
  }
  if (lastEndstop1 && !current1) {
    Serial.println("GO2");
  }

  if (!lastEndstop2 && current2) {
    pwm.setPWM(6, 0, custom_pwm[6]);
    Serial.println("STOP6");
  }
  if (lastEndstop2 && !current2) {
    Serial.println("GO6");
  }

  lastEndstop1 = current1;
  lastEndstop2 = current2;
}

void handleSerial() {
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    if (inChar == '\n' || inChar == '\r') {
      processCommand(inputString);
      inputString = "";
    } else {
      inputString += inChar;
    }
  }
}

void processCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;

  Serial.print("CMD: ");
  Serial.println(cmd);

  if (cmd.startsWith("SET")) {
    int s1 = cmd.indexOf(' ');
    int s2 = cmd.indexOf(' ', s1 + 1);
    int s3 = cmd.indexOf(' ', s2 + 1);
    int servoNum = cmd.substring(s1 + 1, s2).toInt();

    String action;
    int duration = 0;

    if (s3 > 0) {
      action = cmd.substring(s2 + 1, s3);
      duration = cmd.substring(s3 + 1).toInt();
    } else {
      action = cmd.substring(s2 + 1);
    }

    if (action == "FWD") {
      if (servoNum == 2 || servoNum == 6) {
        pwm.setPWM(servoNum, 0, SERVO_PWM_MOVE);
        delay(duration > 0 ? duration : 500);
        pwm.setPWM(servoNum, 0, custom_pwm[servoNum]);
      } else {
        pwm.setPWM(servoNum, 0, 730 - SERVO_PWM_MOVE);
      }
    }

    else if (action == "REV") {
      if (servoNum == 2 || servoNum == 6) {
        pwm.setPWM(servoNum, 0, 730 - SERVO_PWM_MOVE);
        while (true) {
          if ((servoNum == 2 && digitalRead(PUSHER1_ENDSTOP_PIN) == HIGH) ||
              (servoNum == 6 && digitalRead(PUSHER2_ENDSTOP_PIN) == HIGH)) {
            break;
          }
        }
        pwm.setPWM(servoNum, 0, custom_pwm[servoNum]);
      } else {
        pwm.setPWM(servoNum, 0, SERVO_PWM_MOVE);
      }
    }

    else if (action == "STOP") {
      pwm.setPWM(servoNum, 0, custom_pwm[servoNum]);
    }
  }

  else if (cmd.startsWith("POS")) {
    int s1 = cmd.indexOf(' ');
    int s2 = cmd.indexOf(' ', s1 + 1);
    int servoNum = cmd.substring(s1 + 1, s2).toInt();
    int degrees = cmd.substring(s2 + 1).toInt();
    degrees = constrain(degrees, 0, 210);
    int pulse = map(degrees, 0, 180, POS_MIN, POS_MAX);
    pwm.setPWM(servoNum, 0, pulse);
  }

  else if (cmd.startsWith("CAL")) {
    int s1 = cmd.indexOf(' ');
    int s2 = cmd.indexOf(' ', s1 + 1);
    int servoNum = cmd.substring(s1 + 1, s2).toInt();
    int pwmVal = cmd.substring(s2 + 1).toInt();
    if (pwmVal >= 100 && pwmVal <= 530) {
      custom_pwm[servoNum] = pwmVal;
    }
  }

  else if (cmd.startsWith("ROTATE")) {
    int s1 = cmd.indexOf(' ');
    int s2 = cmd.indexOf(' ', s1 + 1);
    int s3 = cmd.indexOf(' ', s2 + 1);
    int servoNum = cmd.substring(s1 + 1, s2).toInt();
    int degrees = cmd.substring(s2 + 1, s3).toInt();
    String dir = cmd.substring(s3 + 1);
    int timeMs = map(abs(degrees), 0, 360, 0, 1560);
    int pwmVal = SERVO_PWM_MOVE;

    if (dir == "FWD") pwm.setPWM(servoNum, 0, 730 - pwmVal);
    else if (dir == "REV") pwm.setPWM(servoNum, 0, pwmVal);
    else return;

    delay(timeMs);
    pwm.setPWM(servoNum, 0, custom_pwm[servoNum]);
  }
}
