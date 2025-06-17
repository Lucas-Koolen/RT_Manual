import sys
import serial
import time
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QLineEdit, QTextEdit, QGroupBox, QDialog
)
from PyQt5.QtCore import QTimer, Qt

class UltraCalDashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.l2_position = None  # Tracks position of L2 (servo 4)
        self.setWindowTitle("Ultra Calibration Dashboard")
        self.resize(1200, 900)
        self.setup_stylesheet()

        # Serial connection
        try:
            self.ser = serial.Serial('COM7', 9600, timeout=1)
            time.sleep(2)
        except serial.SerialException:
            sys.exit(1)

        self.active_buttons = {}
        self.auto_stop_timers = {}
        self.init_ui()
        self.show_safety_popup()

        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_from_serial)
        self.status_timer.start(200)

    def setup_stylesheet(self):
        self.setStyleSheet("""
            * { font-size: 14pt; font-family: Arial; }
            QWidget { background-color: #2b2b2b; color: #f0f0f0; }
            QPushButton {
                background-color: #3c3f41; border: 1px solid #555;
                border-radius: 6px; padding: 8px 16px; color: #ffffff;
            }
            QPushButton:hover { background-color: #ffaa40; color: #000000; }
            QPushButton:pressed, QPushButton[active="true"] {
                background-color: #ffaa00; color: #000000;
                font-size: 18pt; padding: 12px 24px;
            }
            QLineEdit, QTextEdit {
                background-color: #2b2b2b; color: #f0f0f0;
                border: 1px solid #555; border-radius: 6px; padding: 6px;
            }
            QLineEdit[echoMode="0"]::placeholder,
            QLineEdit::placeholder,
            QTextEdit::placeholder {
                color: #ffaa00;
            }
            QGroupBox {
                min-height: 80px; border: 1px solid #555; border-radius: 8px;
                background-color: #1e1e1e; margin-top: 10px; padding: 10px;
            }
            QGroupBox:title {
                subcontrol-origin: margin; subcontrol-position: top center;
                padding: 0 6px; color: #ffaa00; font-weight: bold;
            }
            QLabel {
                color: #dddddd; font-size: 14pt;
                padding: 6px; border-radius: 6px;
            }
            QLabel[active="true"] {
                background-color: #ffaa00; color: #000000;
            }
        """)

    def init_ui(self):
        layout = QVBoxLayout()
        layout.addLayout(self.create_servo_row([(0, "Conveyor 1"), (5, "Conveyor 2")], self.add_directional_controls))
        layout.addLayout(self.create_servo_row([(2, "Pusher 1"), (6, "Pusher 2")], self.add_pusher_controls))
        layout.addLayout(self.create_servo_row([(1, "Turntable 1"), (7, "Turntable 2")], self.add_rotation_controls))
        layout.addLayout(self.create_servo_row([(3, "L1 (degrees)"), (4, "L2 (degrees)")], self.add_fixed_position_controls))

        layout.addWidget(self.build_sensor_panel())
        layout.addWidget(QLabel("Log:"))
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)
        self.setLayout(layout)

    def create_servo_row(self, servo_defs, control_func):
        row = QHBoxLayout()
        row.setSpacing(30)
        for servo_num, name in servo_defs:
            group = QGroupBox(f"{name} (Servo {servo_num})")
            group_layout = QVBoxLayout()
            group_layout.addLayout(control_func(servo_num))
            group.setLayout(group_layout)
            row.addWidget(group)
        return row

    def build_sensor_panel(self):
        self.sensor_group = QGroupBox("Sensors")
        self.sensor_layout = QHBoxLayout()

        left_column = QVBoxLayout()
        beam_group = QGroupBox("Beam Sensors")
        beam_layout = QHBoxLayout()
        self.beam1_label = QLabel("Beam Sensor 1: unknown")
        self.beam2_label = QLabel("Beam Sensor 2: unknown")
        beam_layout.addWidget(self.beam1_label)
        beam_layout.addWidget(self.beam2_label)
        beam_group.setLayout(beam_layout)

        limit_group = QGroupBox("Limit Switches")
        limit_layout = QHBoxLayout()
        self.limit1_label = QLabel("Limit Switch 1: unknown")
        self.limit2_label = QLabel("Limit Switch 2: unknown")
        limit_layout.addWidget(self.limit1_label)
        limit_layout.addWidget(self.limit2_label)
        limit_group.setLayout(limit_layout)

        left_column.addWidget(beam_group)
        left_column.addWidget(limit_group)

        right_column = QVBoxLayout()
        height_group = QGroupBox("Height Sensor")
        height_layout = QVBoxLayout()
        self.height_label = QLabel("Height: unknown")
        height_layout.addWidget(self.height_label)
        height_group.setLayout(height_layout)
        right_column.addWidget(height_group)

        self.sensor_layout.addLayout(left_column)
        self.sensor_layout.addLayout(right_column)
        self.sensor_group.setLayout(self.sensor_layout)
        return self.sensor_group

    def log(self, message):
        self.log_output.append(message)

    def send_command(self, cmd):
        try:
            if cmd.startswith("POS 4"):
                try:
                    self.l2_position = int(cmd.split()[2])
                    self.log(f"L2 position updated to {self.l2_position}")
                except ValueError:
                    self.log("ERROR: Invalid POS 4 value")

            full_cmd = cmd.strip() + "\r\n"
            self.ser.write(full_cmd.encode('utf-8'))
            self.log(f"Sent: {cmd}")
        except serial.SerialException as e:
            self.log(f"ERROR sending: {e}")

    def show_safety_popup(self):
        popup = QDialog(self)
        popup.setWindowTitle("Safety Check")
        popup.setModal(True)
        popup.setStyleSheet(self.styleSheet())

        layout = QVBoxLayout()
        label = QLabel("Are L1, L2, and Conveyor 5 L-Clear?\nIf not, please L-Clear the area.")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)

        confirm_button = QPushButton("Confirm: area is L-Clear")
        confirm_button.clicked.connect(lambda: self.perform_safety_sequence(popup))
        layout.addWidget(confirm_button)

        popup.setLayout(layout)
        popup.exec_()

    def perform_safety_sequence(self, popup):
        self.send_command("SET 5 FWD")
        self.send_command("POS 3 0")
        self.set_L_position_button_active(3, 0)
        self.send_command("POS 4 200")
        self.set_L_position_button_active(4, 200)
        QTimer.singleShot(1000, lambda: self.send_command("SET 5 STOP"))
        popup.accept()

    def set_L_position_button_active(self, servo, angle):
        if servo not in self.active_buttons:
            return
        for btn in self.active_buttons[servo]:
            label = btn.text().lower()
            if (servo == 3 and angle == 0 and "l-clear" in label) or \
               (servo == 4 and angle == 200 and "l-clear" in label):
                btn.setStyleSheet("background-color: #ffaa00; color: black;")
            else:
                btn.setStyleSheet("")

