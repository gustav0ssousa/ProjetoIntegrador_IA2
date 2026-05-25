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
    "moisture_dry_adc": 4095,
    "moisture_wet_adc": 1500,
    "moisture_wet_threshold": 2600,
    "moisture_digital_active_low": True,
    "moisture_use_digital_wet": False,
    "vibration_active_high": False,
    "vibration_sample_count": 25,
    "vibration_event_samples": 0,
    "vibration_sample_delay_ms": 4,
    "vibration_edge_threshold": 4,
    "vibration_continuous_windows": 2,
    "acceleration_attention_threshold_g": 0.4,
    "acceleration_alert_threshold_g": 0.7,
    "buzzer_active_high": True,
    "buzzer_pulse_moisture_min_threshold": 2400,
    "buzzer_continuous_moisture_threshold": 3400,
    "buzzer_normal_pulse_ms": 80,
    "buzzer_normal_interval_ms": 5000,
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


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def scaled_adc(raw_value, dry_adc, wet_adc):
    """Converte a leitura eletrica do HW-103A para escala de risco 0-4095.

    Na maioria dos modulos resistivos, o AO diminui com mais agua. A API e o
    dashboard trabalham melhor para predicao quando valores maiores significam
    mais umidade, por isso a calibracao usa pontos seco/molhado.
    """
    if wet_adc == dry_adc:
        return int(clamp(raw_value, 0, 4095))

    ratio = (raw_value - dry_adc) / (wet_adc - dry_adc)
    return int(round(clamp(ratio, 0.0, 1.0) * 4095))


def digital_active(raw_value, active_high):
    return raw_value == 1 if active_high else raw_value == 0


def read_vibration_event(pin):
    sample_count = max(1, int(cfg("vibration_sample_count")))
    required_samples = max(0, int(cfg("vibration_event_samples")))
    required_edges = max(1, int(cfg("vibration_edge_threshold")))
    delay_ms = max(0, int(cfg("vibration_sample_delay_ms")))
    active_high = bool(cfg("vibration_active_high"))

    active_samples = 0
    transitions = 0
    last_raw = pin.value()
    for index in range(sample_count):
        raw = pin.value()
        if index > 0 and raw != last_raw:
            transitions += 1
        if digital_active(raw, active_high):
            active_samples += 1
        last_raw = raw
        if delay_ms and index < sample_count - 1:
            time.sleep_ms(delay_ms)

    rapid_variation = transitions >= required_edges and active_samples >= required_samples
    return last_raw, rapid_variation, active_samples, transitions


class SW520VibrationMonitor:
    def __init__(self, pin):
        self.pin = pin
        self.irq_edges = 0
        self.irq_enabled = False
        self.last_raw = pin.value()
        try:
            self.pin.irq(
                trigger=Pin.IRQ_RISING | Pin.IRQ_FALLING,
                handler=self._on_edge,
            )
            self.irq_enabled = True
        except Exception as exc:
            print("SW-520 IRQ indisponivel, usando polling:", exc)

    def _on_edge(self, pin):
        self.irq_edges += 1
        self.last_raw = pin.value()

    def read(self):
        irq_edges_before = self.irq_edges
        self.irq_edges = 0
        raw, polling_detected, active_samples, polling_edges = read_vibration_event(self.pin)
        irq_edges_after = self.irq_edges
        self.irq_edges = 0
        irq_edges = irq_edges_before + irq_edges_after
        edges = max(irq_edges, polling_edges)
        detected = polling_detected or edges >= max(1, int(cfg("vibration_edge_threshold")))
        return raw, detected, active_samples, edges, irq_edges, polling_edges

    def print_diagnostics(self):
        print("=== SW-520 ===")
        print("GPIO:", PIN_VIBRATION)
        print("Raw inicial:", self.pin.value())
        print("Ativo em HIGH:", cfg("vibration_active_high"))
        print("IRQ ativo:", "SIM" if self.irq_enabled else "NAO")
        print("Bordas para vibracao:", cfg("vibration_edge_threshold"))
        print("Janelas continuas:", cfg("vibration_continuous_windows"))
        print("==============")


