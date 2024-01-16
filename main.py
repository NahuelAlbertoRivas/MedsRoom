import machine
from machine import Pin, I2C, PWM
import micropython
import network
import time
import dht
from lcd_i2c import LCD
from umqtt.simple import MQTTClient
from hcsr04 import HCSR04

#Indicamos red WIFI y clave
ssid = 'Wokwi-GUEST'
wifipassword = ''
#Datos Server MQTT (Broker)
#Indicamos datos MQTT Broker (server y puerto)
mqtt_server = 'io.adafruit.com'
port = 1883
user = 'gliwa' #definido en adafruit
password = 'aio_yGhe48h7F6X8r8EN4kT3IWJBJ8ZT' #key adafruit
#Indicamos ID(unico) y topicos
client_id = 'DrugsRoom1'
topic_PRIORIDAD = 'gliwa/feeds/prioridad'
topic_RANGOTEMP = 'gliwa/feeds/rangotemp'
topic_RANGOHUM = 'gliwa/feeds/rangohum'
topic_ALERTASENSOR = 'gliwa/feeds/alertasensor'
topic_ESTADOAC = 'gliwa/feeds/estadoac'
topic_TRABA = 'gliwa/feeds/traba-puerta'
# Declaracion del display columnas, parlante y sensor
I2C_ADDR = 0x27     # DEC 39, HEX 0x27
i2c = I2C(0, scl=Pin(18), sda=Pin(19), freq=800000)
lcd = LCD(addr=I2C_ADDR, cols=20, rows=4, i2c=i2c)
sensorTyH = dht.DHT22(Pin(13))
parlante = PWM(Pin(16), freq=440, duty_u16=32768)
sensorultrasonido = HCSR04(trigger_pin=15, echo_pin=2)
# Manipulación del display + alarma + traba
lcd.begin()
salida = Pin(21, Pin.OUT)
Led = Pin(17, Pin.OUT)
traba_puerta = Pin(4, Pin.OUT)

#variables
SEL_PRIORIDAD = 0
RANGO_TEMP = 8
RANGO_HUM = 50
AC_ESTADO_DESCRIPCION = "Temperatura"
AC_ESTADO = 0
TRABA_ESTADO = 0
ALERTA_SENSOR = 0
parlante.duty(0)

#Definimos modo Station (conectarse a Access Point remoto)
sta_if = network.WLAN(network.STA_IF)
sta_if.active(True)
#Conectamos al wifi
sta_if.connect(ssid, wifipassword)
print("Conectando")
while not sta_if.isconnected():
  print(".", end="")
  time.sleep(0.1)
print("Conectado a Wifi!")
#Vemos cuales son las IP
print(sta_if.ifconfig())

def callback_drcontrol(topic, msg):
    global SEL_PRIORIDAD, RANGO_TEMP, RANGO_HUM, AC_ESTADO, AC_ESTADO_DESCRIPCION, TRABA_ESTADO
    #Cuando se ejecuta esta funcion quere decir que
    #hubo un mensaje nuevo en algun topico, verificamos esto
    #Dado que lo que llega viene en UTF-8, lo decodificamos
    #para que sea una cadena de texto regular
    dato = msg.decode('utf-8')
    topicrec = topic.decode('utf-8')
    print("Cambio en: "+topicrec+": "+dato)
    # Selector de prioridad
    if topicrec == topic_PRIORIDAD:
        if "TEMP" in dato:
            lcd.clear()
            AC_ESTADO_DESCRIPCION = "Temperatura"
            SEL_PRIORIDAD = 0
        else:
            lcd.clear()
            AC_ESTADO_DESCRIPCION = "Humedad"
            SEL_PRIORIDAD = 1
    # Indicador del rango de temperatura
    if topicrec == topic_RANGOTEMP:
        RANGO_TEMP = int(dato)
    # Indicador del rango de humedad
    if topicrec == topic_RANGOHUM:
        RANGO_HUM = int(dato)
    # Relay (estado del aire acondicionado)
    if topicrec == topic_ESTADOAC:
        if "OFF" in dato: 
            salida.value(0)
            AC_ESTADO = 0
        else:
            salida.value(1)
            AC_ESTADO = 1
    # Relay (estado de la traba)
    if topicrec == topic_TRABA:
        if "abre" in dato: 
            traba_puerta.value(0)
            TRABA_ESTADO = 0
        else:
            traba_puerta.value(1)
            TRABA_ESTADO = 1

try:
    conexionMQTT = MQTTClient(client_id, mqtt_server,user=user,password=password,port=int(port))
    conexionMQTT.set_callback(callback_drcontrol)
    conexionMQTT.connect()
    conexionMQTT.subscribe(topic_PRIORIDAD)
    conexionMQTT.subscribe(topic_RANGOHUM)
    conexionMQTT.subscribe(topic_RANGOTEMP)
    conexionMQTT.subscribe(topic_ESTADOAC)
    conexionMQTT.subscribe(topic_TRABA)


    print("Conectado con Broker MQTT")
