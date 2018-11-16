import sys
import threading
import socket
import errno
import codecs
import os
import ipaddress
import time
from socket import error as SocketError
from TablaAlcanzabilidad import *
from ArmarMensajes import *
from HiloVerificacionVivo import *


class ReceptorUDP:

	#Constructor
	#nodoId: id del nodo, tupla (ip, mascara, puerto)
	#tablaAlcanzabilidad: tabla de alcanzabilidad del nodo
	#tablaVecinos: tabla de vecinos del nodo
	#socketNodo: sockect del nodo
	#lockSocketNodo: lock del socket del nodo
	def __init__(self, nodoId, tablaAlcanzabilidad, tablaVecinos, socketNodo, lockSocketNodo, bitacora, vecinosSupervivientes, lockVecinosSupervivientes):
		self.bitacora = bitacora
		self.nodoId = nodoId
		self.tablaAlcanzabilidad = tablaAlcanzabilidad
		self.tablaVecinos = tablaVecinos
		self.socketNodo = socketNodo
		self.lockSocketNodo = lockSocketNodo
		self.vecinosSupervivientes = vecinosSupervivientes
		self.lockVecinosSupervivientes = lockVecinosSupervivientes

	#Metodo para responder a vecino que si estoy vivo
	#vecino: tupla que es (ip, puerto)
	#mensaje: mascara del vecino
	def responderVivo(self, vecino, mensaje):
		mensajeRespContacto = bytearray()
		mensajeRespContacto += intToBytes(3,1)#Tipo de mensaje es 3
		#mensajeRespContacto += intToBytes(self.nodoId[1],1) #Se pone la mascara en el mensaje de solicitudes
		#mascara = bytesToInt(mensaje[1:2])
		#print("VECINO: " + str(vecino))
		mascara = (self.tablaVecinos.obtenerKey(vecino))[1]
		estadoVecino = self.tablaVecinos.obtenerBitActivo(vecino[0], mascara, vecino[1])
		distancia = self.tablaVecinos.obtenerDistancia(vecino[0], mascara, vecino[1])
		tuplaVecino = vecino[0], mascara, vecino[1]
		#self.tablaAlcanzabilidad.annadirAlcanzable( tuplaVecino, distancia, tuplaVecino )
		if estadoVecino == None:
			#print(str(vecino[0]) + " " + str(mascara) + " " + str(vecino[0]) + " no es uno de mis vecinos")
			self.bitacora.escribir("ReceptorUDP: " + "EL nodo " + str(vecino) + " no es mi vecino, entonces no le respondo")
		elif estadoVecino == True:
			self.lockSocketNodo.acquire()
			self.socketNodo.sendto(mensajeRespContacto, vecino)
			self.lockSocketNodo.release()
			self.bitacora.escribir("ReceptorUDP: " + "Le respondi al vecino " + str(vecino) + " que estoy vivo")
		else:
			self.tablaAlcanzabilidad.annadirAlcanzable( tuplaVecino, distancia, tuplaVecino )
			self.tablaVecinos.modificarBitActivo(vecino[0], mascara, vecino[1], True)
			self.lockSocketNodo.acquire()
			self.socketNodo.sendto(mensajeRespContacto, vecino)
			self.lockSocketNodo.release()
			self.bitacora.escribir("ReceptorUDP: " + "Le respondi al vecino " + str(vecino) + " que estoy vivo")
			vecinoId = vecino[0], mascara, vecino[1]
			hiloSupervivencia = HiloVerificacionVivo(self.nodoId, vecinoId, self.tablaAlcanzabilidad, self.tablaVecinos, self.socketNodo, self.lockSocketNodo, self.bitacora)
			self.lockVecinosSupervivientes.acquire()
			#print("Vecino que se va a anadir " + str(vecinoId))
			self.vecinosSupervivientes[vecinoId] = hiloSupervivencia
			self.lockVecinosSupervivientes.release()
			proceso_hiloSupervivencia = threading.Thread(target=self.metaSacaHiloSupervivencia, args=(vecinoId, hiloSupervivencia,))
			proceso_hiloSupervivencia.start()#Se crea el hilo

	#Metodo para activar vecino en la tabla vecinos, y meterlo en la tabla de vecinos
	#vecino: tupla que es (ip. puerto)
	#mensaje: mascara del vecino
	def respondieronVivo(self, vecino, mensaje):
		#mascara = bytesToInt(mensaje[1:2])
		mascara = (self.tablaAlcanzabilidad.obtenerKey(vecino))[1]
		self.lockVecinosSupervivientes.acquire()
		buzon = self.vecinosSupervivientes.get((vecino[0],mascara,vecino[1]))
		if buzon != None:
			buzon.meterBuzon(mensaje)
		self.lockVecinosSupervivientes.release()
		#print("El vecino " + str(vecino) + " indico que continua vivo")
		self.bitacora.escribir("ReceptorUDP: " + "El vecino " + str(vecino) + " indico que continua vivo")

	#Metodo para desactivar vecino en la tabla vecinos y sacar las entradas a las que se llevaban mediante este
	#vecino: tupla que es (ip. puerto)
	#mensaje: mascara del vecino
	def murioVecino(self, vecino, mensaje):
		#print("LARGO DEL PAQ " + str(len(mensaje)))
		self.bitacora.escribir("ReceptorUDP: " + "El vecino " + str(vecino) + " indico que se va a morir")
		#mascara = bytesToInt(mensaje[1:2])
		mascara = (self.tablaAlcanzabilidad.obtenerKey(vecino))[1]
		self.tablaVecinos.modificarBitActivo(vecino[0], mascara, vecino[1], False) #Se pone como un vecino no activo
		vecinosActivosConDistancia = self.tablaVecinos.obtenerVecinosActivosConDistancia()
		self.tablaAlcanzabilidad.limpiarPonerVecinosActivos(vecinosActivosConDistancia)

	#Metodo que procesa un mensaje de actualizacion de tabla
	#vecino: tupla que es (ip. puerto)
	#mensaje: mensaje recibido, viene la mascara en el segundo byte
	def mensajeActualizacionTabla(self, vecino, mensaje):
		self.bitacora.escribir("ReceptorUDP: " + "Se recibe mensaje de actializacion de tabla desde el vecino " + str(vecino))
		#mensajeQuitandoTipo = mensaje[2:]
		mensajeQuitandoTipo = mensaje[1:]
		#vecinoConMascara = vecino[0], bytesToInt( mensaje[1:2] ), vecino[1]
		mascara = (self.tablaAlcanzabilidad.obtenerKey(vecino))[1]
		vecinoConMascara = vecino[0], mascara, vecino[1]
		distanciaVecino = self.tablaVecinos.obtenerDistancia(vecino[0], mascara, vecino[1])
		proceso_actualizarTabla = threading.Thread(target=self.tablaAlcanzabilidad.actualizarTabla, args=(mensajeQuitandoTipo, vecinoConMascara, distanciaVecino,))
		proceso_actualizarTabla.start()#Se crea un hilo para actualizar la tabla de alcanzabilidad

	#Metodo que procesa un mensaje de enrutamiento o que me llego
	#vecino: tupla que es (ip. puerto)
	#mensaje: mensaje recibido, viene la mascara en el segundo byte, luego vienen los datos
	def mensajeRecibido(self, vecino, mensaje):
		#ipEmisor = bytesToIp(mensaje[1:5])
		#mascaraEmisor = bytesToInt(mensaje[5:6])
		#puertoEmisor = bytesToInt(mensaje[6:8])
		#ipDestino = bytesToIp(mensaje[8:12])
		#mascaraDestino = bytesToInt(mensaje[12:13])
		#puertoDestino = bytesToInt(mensaje[13:15])
		ipEmisor = bytesToIp(mensaje[1:5])
		puertoEmisor = bytesToInt(mensaje[5:7])
		ipDestino = bytesToIp(mensaje[7:11])
		puertoDestino = bytesToInt(mensaje[11:13])
		tamanno = bytesToInt(mensaje[13:15])
		textoMensaje = (mensaje[15:]).decode()
		nodoEmisor = self.tablaAlcanzabilidad.obtenerKey((ipEmisor, puertoEmisor))
		print("EMISOR " + str(nodoEmisor))
		#nodoEmisor = ipEmisor, puertoEmisor
		if (self.nodoId[0],self.nodoId[2]) == (ipDestino,puertoDestino):
			nodoDestino = self.nodoId
		else:
			nodoDestino = self.tablaAlcanzabilidad.obtenerKey((ipDestino, puertoDestino))
		print("DESTINO " + str(nodoDestino))
		#nodoDestino = ipDestino, puertoDestino
		if self.nodoId == nodoDestino:#Caso donde el mensaje que llega es para mi
			print("Se recibio un mensaje proveniente de " + str(nodoEmisor) + " el cual dice: " + textoMensaje)
			self.bitacora.escribir("ReceptorUDP: " + "Se recibio un mensaje proveniente de " + str(nodoEmisor) + " el cual dice: " + textoMensaje)
		else:#Caso donde el mensaje que llega hay que enrrutarlo
			time.sleep(0.5)
			print("Se recibio un mensaje proveniente de " + str(nodoEmisor) + " el cual va para " + str(nodoDestino))
			self.bitacora.escribir("ReceptorUDP: " + "Se recibio un mensaje proveniente de " + str(nodoEmisor) + " el cual va para " + str(nodoDestino))
			sigNodo = self.tablaAlcanzabilidad.obtenerSiguienteNodo(nodoDestino)
			self.bitacora.escribir("ReceptorUDP: " + "El mensaje se enruta a travez de " + str(sigNodo))
			self.lockSocketNodo.acquire()
			self.socketNodo.sendto(mensaje, (sigNodo[0], sigNodo[2])) #0 es la ip, 1 es el puerto
			self.lockSocketNodo.release()

	#Metodo encargado de ejecutar el ciclo de revisar si el vecino esta vivo
	# cuando muere regresa a este metodo y saca el hilo del diccionario
	#hiloSupervivencia: estructura del hilo que verifica si el vecino esta vivo
	def metaSacaHiloSupervivencia(self, vecinoId, hiloSupervivencia):
		hiloSupervivencia.iniciarCiclo()
		self.lockVecinosSupervivientes.acquire()
		del self.vecinosSupervivientes[vecinoId]
		self.lockVecinosSupervivientes.release()

	#Metodo encargado de recibir los mensajes que le envian al nodo
	def recibeMensajes(self):
		while 1:
			message, clientAddress = self.socketNodo.recvfrom(2048)
			tipoMensaje = bytesToInt(message[0:1])
			if tipoMensaje == 2:
				self.responderVivo(clientAddress, message)
			elif tipoMensaje == 3:#Creo que este caso no tiene sentido aqui, pero por si llegara uno, para decir que esta fuera de lugar
				self.respondieronVivo(clientAddress, message)
			elif tipoMensaje == 7:
				self.murioVecino(clientAddress, message)
			elif tipoMensaje == 1:
				self.mensajeActualizacionTabla(clientAddress, message)
			elif tipoMensaje == 5:
				self.mensajeRecibido(clientAddress, message)
			else:
				#print("Llego mensaje con tipo desconocido")
				self.bitacora.escribir("ReceptorUDP: " + "Llego mensaje con tipo desconocido")