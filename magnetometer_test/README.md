# Live magnetometer plot

The ESP32 sends one `x,y,z` CSV row per measurement over USB serial at
115200 baud. Values are in microteslas (µT). Lines beginning with `#` are
status/error messages; the Python script shows them without plotting them.
The plot shows X, Y, and Z together over the latest 20 seconds and scales
the vertical axis automatically.

## Run on Windows

1. Open `magnetometer_test.ino` in Arduino IDE and upload it to your ESP32.
   Keep the existing Adafruit MLX90393 library installed. Wiring is unchanged:
   SDA GPIO 22, SCL GPIO 19, I2C address `0x18`.
2. Close Arduino Serial Monitor and Serial Plotter to release the serial port.
3. Open PowerShell in this folder and run:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe plot_magnetometer.py --list-ports
   .\.venv\Scripts\python.exe plot_magnetometer.py --port COM5
   ```

   Replace `COM5` with your ESP32's port (also shown in Arduino IDE's Tools >
   Port menu). If exactly one serial port is available, `--port` can be omitted.
   On macOS/Linux, use `.venv/bin/python` and the appropriate serial device path.
4. Move a magnet near the sensor to see the three traces change. Close the plot
   window or press Ctrl+C in the terminal to stop.

Use `--window 60` for a 60-second view. The default baud rate matches the sketch;
if you change `Serial.begin(...)`, also pass the matching `--baud` value.
Opening the port can reset the ESP32; allow a few seconds for startup. The
horizontal axis uses host receipt time, not a hardware acquisition timestamp.

If no readings appear, check the terminal and the message at the top left of the
plot for sensor errors, confirm the correct port/baud and uploaded sketch, and
check wiring. After unplugging/reconnecting the board, restart the script.
After five seconds without readings, the plot explains whether no bytes arrived
or data arrived without usable XYZ readings. Add `--debug` to print the exact
incoming lines in the terminal. If no bytes arrive, try pressing the ESP32's
RESET/EN button with the Python plot open.

The Python reader also accepts the original sketch's labeled output, either
three separate `X: ... uT` / `Y: ... uT` / `Z: ... uT` lines or a single line
containing all three axes, so it can plot firmware already on the board.

The sketch waits 50 ms after each measurement; sensor conversion adds more time,
so this is not an exact 20 Hz sample rate. Adjust `SAMPLE_INTERVAL_MS` in the
sketch to change that delay.

`backup.ino.bak` preserves the original sketch. The `.bak` extension keeps Arduino
from compiling its duplicate `setup()` and `loop()` functions.

API references: [pySerial](https://pyserial.readthedocs.io/en/latest/pyserial_api.html)
and [Matplotlib animation](https://matplotlib.org/stable/api/animation_api.html).
