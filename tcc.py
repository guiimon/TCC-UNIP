import RPi.GPIO as GPIO
import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import pandas as pd
import psycopg2 as pg
import uuid
import configparser
from decimal import Decimal
from datetime import datetime
import multiprocessing
import os.path
#Variaveis
#variaveis de cominucação com o ads1115
i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c)
canal0 = AnalogIn(ads, ADS.P0)
canal1 = AnalogIn(ads, ADS.P1)

#variaveis da velocidade do vento
pi = 3.14159265
tempo = 5
delaytime = 2000
raio = 147
trigger = 0

#variaveis para medição da velocidade do vento
GPIO.cleanup() #reseta qualquer configuração anterior dos GPIOs
GPIO.setup(4, GPIO.IN, pull_up_down=GPIO.PUD_UP)

#variaveis para controle dos motores de passo
Porta1 = [12,16,20,21]
Porta2 = [24,25,8,7]
Porta4 = [6,13,19,26]
Porta3 = [17,27,22,10]
ListaDePinos = [Porta1,Porta2,Porta3,Porta4]
motorWaitTime = 0.005

for porta in ListaDePinos: #configura todas as portas GPIO como output e com o valor de saida null ou 0
    for pin in porta:
        print("Setup pins")
        GPIO.setup(pin,GPIO.OUT)
        GPIO.output(pin, 0)
        
#Definindo sequencia de passos para o motor de passos
sequencia = []
sequencia = [i for i in range(0,8)]
sequencia[0] = [1,0,0,0]
sequencia[1] = [1,1,0,0]
sequencia[2] = [0,1,0,0]
sequencia[3] = [0,1,1,0]
sequencia[4] = [0,0,1,0]
sequencia[5] = [0,0,1,1]
sequencia[6] = [0,0,0,1]
sequencia[7] = [1,0,0,1]

#Metodos
#Gera a conexão com o banco de dados com os dados necessários para acesso.
def iniciaCon():
    global connection
    global cursor
    connection = pg.connect(
    database = 'railway',
    host= 'containers-us-west-147.railway.app',
    user='postgres',
    password='jwiQVvjFu8nG2Yw3rpt5',
    port='5545'
    )
    cursor = connection.cursor()

#retorna a direção do vento por extenso
def direcao(voltagem):
    if (voltagem <= 0.27):
        direcao = "Noroeste"
    elif (voltagem <= 0.32):
        direcao = "Oeste"
    elif (voltagem <= 0.38):
        direcao = "Sudoeste"
    elif (voltagem <= 0.45):
        direcao = "Sul"
    elif (voltagem <= 0.57):
        direcao = "Sudeste"
    elif (voltagem <= 0.75):
        direcao = "Leste"
    elif (voltagem <= 1.25):
        direcao = "Nordeste"
    else:
        direcao = "Norte"
    return direcao;

#retorna a direção do vento por angulo
def direcaoAngulo(voltagem):
    if (voltagem <= 0.27):
        direcao = 315
    elif (voltagem <= 0.32):
        direcao = 270
    elif (voltagem <= 0.38):
        direcao = 225
    elif (voltagem <= 0.45):
        direcao = 180
    elif (voltagem <= 0.57):
        direcao = 135
    elif (voltagem <= 0.75):
        direcao = 90
    elif (voltagem <= 1.25):
        direcao = 45
    else:
        direcao = 0
    return direcao

#calcula as rotações por minuto
def RPMc(counter):
    return ((counter)*60) / tempo

#Calcula a velocidade em metros por segundo
def windSpeed(counter):
    return ((4 * pi * raio * RPMc(counter)) / 60) / 1000

#Calcula a velocidade em kilometros por hora
def speedWind(counter):
    return windSpeed(counter)*3.6

#executa todos os processos do calculo de velocidade do vento medido em 5sec.
def velocidade():
    rotacao = 0
    trigger = 0
    horafim = time.time() + tempo #indica o fim do tempo de medição de rotação
    iniciosensor = GPIO.input(4)
    while time.time() < horafim:
        if GPIO.input(4) == 1 and trigger == 0:
            rotacao = rotacao +1
            trigger = 1
        if GPIO.input(4) == 0:
            trigger = 0
        time.sleep(0.001)
    if rotacao == 1 and iniciosensor == 1:
        rotacao = 0
    resultvelo.value = round(windSpeed(rotacao), 10)