#____________________________________________________________
    def add_directional_controls(self, servo):
        row = QHBoxLayout()
        self.active_buttons[servo] = []

        def handle_click(btn, c):
            for b in self.active_buttons[servo]:
                b.setStyleSheet("")
            btn.setStyleSheet("background-color: #ffaa00; color: black; font-size: 16pt; padding: 10px 20px;")
            self.send_command(f"SET {servo} {c}")

        for label, cmd in [("Forewards", "FWD"), ("Backwards", "REV"), ("Stop", "STOP")]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, b=btn, c=cmd: handle_click(b, c))
            self.active_buttons[servo].append(btn)
            row.addWidget(btn)
        return row

    def add_rotation_controls(self, servo):
        row = QHBoxLayout()
        angle_input = QLineEdit()
        angle_input.setPlaceholderText("Graden (-360 tot 360)")
        angle_input.setStyleSheet("QLineEdit::placeholder { color: #ffcc80; }")

        btn_fwd = QPushButton("Turn FWD")
        btn_rev = QPushButton("Turn REV")

        def rotate(direction, btn):
            angle_text = angle_input.text()
            try:
                degrees = abs(int(angle_text))
            except ValueError:
                self.log("Ongeldige invoer voor graden.")
                return

            duration_ms = int((degrees / 360) * 1600)
            btn.setStyleSheet("background-color: #ffaa00; color: black; font-size: 16pt; padding: 10px 20px;")
            self.send_command(f"ROTATE {servo} {degrees} {direction}")

            if servo in [1, 7]:
                QTimer.singleShot(duration_ms, lambda: btn.setStyleSheet(""))
            else:
                btn.setStyleSheet("")

        btn_fwd.clicked.connect(lambda: rotate("FWD", btn_fwd))
        btn_rev.clicked.connect(lambda: rotate("REV", btn_rev))

        row.addWidget(angle_input)
        row.addWidget(btn_fwd)
        row.addWidget(btn_rev)
        return row

    def add_fixed_position_controls(self, servo):
        row = QHBoxLayout()
        self.active_buttons[servo] = []

        if servo == 3:
            pos_dict = {"Clear": 0, "Box Enter": 110, "Box Out": 185}
        elif servo == 4:
            pos_dict = {"Clear": 200, "Box Enter": 10.0, "Box Out": 100}
        else:
            pos_dict = {}

        def handle_click(btn, angle):
            for b in self.active_buttons[servo]:
                b.setStyleSheet("")
            btn.setStyleSheet("background-color: #ffaa00; color: black;")
            self.send_command(f"POS {servo} {angle}")

        for label, angle in pos_dict.items():
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, b=btn, a=angle: handle_click(b, a))
            self.active_buttons[servo].append(btn)
            row.addWidget(btn)
        return row


    def add_pusher_controls(self, servo):
        row = QHBoxLayout()
        time_input = QLineEdit()
        time_input.setPlaceholderText("ms voor Forwards (Push away)")
        time_input.setStyleSheet("QLineEdit::placeholder { color: #ffcc80; }")

        btn_fwd = QPushButton("Forwards (time)")
        btn_rev = QPushButton("Backwards (auto-stop)")
        btn_stop = QPushButton("Stop")

        self.active_buttons[servo] = [btn_fwd, btn_rev]

        def handle_pusher_click(btn, command):
            if servo == 6 and self.l2_position != 200:
                self.log("Pusher 2 geblokkeerd: L2 staat niet op 'Weg'")
                return

            for b in self.active_buttons[servo]:
                b.setStyleSheet("")
            btn.setStyleSheet("background-color: #ffaa00; color: black; font-size: 16pt; padding: 10px 20px;")
            self.send_command(command)

            if "FWD" in command:
                try:
                    duration = int(command.split()[3])
                    QTimer.singleShot(duration, lambda: btn.setStyleSheet(""))
                except:
                    pass

        def reset_pusher_buttons():
            for b in self.active_buttons[servo]:
                b.setStyleSheet("")
            self.send_command(f"SET {servo} STOP")

        btn_fwd.clicked.connect(lambda: handle_pusher_click(btn_fwd, f"SET {servo} FWD {time_input.text()}"))
        btn_rev.clicked.connect(lambda: handle_pusher_click(btn_rev, f"SET {servo} REV"))
        btn_stop.clicked.connect(lambda: reset_pusher_buttons())

        row.addWidget(time_input)
        row.addWidget(btn_fwd)
        row.addWidget(btn_rev)
        row.addWidget(btn_stop)

        if servo == 6:
            self.pusher2_buttons = [btn_fwd, btn_rev]
            self.update_pusher2_state()

        return row

    def update_pusher2_state(self):
        if hasattr(self, "pusher2_buttons"):
            state = self.l2_position == 200
            for btn in self.pusher2_buttons:
                btn.setEnabled(state)
                if not state:
                    btn.setStyleSheet("background-color: #555555; color: #aaaaaa;")
                else:
                    btn.setStyleSheet("")


    def update_from_serial(self):
        try:
            while self.ser.in_waiting:
                line = self.ser.readline().decode().strip()
                if line:
                    self.log(f"Ontvangen: {line}")
                if line == "b10":
                    self.beam1_label.setText("Beam sensor 1: NOT BROKEN")
                    self.beam1_label.setProperty("active", False)
                    self.beam1_label.setStyle(self.beam1_label.style())
                elif line == "b11":
                    self.beam1_label.setText("Beam sensor 1: BROKEN")
                    self.beam1_label.setProperty("active", True)
                    self.beam1_label.setStyle(self.beam1_label.style())
                elif line == "b20":
                    self.beam2_label.setText("Beam sensor 2: NOT BROKEN")
                    self.beam2_label.setProperty("active", False)
                    self.beam2_label.setStyle(self.beam2_label.style())
                elif line == "b21":
                    self.beam2_label.setText("Beam sensor 2: BROKEN")
                    self.beam2_label.setProperty("active", True)
                    self.beam2_label.setStyle(self.beam2_label.style())
                elif line == "STOP2":
                    self.limit1_label.setText("Limit switch 1: PRESSED")
                    self.limit1_label.setProperty("active", True)
                    self.limit1_label.setStyle(self.limit1_label.style())
                elif line == "STOP6":
                    self.limit2_label.setText("Limit switch 2: PRESSED")
                    self.limit2_label.setProperty("active", True)
                    self.limit2_label.setStyle(self.limit2_label.style())
                elif line == "GO2":
                    self.limit1_label.setText("Limit switch 1: NOT PRESSED")
                    self.limit1_label.setProperty("active", False)
                    self.limit1_label.setStyle(self.limit1_label.style())
                elif line == "GO6":
                    self.limit2_label.setText("Limit switch 2: NOT PRESSED")
                    self.limit2_label.setProperty("active", False)
                    self.limit2_label.setStyle(self.limit2_label.style())

            self.update_pusher2_state()  # live update Pusher 2 beschikbaarheid

        except Exception as e:
            self.log(f"FOUT: {e}")

        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = UltraCalDashboard()
    window.show()
    sys.exit(app.exec_())