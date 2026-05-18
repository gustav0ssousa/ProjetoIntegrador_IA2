from machine import ADC, I2C, Pin
import gc
import math
import network
import os
import time
import ujson

try:
    import urequests as requests
except ImportError:
    requests = None

try:
    from config import CONFIG
except ImportError:
    CONFIG = {}


DEFAULT_CONFIG = {
    "wifi_ssid": "",
    "wifi_password": "",
    "api_url": "http://192.168.0.10:8000/leituras",
    "api_key": "",
    "device_id": "esp32-sensores-01",
    "send_interval_ms": 3000,
    "moisture_wet_threshold": 3800,
    "vibration_active_high": True,
    "acceleration_alert_ms2": 12.0,
}

PIN_MOISTURE_AO = 34
PIN_MOISTURE_DO = 27
PIN_BUZZER = 25
PIN_VIBRATION = 26
PIN_SDA = 21
PIN_SCL = 22

MPU_ADDR = 0x68
MPU_REG_PWR_MGMT_1 = 0x6B
MPU_REG_WHO_AM_I = 0x75
MPU_REG_ACCEL_XOUT_H = 0x3B
MPU_REG_TEMP_OUT_H = 0x41
MPU_REG_GYRO_XOUT_H = 0x43
GRAVITY_MS2 = 9.80665


def cfg(key):
    return CONFIG.get(key, DEFAULT_CONFIG[key])


def ticks_elapsed(start):
    return time.ticks_diff(time.ticks_ms(), start)


def info_esp32():
    print()
    print("=== ESP32 GeoRisk ===")
    print("CPU:", os.uname().machine)
    print("Plataforma:", os.uname().sysname)
    print("Versao:", os.uname().release)
    try:
        stat = os.statvfs("/")
        print("Flash livre:", stat[0] * stat[3], "bytes")
    except OSError:
        print("Flash livre: indisponivel")
    print("=====================")


def connect_wifi(timeout_ms=20000):
    ssid = cfg("wifi_ssid")
    password = cfg("wifi_password")

    if not ssid:
        print("Wi-Fi nao configurado. Crie src/config.py a partir de src/config.example.py.")
        return None

    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if wlan.isconnected():
        return wlan

    print("Conectando ao Wi-Fi:", ssid)
    wlan.connect(ssid, password)
    started = time.ticks_ms()

    while not wlan.isconnected() and ticks_elapsed(started) < timeout_ms:
        print(".", end="")
        time.sleep_ms(500)

    print()
    if wlan.isconnected():
        print("Wi-Fi conectado:", wlan.ifconfig())
        return wlan

    print("Falha ao conectar no Wi-Fi dentro do timeout.")
    return wlan


def setup_adc():
    adc = ADC(Pin(PIN_MOISTURE_AO))
    try:
        adc.atten(ADC.ATTN_11DB)
        adc.width(ADC.WIDTH_12BIT)
    except AttributeError:
        pass
    return adc


def read_adc(adc):
    try:
        return adc.read()
    except AttributeError:
        return adc.read_u16() >> 4


class MPU6050:
    def __init__(self, i2c):
        self.i2c = i2c
        self.connected = False

    def write_register(self, reg, value):
        self.i2c.writeto_mem(MPU_ADDR, reg, bytes([value]))

    def read_register(self, reg):
        return self.i2c.readfrom_mem(MPU_ADDR, reg, 1)[0]

    def read_i16(self, reg):
        data = self.i2c.readfrom_mem(MPU_ADDR, reg, 2)
        value = (data[0] << 8) | data[1]
        if value > 32767:
            value -= 65536
        return value

    def init(self):
        devices = self.i2c.scan()
        print("Dispositivos I2C:", devices)
        if MPU_ADDR not in devices:
            print("MPU6050 nao encontrado em 0x68.")
            self.connected = False
            return False

        who_am_i = self.read_register(MPU_REG_WHO_AM_I)
        print("WHO_AM_I MPU6050:", hex(who_am_i))
        self.write_register(MPU_REG_PWR_MGMT_1, 0x00)
        time.sleep_ms(100)
        self.connected = True
        print("MPU6050 pronto.")
        return True

    def read(self):
        if not self.connected:
            return {
                "aceleracao_x": 0.0,
                "aceleracao_y": 0.0,
                "aceleracao_z": 0.0,
                "giroscopio_x": 0.0,
                "giroscopio_y": 0.0,
                "giroscopio_z": 0.0,
                "temperatura": 0.0,
                "magnitude": 0.0,
            }

        ax = (self.read_i16(MPU_REG_ACCEL_XOUT_H) / 16384.0) * GRAVITY_MS2
        ay = (self.read_i16(MPU_REG_ACCEL_XOUT_H + 2) / 16384.0) * GRAVITY_MS2
        az = (self.read_i16(MPU_REG_ACCEL_XOUT_H + 4) / 16384.0) * GRAVITY_MS2
        temp = (self.read_i16(MPU_REG_TEMP_OUT_H) / 340.0) + 36.53
        gx = self.read_i16(MPU_REG_GYRO_XOUT_H) / 131.0
        gy = self.read_i16(MPU_REG_GYRO_XOUT_H + 2) / 131.0
        gz = self.read_i16(MPU_REG_GYRO_XOUT_H + 4) / 131.0
        magnitude = math.sqrt(ax * ax + ay * ay + az * az)

        return {
            "aceleracao_x": round(ax / GRAVITY_MS2, 3),
            "aceleracao_y": round(ay / GRAVITY_MS2, 3),
            "aceleracao_z": round(az / GRAVITY_MS2, 3),
            "giroscopio_x": round(gx, 2),
            "giroscopio_y": round(gy, 2),
            "giroscopio_z": round(gz, 2),
            "temperatura": round(temp, 2),
            "magnitude": round(magnitude, 2),
        }


