"""Plot newline-delimited x,y,z readings from magnetometer_test.ino."""

import argparse
from collections import deque
import math
import re
import sys
import time


def parse_sample(line):
    """Ignore comments, boot messages, malformed rows, and nonfinite values."""
    fields = line.strip().split(",")
    if len(fields) != 3:
        return None
    try:
        values = tuple(float(field) for field in fields)
    except ValueError:
        return None
    return values if all(math.isfinite(value) for value in values) else None


def positive_number(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a positive finite number")
    return number


class SampleParser:
    """Accept CSV and both labeled formats emitted by the original sketch."""

    def __init__(self):
        self.axes = {}

    def parse(self, line):
        sample = parse_sample(line)
        if sample is not None:
            self.axes.clear()
            return sample
        for axis, value in re.findall(
                r"\b([XYZ]):\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)",
                line):
            if axis == "X":
                self.axes.clear()
            self.axes[axis] = float(value)
        if all(axis in self.axes for axis in "XYZ"):
            sample = tuple(self.axes[axis] for axis in "XYZ")
            self.axes.clear()
            if all(math.isfinite(value) for value in sample):
                return sample
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", help="ESP32 serial port, for example COM5")
    parser.add_argument("--list-ports", action="store_true", help="list ports and exit")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--debug", action="store_true",
                        help="print incoming serial lines for troubleshooting")
    parser.add_argument("--window", type=positive_number, default=20,
                        help="seconds visible on the plot (default: 20)")
    args = parser.parse_args()
    if args.baud <= 0:
        parser.error("--baud must be positive")

    try:
        import serial
        from serial.tools import list_ports
    except ImportError:
        parser.exit(1, "Install dependencies: python -m pip install -r requirements.txt\n")

    ports = list(list_ports.comports())
    if args.list_ports:
        for port in ports:
            print(f"{port.device}: {port.description}")
        if not ports:
            print("No serial ports found. Connect the ESP32 and try again.")
        return 0

    if not args.port:
        if len(ports) == 1:
            args.port = ports[0].device
        else:
            parser.exit(1, "Specify --port COM5 (use --list-ports to find your ESP32).\n")

    try:
        import matplotlib.pyplot as plt
        from matplotlib.animation import FuncAnimation
    except ImportError:
        parser.exit(1, "Install dependencies: python -m pip install -r requirements.txt\n")

    try:
        connection = serial.Serial(args.port, args.baud, timeout=0)
    except (serial.SerialException, OSError) as exc:
        parser.exit(1, f"Cannot open {args.port}: {exc}\n"
                    "Close Arduino Serial Monitor/Plotter and check the port.\n")

    print(f"Reading {args.port} at {args.baud} baud. Close the plot to stop.")
    # A hard limit also bounds memory if an unusually high-rate device is used.
    samples = deque(maxlen=100000)
    pending = bytearray()
    sample_parser = SampleParser()
    start = time.monotonic()
    last_sample = start
    last_raw = ""
    received_bytes = 0
    sample_count = 0
    disconnected = False
    fig, ax = plt.subplots(figsize=(10, 5))
    lines = [ax.plot([], [], label=axis, color=color, marker=".", markersize=3)[0]
             for axis, color in zip("XYZ", ("tab:red", "tab:green", "tab:blue"))]
    ax.set(xlabel="Time since connection (s)", ylabel="Magnetic field (µT)",
           title=f"MLX90393 — {args.port}", xlim=(0, args.window))
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right")
    status = ax.text(0.01, 0.98, "Waiting for sensor data…", transform=ax.transAxes,
                     va="top", fontsize=9)
    fig.tight_layout()

    def update(_frame):
        nonlocal disconnected, last_sample, last_raw, received_bytes, sample_count
        if disconnected:
            return lines
        try:
            # Nonblocking and bounded so a quiet/busy port cannot freeze the GUI.
            chunk = connection.read(min(connection.in_waiting, 65536))
            received_bytes += len(chunk)
            pending.extend(chunk)
        except (serial.SerialException, OSError) as exc:
            disconnected = True
            status.set_text("Serial connection lost. Reconnect and restart the script.")
            print(f"Serial connection lost: {exc}", file=sys.stderr)
            connection.close()
            return lines

        while b"\n" in pending:
            raw, _, rest = pending.partition(b"\n")
            pending[:] = rest
            text = raw.decode("utf-8", errors="replace").strip()
            last_raw = text[:100]
            if args.debug:
                print(f"RX: {text!r}", flush=True)
            sample = sample_parser.parse(text)
            if sample is not None:
                last_sample = time.monotonic()
                sample_count += 1
                samples.append((last_sample - start, *sample))
                status.set_text("   ".join(f"{axis}: {value:.2f} µT"
                                          for axis, value in zip("XYZ", sample)))
            elif text.startswith("#"):
                print(text)
                status.set_text(text.lstrip("# "))
        if len(pending) > 4096:
            pending.clear()  # Recover from corrupt data without growing forever.

        now = time.monotonic() - start
        if time.monotonic() - last_sample > 5:
            if not received_bytes:
                message = (f"No serial data from {args.port}. Check the port and baud rate; "
                           "press ESP32 RESET/EN.")
            elif not sample_count:
                message = f"Receiving data, but no XYZ readings. Latest: {last_raw!r}"
            else:
                message = f"Readings stopped. Latest serial line: {last_raw!r}"
            status.set_text(message)
        left = max(0, now - args.window)
        while samples and samples[0][0] < left:
            samples.popleft()
        if samples:
            timestamps, xs, ys, zs = zip(*samples)
            for line, values in zip(lines, (xs, ys, zs)):
                line.set_data(timestamps, values)
            ax.relim()
            ax.autoscale_view(scalex=False, scaley=True)
        else:
            for line in lines:
                line.set_data([], [])
        ax.set_xlim(left, left + args.window)
        return lines

    # Keep the animation alive for the entire lifetime of the window.
    animation = FuncAnimation(fig, update, interval=50, cache_frame_data=False)
    try:
        plt.show()
    except KeyboardInterrupt:
        pass
    finally:
        if animation.event_source is not None:
            animation.event_source.stop()
        connection.close()
        plt.close(fig)
    return 0


if __name__ == "__main__":
    sys.exit(main())
