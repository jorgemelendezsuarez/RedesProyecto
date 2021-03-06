import sys
import threading
import socket
import errno
import codecs
import os
import ipaddress

from socket import error as SocketError
from TablaAlcanzabilidad import *
from TablaVecinos import *
from ReceptorUDP import *
from EmisorUDP import *
from HiloEnviaTabla import *
from Bitacora import *
from HiloVerificacionVivo import *

class NodoUDP:

	#Constructor
	#ip: ip de la maquina donde va a ser iniciado
	#mascara: mascara del nodo
	#puerto: puerto donde va a ser iniciado
	#ipServerVecinos: ip del servidor de vecinos
	#mascaraServerVecinos: mascara del servidor de vecinos
	#puertoServerVecinos: puerto del servidor de vecinos
	def __init__(self, ip, mascara, puerto, ipServerVecinos, mascaraServerVecinos, puertoServerVecinos):
		self.servidorVecinos = ipServerVecinos, mascaraServerVecinos, puertoServerVecinos
		self.serverVecinos = ipServerVecinos, puertoServerVecinos
		self.nodoId = ip, mascara, puerto
		self.bitacora = Bitacora("Bitacora-"+str(self.nodoId)+".txt")
		self.lockAbortarActualizaciones = threading.Lock()
		self.abortarActualizaciones = False
		self.tablaAlcanzabilidad = TablaAlcanzabilidad(self.bitacora, self.lockAbortarActualizaciones, self.abortarActualizaciones)
		self.tablaVecinos = TablaVecinos(self.bitacora)
		self.socketNodo = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		self.socketNodo.bind((ip, puerto))
		self.lockSocketNodo = threading.Lock()
		self.bitacora.escribir("NodoUDP: " + "Me crearon")
		self.vecinosSupervivientes = dict()
		self.lockVecinosSupervivientes = threading.Lock()

	#Funcion para pedir los vecinos al ServerVecinos
	#Retorna 1 si se pudo comunicar con el servidor de vecinos
	#Retorna 0 si no se pudo comunicar con el servidor de vecinos
	def pedirVecinos(self):
		self.bitacora.escribir("NodoUDP: " + "Voy a perdir vecinos al servidor de vecinos")
		mensajeSolicitudVecinos = bytearray()
		mensajeSolicitudVecinos += intToBytes(self.nodoId[1],1) #Se pone la mascara en el mensaje de solicitudes
		banderaParada = False
		vecinos = bytearray()
		self.socketNodo.settimeout(1)
		intento = 1
		while not(banderaParada):
			self.lockSocketNodo.acquire()
			self.socketNodo.sendto(mensajeSolicitudVecinos, self.serverVecinos)
			self.lockSocketNodo.release()
			try:
				vecinos, serverAddress = self.socketNodo.recvfrom(2048)
			except socket.timeout:
				intento = intento + 1
				if intento == 10:
					print("El servidor no esta activo")
					banderaParada = True
			else:
				if serverAddress == self.serverVecinos:
					banderaParada = True
				else:
					intento = intento + 1
					if intento == 10:
						print("El servidor no esta activo")
						banderaParada = True
		self.socketNodo.settimeout(None)
		if intento == 10:
			self.bitacora.escribir("NodoUDP: " + "El servidor nunca contesto")
			return 0
		else:
			self.bitacora.escribir("NodoUDP: " + "El servidor me dio los vecinos")
			self.tablaVecinos.ingresarVecinos(vecinos)
			return 1

	#Metodo para intentar contactar a los vecinos para ver si estan activos
	# envia un mensaje a los vecinos (5 intentos) y espera respuesta
	# actualiza el bitActivo del vecino en la tabla de vecinos
	# si el vecino contesta, lo annade a la tabla de alcanzabilidad,(para indicar directo usa la misma tupla en atravez)
	def contactarVecinos(self):
		self.bitacora.escribir("NodoUDP: " + "Voy a intentar contactar vecinos")
		mensajeContactoVecino = bytearray()
		mensajeContactoVecino += intToBytes(2,1)#Tipo de mensaje es 1
		#mensajeContactoVecino += intToBytes(self.nodoId[1],1) #Se pone la mascara en el mensaje de solicitudes
		vecinosTabla = self.tablaVecinos.obtenerVecinos()#Se obtiene  los vecinos para intentar contactarlos
		for x in vecinosTabla: #Cada x, es (ip, mascara, puerto)
			banderaParada = False
			vecinos = bytearray()
			self.socketNodo.settimeout(1) #Espera respuesta durante 1 segundo
			intento = 1
			print("Intentando contactar al vecino: " + str(x))
			self.bitacora.escribir("NodoUDP: " + "Intentando contactar al vecino: " + str(x))
			while not(banderaParada): #While de intentos de contacto(maximo 5)
				#print("ASQUEROSO")
				#print("intento: " + str(intento))
				self.lockSocketNodo.acquire()
				self.socketNodo.sendto(mensajeContactoVecino, (x[0], x[2]))
				self.lockSocketNodo.release()
				try:
					vecinos, serverAddress = self.socketNodo.recvfrom(2048)
				except socket.timeout:
					intento = intento + 1
					if intento == 5:
						print("El vecino " + str(x) + " no esta activo")
						self.bitacora.escribir("NodoUDP: " + "El vecino " + str(x) + " no esta activo")
						banderaParada = True
				else:
					if serverAddress == (x[0], x[2]):
						banderaParada = True
						self.bitacora.escribir("NodoUDP: " + "El vecino " + str(x) + " esta activo")
					else:
						intento = intento + 1
						if intento == 5:#se mete esta condicion aqui porque si no puede generar ciclos infinitos si algun vecino enviar mensajes muchas veces porque le llegan otros que no esta esperando
							print("El vecino " + str(x) + " no esta activo")
							self.bitacora.escribir("NodoUDP: " + "El vecino " + str(x) + " no esta activo")
							banderaParada = True
						#print("Mensaje de " + str(serverAddress))
			self.socketNodo.settimeout(None)
			if intento == 5:
				self.tablaVecinos.modificarBitActivo(x[0], x[1], x[2], False)
			else:
				self.tablaVecinos.modificarBitActivo(x[0], x[1], x[2], True)
				distancia = self.tablaVecinos.obtenerDistancia(x[0], x[1], x[2])
				self.tablaAlcanzabilidad.annadirAlcanzable( x, distancia, x )

	#Metodo que da inico al nodo, pide los vecinos al ServerVecinos, intenta contactar a los vecinos 
	# manda a ejecutar un hilo receptor y el emisor(interfaz con usuario)
	def iniciarNodoUDP(self):
		llenaronVecinos = self.pedirVecinos()
		if llenaronVecinos == 1:
			self.contactarVecinos()#Se intenta contactar a los vecinos
			hiloEnviaTabla = HiloEnviaTabla(self.nodoId, self.tablaAlcanzabilidad, self.tablaVecinos, self.socketNodo, self.lockSocketNodo, self.bitacora)
			proceso_hiloEnviaTabla = threading.Thread(target=hiloEnviaTabla.iniciarCiclo, args=())
			proceso_hiloEnviaTabla.start()#Se crea el hilo de enviar tablas cada 30 segunodos
			self.bitacora.escribir("NodoUDP: " + "Se inicia el hilo que reenvia las tablas cada cierto tiempo")
			receptorUDP = ReceptorUDP(self.nodoId, self.tablaAlcanzabilidad, self.tablaVecinos, self.socketNodo, self.lockSocketNodo, self.bitacora, self.vecinosSupervivientes, self.lockVecinosSupervivientes, self.lockAbortarActualizaciones, self.abortarActualizaciones)
			receptorUDP.levantarHiloSupervivencia()
			proceso_receptorUDP = threading.Thread(target=receptorUDP.recibeMensajes, args=())
			proceso_receptorUDP.start()#Se crea el hilo de recepcion de mensajes
			self.bitacora.escribir("NodoUDP: " + "Se inicia el hilo que recibe mensajes")
			emisorUDP = EmisorUDP(self.nodoId, self.tablaAlcanzabilidad, self.tablaVecinos, self.socketNodo, self.lockSocketNodo, self.bitacora)
			proceso_emisorUDP = threading.Thread(target=emisorUDP.despligueMenuUDP, args=())
			proceso_emisorUDP.start()#Se crea el hilo emisor de mensajes (interfaz con el usuario)
			self.bitacora.escribir("NodoUDP: " + "Se inicia el hilo que envia mensajes")
		else:
			print("Error al tratar de comunicarse con el ServerVecinos")
			self.bitacora.escribir("NodoUDP: " + "Error al tratar de comunicarse con el ServerVecinos")