except OSError as e:
    #Si fallo la conexion, reiniciamos todo
    print("Fallo la conexion al Broker, reiniciando...")
    time.sleep(5)
    machine.reset()

while True:
    sensorTyH.measure()
    temperatura = sensorTyH.temperature()
    humedad = sensorTyH.humidity()
    distance = sensorultrasonido.distance_cm()
    try:
        #Tenemos que verificar si hay mensajes nuevos publicados por el broker
        conexionMQTT.check_msg()
        time.sleep_ms(500)
        if SEL_PRIORIDAD == 0:
            # sentencias de comparación para el rango de temperatura elegido
            # por el usuario; hay que ver cómo resolvemos
            # la recepción de tal tango desde el protoboard
            # a algún dispositivo de wokwi
            if temperatura > RANGO_TEMP:
                conexionMQTT.publish(topic_ALERTASENSOR,str(1))
                # Obs: tanquilamente el sistema puede estar automatizado, apenas detecta que el rango es mayor al tolerado se setea en 1 ESTADO_AC y comienza el período de enfriamiento sin necesidad de que el usuario interactué, y ante cualquier falla, se podría setear un encendido/apagado forzado
                ALERTA_SENSOR = 1
            else:
                conexionMQTT.publish(topic_ALERTASENSOR,str(0))
                ALERTA_SENSOR = 0
        else:
            if humedad > RANGO_HUM:
                conexionMQTT.publish(topic_ALERTASENSOR,str(1))
                ALERTA_SENSOR = 1
            else:
                conexionMQTT.publish(topic_ALERTASENSOR,str(0))
                ALERTA_SENSOR = 0
    except OSError as e:
        print("Error ",e)
        time.sleep(5)
        machine.reset()
    if ALERTA_SENSOR==1 and AC_ESTADO==0:
        Led.value(1)
        parlante.duty(50)
    else:
        Led.value(0)
        parlante.duty(0)
    if distance<250 and TRABA_ESTADO==1:
       #250 ES DISTANCIA PREDETERMINADA, SI NO SE CUMPLE SIGNIFICA QUE
       #HAY UNA PERSONA EN MEDIO, POR LO TANTO DEBE DESACTIVARSE
        traba_puerta.value(0)
        time.sleep(1)
        TRABA_ESTADO=0
        #AL VOLVER A COLOCAR DISTANCIA CORRESPONDIENTE NO VUELVE A TOMAR
        #VALOR 1 (CERRADO), NO SE COMO AUTOMATIZARLO


    lcd.clear()
    lcd.print("Prioridad selec.: ")
    lcd.set_cursor(col=4, row=1)
    lcd.print(AC_ESTADO_DESCRIPCION)
    time.sleep(3)
    lcd.clear()
    lcd.print("Temperatura actual: ")
    # Desplazar el cursor en fila x columna y
    #lcd.set_cursor(col=y, row=x)
    lcd.set_cursor(col=4, row=1)
    lcd.print(str(temperatura) + " grados")
    time.sleep(3)
    lcd.clear()
    lcd.print("   Humedad actual:")
    lcd.set_cursor(col=8, row=1)
    lcd.print(str(humedad) + "%")
    time.sleep(3)
    lcd.clear()
    lcd.print("   Estado -> " + str(ALERTA_SENSOR) + ": ")
    if ALERTA_SENSOR == 0:
        lcd.print("OK")
        lcd.set_cursor(col=4, row=1)
        lcd.print("solo personal")
        lcd.set_cursor(col=6, row=2)
        lcd.print("autorizado")
        time.sleep(3)
    else:
        if AC_ESTADO == 0:
            lcd.set_cursor(col=4, row=1)
            lcd.print("ACTIVAR AC")
            lcd.set_cursor(col=0, row=2)
        else:
            lcd.set_cursor(col=4, row=1)
            lcd.print("Climatizacion")
            lcd.set_cursor(col=5, row=2)
            lcd.print("en proceso")
            lcd.set_cursor(col=0, row=3)
        lcd.print("INGRESO INHABILITADO")
        time.sleep(3)
    lcd.clear()
    lcd.print("     Puerta:")
    if TRABA_ESTADO==0:
            lcd.set_cursor(col=6, row=1)
            lcd.print("Destrabada")
            time.sleep(1)
    else:
        lcd.set_cursor(col=7, row=1)
        lcd.print("Trabada!")
        time.sleep(4)

# while True:
#     if SELECCION_PRIORIDAD # Por defecto la prioridad es la temperatura
#Problemas: Si tengo el topico directamente en hum no me detecta el cambio
#no detecta varios cambios al mismo tiempo, los hace por leida(tiene que terminar
#el ciclo) optimizar?
#topico alertasensor, mantenerlo? Solo indica estado, no considera ac encendido
#como el topico LedAlerta... Aunque sigue siendo util saber solo el estado.
#para corroborar cuando se baja del rango limite la temp o hum.