#Método de inserção de registro no BD
def incluir_registro_anemometro(velocidade, direcao, angulo, voltagem):
    iniciaCon()
    data_atual = datetime.now()
    
    uuidRandom = uuid.uuid4()
    query = "INSERT INTO anemometro123 (id, angulo, velocidade, direcao, data, energia_gerada) VALUES(%s, %s, %s, %s, %s, %s)"
    cursor.execute(query, (
        str(uuidRandom),
        angulo,
        Decimal(velocidade),
        str(direcao),
        data_atual ,
        voltagem
    ))
    connection.commit()
    connection.close()
    print("executou incluir registro")
   
def verificaEstado():
    iniciaCon()
    query = "SELECT * FROM portas"
    cursor.execute(query)
    connection.commit()
    connection.close()
    resultado = cursor.fetchall()
    for x in resultado:
        print(x)
    
def listar_registros_portas():
    iniciaCon()
    query = f"SELECT * FROM portas"
    df = pd.read_sql_query(query, con=connection)
    registros = df.to_dict(orient='records')
    connection.close()
    return registros[0]['funcionamento_normal']

#Metodo que retorna a voltagem capturada pelo mini gerador eólico   
def Voltagem():
    volt = 0
    counter = 0
    horafim = time.time() + tempo
    while time.time() < horafim:
        tempvolt = canal1.voltage
    #print("Sinal captado %.2f" % volt)
    #print(canal1.value)
        tempvolt = (tempvolt * 5)
        if (tempvolt < 0):
            tempvolt = 0
        volt += tempvolt
        counter+=1
    volt = volt/counter
    resultvolt.value = volt

#Metodo de movimento das portas
def steps(nb, StepPins):
        StepCount = 8
        StepCounter = 0
        if nb<0: sign=-1
        else: sign=1
        nb=sign*nb*2
        #print("nbsteps {} and sign {}".format(nb,sign))
        for i in range(nb):
                for pin in range(4):
                        xpin = StepPins[pin]
                        if sequencia[StepCounter][pin]!=0:
                                GPIO.output(xpin, True)
                        else:
                                GPIO.output(xpin, False)
                StepCounter += sign
                if (StepCounter==StepCount):
                        StepCounter = 0
                if (StepCounter<0):
                        StepCounter = StepCount-1
                time.sleep(0.005)
        for pin in StepPins:
            GPIO.output(pin, False)

#Metodo que traduz a quantidade de passos de acordo com o angulo e manda o movimento para a porta
def movePorta(angulo, porta):
    print(angulo)
    if(angulo!=0):
        passo = angulo * 2048 / 360
    else:
        passo =0
    steps(int(passo), porta)
    
#Metodo que encontra qual movimento deve ser feito de acordo com o angulo de objetivo
def achaMovimento(atual, objetivo):
    oposto = atual + 180
    resetou = False
    result1 = 0 #valor para a distancia em sentido horário
    result2 = 0 #valor para a distancia em sentido antihorário
    if(oposto >=360):
        oposto -= 360
        resetou = True
    if(oposto == objetivo or atual == objetivo):
        return 0
    if (resetou == True):
        if(objetivo>atual):
            result1 = objetivo - atual
            result2 = (oposto + (360 - objetivo))
        elif(objetivo<oposto):
            result1 = (360-atual)+objetivo
            result2 = (oposto - objetivo)
        else:
            result1 = objetivo - oposto
            result2 = (atual - objetivo)
    else:
        if(objetivo>atual and objetivo<oposto):
            result1 = objetivo - atual
            result2 = (oposto - objetivo)
        elif(objetivo<atual):
            result1 = (360 - oposto) + objetivo
            result2 = (atual - objetivo)
        else:
            result1 = objetivo - oposto
            result2 = atual + (360 - objetivo)
    result = min(result1, result2)
    if(result == result2):
        result = result * -1
    return result

