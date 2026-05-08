from machine import I2C, Pin
import machine
import network
import time
import os

MPU_ADDR = 0x68
PWR_MGMT_1 = 0x6B
ACCEL_XOUT_H = 0x3B
GYRO_XOUT_H = 0x43

i2c = I2C(0, scl=Pin(22), sda=Pin(21))



def mostrar_info():
    print()
    print("=== Informacoes do ESP32 ===")

    # CPU
    print("Frequencia CPU:", machine.freq() // 1_000_000, "MHz")

    # Núcleos (ESP32 padrão)
    print("Nucleos: 2")

    # Flash (filesystem)
    try:
        stat = os.statvfs('/')
        total = stat[0] * stat[2]
        livre = stat[0] * stat[3]
        print("Flash total:", total, "bytes")
        print("Flash livre:", livre, "bytes")
    except:
        print("Flash: desconhecido")

    # MAC Address
    wlan = network.WLAN(network.STA_IF)
    mac = wlan.config('mac')
    mac_str = ':'.join('{:02x}'.format(b) for b in mac)
    print("MAC Address:", mac_str)

    # Info adicional útil
    print("Plataforma:", os.uname().sysname)
    print("Versao:", os.uname().release)

    print("============================")


def init_mpu():

  i2c.writeto_mem(MPU_ADDR, PWR_MGMT_1, b'\x00')
  print('MPU6050 inicializado!\n')

def ler_word(reg):
  high= i2c.readfrom_mem(MPU_ADDR, reg, 1)[0]
  low = i2c.readfrom_mem(MPU_ADDR, reg + 1, 1)[0]
  value = (high << 8) | low
  if value > 32767:
    value -= 65536
  
  return value

def ler_aceleracao():
  ax = ler_word(ACCEL_XOUT_H) / 16384.0
  ay = ler_word(ACCEL_XOUT_H + 2) / 16384.0
  az = ler_word(ACCEL_XOUT_H + 4) / 16384.0
  
  return ax, ay, az

def ler_gyro():
    gx = ler_word(GYRO_XOUT_H) / 131.0
    gy = ler_word(GYRO_XOUT_H + 2) / 131.0
    gz = ler_word(GYRO_XOUT_H + 4) / 131.0
    return gx, gy, gz

def scan_i2c():
  devices = i2c.scan()
  print("Dispositivos I2C encontrados:", devices)
  if MPU_ADDR not in devices:
    print("MPU6050 NAO encontrado!")
  else:
    print("MPU6050 detectado!\n")

mostrar_info()
scan_i2c()
init_mpu()

while True:
    try:
        ax, ay, az = ler_aceleracao()
        gx, gy, gz = ler_gyro()

        print("Aceleracao (g): X={:.2f} Y={:.2f} Z={:.2f}".format(ax, ay, az))
        print("Gyro (°/s):     X={:.2f} Y={:.2f} Z={:.2f}".format(gx, gy, gz))
        print("-----------------------------")

        time.sleep(1)

    except Exception as e:
        print("Erro:", e)
        time.sleep(2)