def build_payload(moisture_ao, moisture_do, wet, vibration_raw, vibrating, mpu_data):
    acceleration_alarm = mpu_data["magnitude"] > cfg("acceleration_alert_ms2")
    event = bool(vibrating or acceleration_alarm)

    return {
        "id_simulacao": cfg("device_id"),
        "aceleracao_x": mpu_data["aceleracao_x"],
        "aceleracao_y": mpu_data["aceleracao_y"],
        "aceleracao_z": mpu_data["aceleracao_z"],
        "giroscopio_x": mpu_data["giroscopio_x"],
        "giroscopio_y": mpu_data["giroscopio_y"],
        "giroscopio_z": mpu_data["giroscopio_z"],
        "umidade_solo": int(moisture_ao),
        "chuva": 0,
        "inclinacao": 1 if vibrating else 0,
        "evento_deslizamento": event,
        "observacoes_experimento": (
            "higrometro_ao={}; higrometro_do={}; wet={}; vibracao_raw={}; "
            "mpu_temp={}; magnitude_ms2={}"
        ).format(
            moisture_ao,
            moisture_do,
            wet,
            vibration_raw,
            mpu_data["temperatura"],
            mpu_data["magnitude"],
        ),
    }


def send_payload(payload):
    if requests is None:
        print("Modulo urequests indisponivel no firmware.")
        return False

    headers = {"Content-Type": "application/json"}
    api_key = cfg("api_key")
    if api_key:
        headers["x-api-key"] = api_key

    response = None
    try:
        response = requests.post(cfg("api_url"), data=ujson.dumps(payload), headers=headers)
        ok = 200 <= response.status_code < 300
        print("POST", cfg("api_url"), "status", response.status_code)
        if not ok:
            try:
                print(response.text)
            except Exception:
                pass
        return ok
    except Exception as exc:
        print("Erro ao enviar leitura:", exc)
        return False
    finally:
        if response:
            response.close()
        gc.collect()


def main():
    info_esp32()

    moisture_adc = setup_adc()
    moisture_do = Pin(PIN_MOISTURE_DO, Pin.IN)
    buzzer = Pin(PIN_BUZZER, Pin.OUT)
    vibration = Pin(PIN_VIBRATION, Pin.IN, Pin.PULL_UP)
    buzzer.value(0)

    i2c = I2C(0, scl=Pin(PIN_SCL), sda=Pin(PIN_SDA), freq=100000)
    mpu = MPU6050(i2c)
    try:
        mpu.init()
    except Exception as exc:
        print("Falha ao inicializar MPU6050:", exc)

    wlan = connect_wifi()
    last_send = time.ticks_ms() - cfg("send_interval_ms")

    while True:
        moisture_ao = read_adc(moisture_adc)
        moisture_digital = moisture_do.value()
        wet = moisture_ao < cfg("moisture_wet_threshold")

        vibration_raw = vibration.value()
        active_high = cfg("vibration_active_high")
        vibrating = vibration_raw == 1 if active_high else vibration_raw == 0

        try:
            mpu_data = mpu.read()
        except Exception as exc:
            print("Erro ao ler MPU6050:", exc)
            mpu.connected = False
            mpu_data = mpu.read()

        buzzer_on = wet or vibrating or mpu_data["magnitude"] > cfg("acceleration_alert_ms2")
        buzzer.value(1 if buzzer_on else 0)

        print("===== LEITURA DOS SENSORES =====")
        print("Umidade AO:", moisture_ao)
        print("Umidade DO:", moisture_digital)
        print("Solo molhado:", "SIM" if wet else "NAO")
        print("Vibracao:", "VIBRANDO" if vibrating else "SEM VIBRACAO")
        print("Buzzer:", "LIGADO" if buzzer_on else "DESLIGADO")
        print("Aceleracao g: X={:.3f} Y={:.3f} Z={:.3f}".format(
            mpu_data["aceleracao_x"],
            mpu_data["aceleracao_y"],
            mpu_data["aceleracao_z"],
        ))
        print("Gyro deg/s: X={:.2f} Y={:.2f} Z={:.2f}".format(
            mpu_data["giroscopio_x"],
            mpu_data["giroscopio_y"],
            mpu_data["giroscopio_z"],
        ))

        if ticks_elapsed(last_send) >= cfg("send_interval_ms"):
            last_send = time.ticks_ms()
            if wlan is None or not wlan.isconnected():
                wlan = connect_wifi()
            if wlan and wlan.isconnected():
                payload = build_payload(
                    moisture_ao,
                    moisture_digital,
                    wet,
                    vibration_raw,
                    vibrating,
                    mpu_data,
                )
                send_payload(payload)

        time.sleep_ms(500)


main()