def guardaPosicoes(posicaoP1,posicaoP2,posicaoP3,posicaoP4,angulo):
    with open('posicoes.txt', 'w') as f:
        f.write('%s\n' % posicaoP1)
        f.write('%s\n' % posicaoP2)
        f.write('%s\n' % posicaoP3)
        f.write('%s\n' % posicaoP4)
        f.write('%s\n' % angulo)
        
def guardaAngulo(angulo):
    with open('angulo.txt', 'a') as f:
        f.write('%s\n' % angulo)
        
def identificaPosicoes():
    with open('posicoes.txt') as f:
        lines = f.readlines()
        f.close()
        resultados = []
        for linha in lines:
            resultados.append(linha.strip())
        return resultados
        
def identificaDirecao(anguloP1, anguloP2, anguloP3, anguloP4, direcaoatual, direcao):
    objetivoP1 = multiprocessing.Value('i',0)
    objetivoP2 = multiprocessing.Value('i',0)
    objetivoP3 = multiprocessing.Value('i',0)
    objetivoP4 = multiprocessing.Value('i',0)
    if(direcaoatual != direcao):
        if(direcao.lower() == "norte"):
            objetivoP1.value = 315
            objetivoP2.value = 315
            objetivoP3.value = 0 #depende do resultado do teste prático
            objetivoP4.value = 0 #depende do resultado do teste prático
            movePorta(achaMovimento(anguloP1, objetivoP1.value),Porta1)
            movePorta(achaMovimento(anguloP2, objetivoP2.value),Porta2)
            movePorta(achaMovimento(anguloP3, objetivoP3.value),Porta3)
            movePorta(achaMovimento(anguloP4, objetivoP4.value),Porta4)
        elif(direcao.lower() == "nordeste"):
            objetivoP1.value = 315
            objetivoP2.value = 90
            objetivoP3.value = 45 
            objetivoP4.value = 0 
            movePorta(achaMovimento(anguloP2, objetivoP2.value),Porta2)
            movePorta(achaMovimento(anguloP1, objetivoP1.value),Porta1)
            movePorta(achaMovimento(anguloP3, objetivoP3.value),Porta3)
            movePorta(achaMovimento(anguloP4, objetivoP4.value),Porta4)
        elif(direcao.lower() == "leste"):
            objetivoP1.value = 0
            objetivoP2.value = 45
            objetivoP3.value = 45 
            objetivoP4.value = 0 
            movePorta(achaMovimento(anguloP2, objetivoP2.value),Porta2)
            movePorta(achaMovimento(anguloP3, objetivoP3.value),Porta3)
            movePorta(achaMovimento(anguloP1, objetivoP1.value),Porta1)
            movePorta(achaMovimento(anguloP4, objetivoP4.value),Porta4)
        elif(direcao.lower() == "sudeste"):
            objetivoP1.value = 0
            objetivoP2.value = 45
            objetivoP3.value = 90
            objetivoP4.value = 45 
            movePorta(achaMovimento(anguloP3, objetivoP3.value),Porta3)
            movePorta(achaMovimento(anguloP2, objetivoP2.value),Porta2)
            movePorta(achaMovimento(anguloP4, objetivoP4.value),Porta4)
            movePorta(achaMovimento(anguloP1, objetivoP1.value),Porta1)
        elif(direcao.lower() == "sul"):
            objetivoP1.value = 0
            objetivoP2.value = 0
            objetivoP3.value = 315 
            objetivoP4.value = 45 
            movePorta(achaMovimento(anguloP3, objetivoP3.value),Porta3)
            movePorta(achaMovimento(anguloP4, objetivoP4.value),Porta4)
            movePorta(achaMovimento(anguloP2, objetivoP2.value),Porta2)
            movePorta(achaMovimento(anguloP1, objetivoP1.value),Porta1)
        elif(direcao.lower() == "sudoeste"):
            objetivoP1.value = 45
            objetivoP2.value = 0
            objetivoP3.value = 315 
            objetivoP4.value = 90 
            movePorta(achaMovimento(anguloP4, objetivoP4.value),Porta4)
            movePorta(achaMovimento(anguloP1, objetivoP1.value),Porta1)
            movePorta(achaMovimento(anguloP3, objetivoP3.value),Porta3)
            movePorta(achaMovimento(anguloP2, objetivoP2.value),Porta2)
        elif(direcao.lower() == "oeste"):
            objetivoP1.value = 45
            objetivoP2.value = 0
            objetivoP3.value = 0 
            objetivoP4.value = 315
            movePorta(achaMovimento(anguloP4, objetivoP4.value),Porta4)
            movePorta(achaMovimento(anguloP1, objetivoP1.value),Porta1)
            movePorta(achaMovimento(anguloP2, objetivoP2.value),Porta2)
            movePorta(achaMovimento(anguloP3, objetivoP3.value),Porta3)
        elif(direcao.lower() == "noroeste"):
            objetivoP1.value = 90
            objetivoP2.value = 315
            objetivoP3.value = 0 
            objetivoP4.value = 315
            movePorta(achaMovimento(anguloP1, objetivoP1.value),Porta1)
            movePorta(achaMovimento(anguloP2, objetivoP2.value),Porta2)
            movePorta(achaMovimento(anguloP4, objetivoP4.value),Porta4)
            movePorta(achaMovimento(anguloP3, objetivoP3.value),Porta3)
        elif(direcao.lower() == "fechado"):
            objetivoP1.value = 0
            objetivoP2.value = 0
            objetivoP3.value = 0 
            objetivoP4.value = 0
            movePorta(achaMovimento(anguloP1, objetivoP1.value),Porta1)
            movePorta(achaMovimento(anguloP2, objetivoP2.value),Porta2)
            movePorta(achaMovimento(anguloP3, objetivoP3.value),Porta3)
            movePorta(achaMovimento(anguloP4, objetivoP4.value),Porta4)
        guardaPosicoes(objetivoP1.value,objetivoP2.value,objetivoP3.value,objetivoP4.value,direcao.lower())
        guardaAngulo(direcao.lower())
    movendoPortas.value=False

