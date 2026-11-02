#include "Adafruit_MLX90393.h"

Adafruit_MLX90393 sensor = Adafruit_MLX90393();
const unsigned long SAMPLE_INTERVAL_MS = 50;

void setup(void)
{
  Serial.begin(115200);

  /* Wait for serial on USB platforms. */
  while (!Serial) {
      delay(10);
  }

  Serial.println("# Starting MLX90393");

  Wire1.begin(22, 19);  // SDA, SCL

  if (!sensor.begin_I2C(0x18, &Wire1)) {
    Serial.println("# No sensor found ... check your wiring?");
    while (1) { delay(10); }
  }

  Serial.println("# Found a MLX90393 sensor");

  sensor.setGain(MLX90393_GAIN_1X);
  // You can check the gain too
  Serial.print("# Gain set to: ");
  switch (sensor.getGain()) {
    case MLX90393_GAIN_1X: Serial.println("1 x"); break;
    case MLX90393_GAIN_1_33X: Serial.println("1.33 x"); break;
    case MLX90393_GAIN_1_67X: Serial.println("1.67 x"); break;
    case MLX90393_GAIN_2X: Serial.println("2 x"); break;
    case MLX90393_GAIN_2_5X: Serial.println("2.5 x"); break;
    case MLX90393_GAIN_3X: Serial.println("3 x"); break;
    case MLX90393_GAIN_4X: Serial.println("4 x"); break;
    case MLX90393_GAIN_5X: Serial.println("5 x"); break;
  }

  // Set resolution, per axis. Aim for sensitivity of ~0.3 for all axes.
  sensor.setResolution(MLX90393_X, MLX90393_RES_17);
  sensor.setResolution(MLX90393_Y, MLX90393_RES_17);
  sensor.setResolution(MLX90393_Z, MLX90393_RES_16);

  // Set oversampling
  sensor.setOversampling(MLX90393_OSR_3);

  // Set digital filtering
  sensor.setFilter(MLX90393_FILTER_5);
  Serial.println("# x_uT,y_uT,z_uT");
}

void loop(void) {
  float x, y, z;

  // get X Y and Z data at once
  if (sensor.readData(&x, &y, &z)) {
      Serial.print(x, 4); Serial.print(',');
      Serial.print(y, 4); Serial.print(',');
      Serial.println(z, 4);
  } else {
      Serial.println("# Unable to read XYZ data from the sensor.");
  }

  // Sensor conversion time adds to this interval.
  delay(SAMPLE_INTERVAL_MS);
}