def set_buzzer(pin, active):
    pin.value(1 if bool(active) == bool(cfg("buzzer_active_high")) else 0)


def update_buzzer(pin, alert_active, pulse_enabled, last_normal_pulse):
    if alert_active:
        set_buzzer(pin, True)
        return last_normal_pulse, "ALERTA CONTINUO"

    set_buzzer(pin, False)
    if not pulse_enabled:
        return last_normal_pulse, "NORMAL SEM BUZZER"

    interval_ms = max(500, int(cfg("buzzer_normal_interval_ms")))
    pulse_ms = max(0, int(cfg("buzzer_normal_pulse_ms")))

    if pulse_ms and ticks_elapsed(last_normal_pulse) >= interval_ms:
        set_buzzer(pin, True)
        time.sleep_ms(pulse_ms)
        set_buzzer(pin, False)
        return time.ticks_ms(), "PULSO NORMAL"

    return last_normal_pulse, "NORMAL SILENCIOSO"


def acceleration_motion_g(mpu_data):
    ax = mpu_data["aceleracao_x"]
    ay = mpu_data["aceleracao_y"]
    az = mpu_data["aceleracao_z"] - 1.0
    return round(math.sqrt(ax * ax + ay * ay + az * az), 3)


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


def build_payload(
    moisture_ao,
    moisture_scaled,
    moisture_do,
    moisture_digital_wet,
    wet,
    vibration_raw,
    vibration_hits,
    vibration_edges,
    vibration_streak,
    vibrating,
    acceleration_motion,
    mpu_data,
):
    acceleration_alarm = acceleration_motion > cfg("acceleration_alert_threshold_g")
    event = bool(vibrating or acceleration_alarm)

    return {
        "id_simulacao": cfg("device_id"),
        "aceleracao_x": mpu_data["aceleracao_x"],
        "aceleracao_y": mpu_data["aceleracao_y"],
        "aceleracao_z": mpu_data["aceleracao_z"],
        "giroscopio_x": mpu_data["giroscopio_x"],
        "giroscopio_y": mpu_data["giroscopio_y"],
        "giroscopio_z": mpu_data["giroscopio_z"],
        "umidade_solo": int(moisture_scaled),
        "inclinacao": 1 if vibrating else 0,
        "hw103a_ao": int(moisture_ao),
        "hw103a_do": int(moisture_do),
        "hw103a_do_wet": bool(moisture_digital_wet),
        "sw520_raw": int(vibration_raw),
        "sw520_hits": int(vibration_hits),
        "sw520_edges": int(vibration_edges),
        "sw520_streak": int(vibration_streak),
        "mpu_motion_g": float(acceleration_motion),
        "evento_deslizamento": event,
        "observacoes_experimento": (
            "sensores=MPU6050,SW-520,HW-103A,buzzer; hw103a_ao={}; "
            "umidade_norm={}; hw103a_do={}; hw103a_do_wet={}; wet={}; "
            "sw520_raw={}; sw520_hits={}; sw520_edges={}; sw520_streak={}; "
            "mpu_motion_g={}; mpu_temp={}; magnitude_ms2={}"
        ).format(
            moisture_ao,
            moisture_scaled,
            moisture_do,
            moisture_digital_wet,
            wet,
            vibration_raw,
            vibration_hits,
            vibration_edges,
            vibration_streak,
            acceleration_motion,
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
    vibration_monitor = SW520VibrationMonitor(vibration)
    set_buzzer(buzzer, False)
    vibration_monitor.print_diagnostics()

    i2c = I2C(0, scl=Pin(PIN_SCL), sda=Pin(PIN_SDA), freq=100000)
    mpu = MPU6050(i2c)
    try:
        mpu.init()
    except Exception as exc:
        print("Falha ao inicializar MPU6050:", exc)

    wlan = connect_wifi()
    last_send = time.ticks_ms() - cfg("send_interval_ms")
    last_normal_buzzer_pulse = time.ticks_ms() - cfg("buzzer_normal_interval_ms")
    vibration_streak = 0

    while True:
        moisture_ao = read_adc(moisture_adc)
        moisture_digital = moisture_do.value()
        moisture_scaled = scaled_adc(
            moisture_ao,
            int(cfg("moisture_dry_adc")),
            int(cfg("moisture_wet_adc")),
        )
        moisture_digital_wet = digital_active(
            moisture_digital,
            not bool(cfg("moisture_digital_active_low")),
        )
        wet_by_analog = moisture_scaled >= cfg("moisture_wet_threshold")
        wet_by_digital = bool(cfg("moisture_use_digital_wet")) and moisture_digital_wet
        wet = wet_by_analog or wet_by_digital

        (
            vibration_raw,
            vibration_window_detected,
            vibration_hits,
            vibration_edges,
            vibration_irq_edges,
            vibration_polling_edges,
        ) = vibration_monitor.read()
        if vibration_window_detected:
            vibration_streak += 1
        else:
            vibration_streak = 0
        vibrating = vibration_streak >= max(1, int(cfg("vibration_continuous_windows")))

        try:
            mpu_data = mpu.read()
        except Exception as exc:
            print("Erro ao ler MPU6050:", exc)
            mpu.connected = False
            mpu_data = mpu.read()

        acceleration_motion = acceleration_motion_g(mpu_data)
        acceleration_attention = acceleration_motion > cfg("acceleration_attention_threshold_g")
        acceleration_alert = acceleration_motion > cfg("acceleration_alert_threshold_g")
        moisture_buzzer_alert = moisture_scaled >= cfg("buzzer_continuous_moisture_threshold")
        moisture_buzzer_pulse = moisture_scaled >= cfg("buzzer_pulse_moisture_min_threshold")
        buzzer_alert = moisture_buzzer_alert or vibrating or acceleration_alert
        buzzer_pulse = moisture_buzzer_pulse or acceleration_attention
        last_normal_buzzer_pulse, buzzer_status = update_buzzer(
            buzzer,
            buzzer_alert,
            buzzer_pulse,
            last_normal_buzzer_pulse,
        )

        print("===== LEITURA DOS SENSORES =====")
        print("HW-103A AO bruto:", moisture_ao)
        print("Umidade normalizada:", moisture_scaled)
        print("umidade_solo enviada:", moisture_scaled)
        print(
            "HW-103A DO:",
            moisture_digital,
            "ATIVO" if moisture_digital_wet else "INATIVO",
            "(diagnostico)",
        )
        print("Solo molhado:", "SIM" if wet else "NAO", "origem:", "AO" if wet_by_analog else "DO" if wet_by_digital else "nenhuma")
        print("Limiar buzzer pulso:", cfg("buzzer_pulse_moisture_min_threshold"))
        print("Limiar buzzer continuo:", cfg("buzzer_continuous_moisture_threshold"))
        print(
            "SW-520:",
            "VIBRACAO CONTINUA" if vibrating else "VARIACAO RAPIDA" if vibration_window_detected else "ESTAVEL",
            "amostras:",
            vibration_hits,
            "bordas:",
            vibration_edges,
            "irq:",
            vibration_irq_edges,
            "polling:",
            vibration_polling_edges,
            "sequencia:",
            vibration_streak,
        )
        print("Buzzer:", buzzer_status)
        print(
            "MPU movimento g:",
            acceleration_motion,
            "nivel:",
            "ALERTA" if acceleration_alert else "ATENCAO" if acceleration_attention else "NORMAL",
        )
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
                    moisture_scaled,
                    moisture_digital,
                    moisture_digital_wet,
                    wet,
                    vibration_raw,
                    vibration_hits,
                    vibration_edges,
                    vibration_streak,
                    vibrating,
                    acceleration_motion,
                    mpu_data,
                )
                send_payload(payload)

        time.sleep_ms(500)


main()