def ajustePortas(direcao):
    posicaoAtual = identificaPosicoes()
    '''
    print("Direção: %s" % direcao)
    print("AnguloP1: %s" % posicaoAtual[0])
    print("AnguloP2: %s" % posicaoAtual[1])
    print("AnguloP3: %s" % posicaoAtual[2])
    print("AnguloP4: %s" % posicaoAtual[3])
    print("Direção Atual: %s" % posicaoAtual[4])
    '''
    identificaDirecao(int(posicaoAtual[0]),int(posicaoAtual[1]),int(posicaoAtual[2]),int(posicaoAtual[3]),posicaoAtual[4],direcao)
    
#execução
if __name__ == '__main__':
    resultvolt = multiprocessing.Value('f',0.0)
    resultvelo = multiprocessing.Value('f',0.0)
    movendoPortas = multiprocessing.Value('b',False)
    if(os.path.isfile("./posicoes.txt")==False):
        guardaPosicoes(0,0,0,0,"fechado")
    while True:
        
        pVolt = multiprocessing.Process(target=Voltagem)
        pVelo = multiprocessing.Process(target=velocidade)
        pVolt.start()
        pVelo.start()
        pVolt.join()
        pVelo.join()
        angulovolt = canal0.voltage
        try:
            if(listar_registros_portas()):
                if(movendoPortas.value==False and resultvelo.value > 6):
                    movendoPortas.value = True;
                    time.sleep(1)
                    pMove = multiprocessing.Process(target=ajustePortas,args=(direcao(angulovolt).lower(),))
                    pMove.start()
            else:
                if(movendoPortas.value == False):
                    movendoPortas.value = True;
                    pMove = multiprocessing.Process(target=ajustePortas,args=("fechado",))
                    pMove.start()
        except:
            print("Sem conexão com internet.")
        
        print('Voltagem %s' % resultvolt.value)
        print('Velocidade %s' % resultvelo.value)
        print('Valor da direcao %s' % angulovolt)
        print('Direcao %s' % direcao(angulovolt))
        
        try:    
            incluir_registro_anemometro(resultvelo.value, direcao(angulovolt), direcaoAngulo(angulovolt), resultvolt.value)
        except:
            print("Erro de conexão, nova tentativa será efetuada.")
        print('--reset--')
        '''
        movePorta(0, Porta1)
        movePorta(0, Porta2)
        movePorta(0, Porta3)
        movePorta(90, Porta4)
        time.sleep(360)
        '''