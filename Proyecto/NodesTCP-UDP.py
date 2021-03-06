import sys
import threading
import socket
import errno
import codecs
import os
from socket import error as SocketError

class Mensaje:
	def __init__(self,ip,puerto,mensaje):
		self.ip = ip
		self.puerto = puerto
		self.mensaje = mensaje


class Red:
	def __init__(self,ipFuente,puertoFuente,ipRed, mascaraRed, costo):
		self.ipFuente = ipFuente
		self.puertoFuente = puertoFuente
		self.ipRed = ipRed
		self.mascaraRed = mascaraRed 
		self.costo = costo

	def soyEsaRed(self, ipRed, mascaraRed):
		if ipRed == self.ipRed and mascaraRed == self.mascaraRed:
			return True
		return False

	def soyEsaFuente(self, ipFuente, puertoFuente):
		if ipFuente == self.ipFuente and puertoFuente == self.puertoFuente:
			return True
		return False

	def costoMenor(self, costo):
		if costo < self.costo:
			return True
		return False

	def actualizarRed(self,ipFuente,puertoFuente,ipRed, mascaraRed, costo):
		self.ipFuente = ipFuente
		self.puertoFuente = puertoFuente
		self.ipRed = ipRed
		self.mascaraRed = mascaraRed 
		self.costo = costo


class TablaAlcanzabilidad:
	tabla = list()
	#lockTablaAlcanzabilidad = threading.Lock()
	
	def __init__(self):
		self.tabla = list()
		#self.lockTablaAlcanzabilidad = threading.Lock()

	def existeRed(self, ipRed, mascaraRed):
		#self.lockTablaAlcanzabilidad.acquire()
		i = 0
		largo = len(self.tabla)
		while i < largo:
			if self.tabla[i].soyEsaRed(ipRed, mascaraRed) :
				#self.lockTablaAlcanzabilidad.release()
				return i
			i = i + 1
		#self.lockTablaAlcanzabilidad.release()
		return -1

	def imprimirTabla(self):
		#self.lockTablaAlcanzabilidad.acquire()
		i = 0
		largo = len(self.tabla)
		while i < largo:
			ipFuente = self.tabla[i].ipFuente
			puertoFuente = self.tabla[i].puertoFuente
			ipA = int.from_bytes( self.tabla[i].ipRed[0:1], byteorder='big' )
			ipB = int.from_bytes( self.tabla[i].ipRed[1:2], byteorder='big' )
			ipC = int.from_bytes( self.tabla[i].ipRed[2:3], byteorder='big' )
			ipD = int.from_bytes( self.tabla[i].ipRed[3:4], byteorder='big' )

			mascaraRed = int.from_bytes( self.tabla[i].mascaraRed, byteorder='big' )
			costo = int.from_bytes( self.tabla[i].costo, byteorder='big' )
			print(str(ipFuente) + " " + str(puertoFuente) + " " + str(ipA) + "." + str(ipB) + "." + str(ipC) + "." + str(ipD) + " " + str(mascaraRed) + " " + str(costo) )

			i = i + 1

		#self.lockTablaAlcanzabilidad.release()

	def actualizarTabla(self, mensaje):
		#self.lockTablaAlcanzabilidad.acquire()

		ipFuenteNuevo = mensaje.ip
		puertoFuenteNuevo = mensaje.puerto
		bytesMensaje = mensaje.mensaje

		cantTuplas = int(codecs.encode(bytesMensaje[0:2], 'hex_codec'))
		i = 0
		while i < cantTuplas:
			ipRedNuevo = bytesMensaje[(i*8)+2:(i*8)+6]
			mascaraRedNuevo = bytesMensaje[(i*8)+6:(i*8)+7]
			costoNuevo = bytesMensaje[(i*8)+7:(i*8)+10]

			exite = self.existeRed(ipRedNuevo, mascaraRedNuevo)
			if exite == -1 :
				#Se crea una nueva tupla
				self.tabla.append(Red(ipFuenteNuevo,puertoFuenteNuevo,ipRedNuevo, mascaraRedNuevo, costoNuevo))
			else:
				#se actualiza la tupla de ser necesario
				if self.tabla[exite].costoMenor(costoNuevo) :
					self.tabla[exite].actualizarRed(ipFuenteNuevo,puertoFuenteNuevo,ipRedNuevo, mascaraRedNuevo, costoNuevo);
				#Si el costo es mayor queda como antes
			i = i + 1

		#self.lockTablaAlcanzabilidad.release()

	def borrarFuente(self,ipFuente, puetoFuente):
		#self.lockTablaAlcanzabilidad.acquire()
		i = 0
		largo = len(self.tabla)
		while i < largo:
			if self.tabla[i].soyEsaFuente(ipFuente, puetoFuente) :
				self.tabla.pop(i)
			i = i + 1

		#self.lockTablaAlcanzabilidad.release()

class UDPNode:
	
	mensajesRecibidos = list()
	tablaAlcanzabilidad = TablaAlcanzabilidad()

	def guardarMensaje(self,mensaje):
		self.mensajesRecibidos.append(mensaje)

	def recibeMensajes(self, serverSocket):
		while 1:
			message, clientAddress = serverSocket.recvfrom(2048)
			mensaje = Mensaje(clientAddress[0],clientAddress[1], message)

			cantTuplas = int(codecs.encode(message[0:2], 'hex_codec'))
			mensajeSalir = int.from_bytes( message[2:3], byteorder='big' )
			#Si el mensaje recibido es la palabra close se cierra la aplicacion
			if cantTuplas == 1 and len(message) == 3 and mensajeSalir == 0:
				print("Conexion Terminada")
				self.tablaAlcanzabilidad.borrarFuente(clientAddress[0],clientAddress[1])
			else:
				self.guardarMensaje(mensaje)
				self.imprimirMensaje(mensaje)
				self.tablaAlcanzabilidad.actualizarTabla(mensaje)

	def procRecibeMsg(self, ip, puerto):
		serverSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		serverSocket.bind((ip, puerto))
		self.recibeMensajes(serverSocket)

	def imprimirMensaje(self, mensaje):
		ip = mensaje.ip
		puerto = mensaje.puerto
		bytesMensaje = mensaje.mensaje

		cantTuplas = int(codecs.encode(bytesMensaje[0:2], 'hex_codec'))
		i = 0
		#print("\n\nIPf = " + str(ip) + " Puerto = " + str(puerto) + " Envio el siguiente mensaje: ")
		print("IPf = " + str(ip) + " Puerto = " + str(puerto) + " Envio el siguiente mensaje: ")
		while i < cantTuplas:
			ipA = int.from_bytes( bytesMensaje[(i*8)+2:(i*8)+3], byteorder='big' )
			ipB = int.from_bytes( bytesMensaje[(i*8)+3:(i*8)+4], byteorder='big' )
			ipC = int.from_bytes( bytesMensaje[(i*8)+4:(i*8)+5], byteorder='big' )
			ipD = int.from_bytes( bytesMensaje[(i*8)+5:(i*8)+6], byteorder='big' )
			mascara = int.from_bytes( bytesMensaje[(i*8)+6:(i*8)+7], byteorder='big' )
			costo = int.from_bytes( bytesMensaje[(i*8)+7:(i*8)+10], byteorder='big' )
			print( str(ipA) + "." + str(ipB) + "." + str(ipC) + "." + str(ipD) + " " + str(mascara) + " " + str(costo) )
			i = i + 1
		#print("\n\n")

	def imprimirMensajes(self):
		i = 0
		largo = len(self.mensajesRecibidos)
		while i < largo:
			self.imprimirMensaje( self.mensajesRecibidos[i] )
			i = i + 1

	def tuplaToBytes(self, tupla):
	    tupladiv = tupla.split(' ')
	    numeroip = tupladiv[0]
	    myip = numeroip.split('.')
	    bytesmios = bytearray()
	    for x in range(0, 4):
	        ipnum = int(myip[x])
	        bytesmios += (ipnum).to_bytes(1, byteorder='big')
	    masc = int(tupladiv[1])
	    bytesmios += (masc).to_bytes(1, byteorder='big')
	    costo = int(tupladiv[2])
	    bytesmios += (costo).to_bytes(3, byteorder='big')
	    #print(bytesmios)
	    return bytesmios

	def leerMensaje(self):
		#print('Ingrese la cantidad de tuplas que quiere enviar:')
		entradas = input()
		vectorBytes = bytearray((int(entradas)).to_bytes(2, byteorder='big'))
		i = 0
		
		while i < int(entradas):
			#print('Ingrese la tupla:')
			tupla = input()
			vectorBytes += self.tuplaToBytes(tupla)
			i = i + 1
			#print('\n')
		return vectorBytes

	#Metodo que envia un mensaje mediante UDP al IP + socket que esocgio al inicio.
	def envioMensajeUDP(self, mensajeExit):
			if mensajeExit == 1:
				serverNameS = input('Ingrese el IP del servidor al que quiere enviar el mensaje: ')
				serverPortS = input('Ingrese el puerto al que desea enviar: ')
				message = self.leerMensaje()
				clientSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				clientSocket.sendto(message, (serverNameS, int(serverPortS)))
				clientSocket.close()
			else:
				mensaje = bytearray((1).to_bytes(2, byteorder='big'))# cant tuplas
				mensaje += (0).to_bytes(1, byteorder='big')
				#clientSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				#clientSocket.sendto(mensaje, (serverNameS, int(serverPortS)))
				#clientSocket.close()
			#print('El mensaje fue enviado.\n')

	#def borrarme(self):
	#	mensaje = bytearray((1).to_bytes(2, byteorder='big'))# cant tuplas
	#	mensaje += (0).to_bytes(1, byteorder='big')

	#	i = 0
	#	cant = len(self.conexiones)
	#	while i < cant:
	#		self.conexiones[i].enviarMensaje(mensaje)
	#		i = i + 1
	#	self.cerrarConexiones()
	#	return

	#Metodo que despliega Menu principal de UDP
	def despligueMenuUDP(self):
		print('Menu principal del modulo de Red UDP: \n'
					'\t1. Enviar un mensaje. \n'
					'\t2. Ver mensajes recibidos. \n'
					'\t3. Imprimir tabla de alcanzabilidad.\n'
					'\t4. Cerrar servidor de mensajes.')
		bandera = True
		while bandera == True:
			taskUsuario = input('Que desea hacer:')
			if taskUsuario == '1':
				self.envioMensajeUDP(1)
			elif taskUsuario == '2':
				print("\n\n")
				print('Mensajes recibidos:')
				self.imprimirMensajes()
				print("\n\n")
			elif taskUsuario == '3':
				print("\n\n")
				print('Tabla de alcanzabilidad:')
				self.tablaAlcanzabilidad.imprimirTabla()
				print("\n\n")
			elif taskUsuario == '4':
				bandera = False
				#self.envioMensajeUDP(2)
				print('Salida.')
				os._exit(1)

			else:
				print('Ingrese opcion valida.')

class ReceptorTCP:
	mensajesRecibidos = list()
	tablaAlcanzabilidad = TablaAlcanzabilidad()

	def __init__(self,mensajesRecibidos, tablaAlcanzabilidad):
		self.mensajesRecibidos = mensajesRecibidos
		self.tablaAlcanzabilidad = tablaAlcanzabilidad

	def guardarMensaje(self,mensaje):
		self.mensajesRecibidos.append(mensaje)

	def imprimirMensaje(self, mensaje):
		ip = mensaje.ip
		puerto = mensaje.puerto
		bytesMensaje = mensaje.mensaje

		cantTuplas = int(codecs.encode(bytesMensaje[0:2], 'hex_codec'))
		i = 0
		print("IPf = " + str(ip) + " Puerto = " + str(puerto) + " Envio el siguiente mensaje: ")
		while i < cantTuplas:
			ipA = int.from_bytes( bytesMensaje[(i*8)+2:(i*8)+3], byteorder='big' )
			ipB = int.from_bytes( bytesMensaje[(i*8)+3:(i*8)+4], byteorder='big' )
			ipC = int.from_bytes( bytesMensaje[(i*8)+4:(i*8)+5], byteorder='big' )
			ipD = int.from_bytes( bytesMensaje[(i*8)+5:(i*8)+6], byteorder='big' )
			mascara = int.from_bytes( bytesMensaje[(i*8)+6:(i*8)+7], byteorder='big' )
			costo = int.from_bytes( bytesMensaje[(i*8)+7:(i*8)+10], byteorder='big' )
			print( str(ipA) + "." + str(ipB) + "." + str(ipC) + "." + str(ipD) + " " + str(mascara) + " " + str(costo) )
			i = i + 1
		
	def imprimirMensajes(self):
		i = 0
		largo = len(self.mensajesRecibidos)
		while i < largo:
			self.imprimirMensaje( self.mensajesRecibidos[i] )
			i = i + 1

	def establecerConexion(self, conexion, addr):
		while True:
			#Recibimos el mensaje, con el metodo recv recibimos datos y como parametro 
			#la cantidad de bytes para recibir
			try:
				recibido = conexion.recv(1024)
			except SocketError:
				print("Conexion Perdida")
				self.tablaAlcanzabilidad.borrarFuente(addr[0],addr[1])
				break

			if(recibido == b''):#Salida para cuando el otro muere antes de mandar el primer mensaje
				print("Conexion Perdida")
				self.tablaAlcanzabilidad.borrarFuente(addr[0],addr[1])
				break

			cantTuplas = int(codecs.encode(recibido[0:2], 'hex_codec'))
			#mensajeSalir = int.from_bytes( recibido[2:3], byteorder='big' )
			#Si el mensaje recibido es la palabra close se cierra la aplicacion
			if cantTuplas == 1 and len(recibido) == 3:
				print("Conexion Terminada")
				self.tablaAlcanzabilidad.borrarFuente(addr[0],addr[1])
				break
			
			mensaje = Mensaje(addr[0],addr[1],recibido)
			self.guardarMensaje(mensaje)
			self.imprimirMensaje(mensaje) 
			self.tablaAlcanzabilidad.actualizarTabla(mensaje)
			
		conexion.close()

	def recibir(self,ip,puerto):
		#instanciamos un objeto para trabajar con el socket
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		 
		#Con el metodo bind le indicamos que puerto debe escuchar y de que servidor esperar conexiones
		#Es mejor dejarlo en blanco para recibir conexiones externas si es nuestro caso
		s.bind((ip,puerto))
		 
		#Aceptamos conexiones entrantes con el metodo listen, y ademas aplicamos como parametro
		#El numero de conexiones entrantes que vamos a aceptar
		s.listen(5)
		
		while True:
			#Instanciamos un objeto sc (socket cliente) para recibir datos, al recibir datos este 
			#devolvera tambien un objeto que representa una tupla con los datos de conexion: IP y puerto
			conexion, addr = s.accept()
			
			thread_servidor = threading.Thread(target=self.establecerConexion, args=(conexion,addr))
			thread_servidor.start()
			print("Conexion recibida")
		
		#Cerramos la instancia del socket cliente y servidor
		s.close()

class ConexionAbierta:

	def __init__(self,ip,puerto,socketEmisorTCP):
		self.socketEmisorTCP = socketEmisorTCP
		self.ip = ip
		self.puerto = puerto

	def enviarMensaje(self,mensaje):
		try:
			sent = self.socketEmisorTCP.send(mensaje)
		except SocketError as e:
				print("ERROR AL ENVIAR EL MENSAJE")
				return False
		else:
			if sent == 0:
				print("ERROR AL ENVIAR EL MENSAJE")
				return False
		return True

	def cerrarConexion(self):
		self.socketEmisorTCP.close()

	def soyLaConexion(self,ip,puerto):
		if self.ip == ip and self.puerto == puerto:
			return True
		
		return False


class EmisorTCP:
	#Objeto para guardar conexiones
	conexiones = list()

	mensajesRecibidos = list()

	tablaAlcanzabilidad = TablaAlcanzabilidad()

	def __init__(self,mensajesRecibidos, tablaAlcanzabilidad):
		self.mensajesRecibidos = mensajesRecibidos
		self.tablaAlcanzabilidad = tablaAlcanzabilidad
		self.conexiones = list()

	def hacerConexion(self, ip,puerto):
		#se crea el socket para enviar
		socketEmisorTCP = socket.socket()
		conexion = ConexionAbierta(ip,puerto,socketEmisorTCP)
		#Se establece la conexion con el receptorTCP mediante la ip y el puerto
		socketEmisorTCP.connect((ip, puerto))
		print("Conexion establecida")
		self.conexiones.append(conexion)

	#retorna el numero del indice de la conexion si lo encuentra, sino entonces retorna -1
	def buscarConexion(self, ip,puerto):
		i = 0;
		largo = len(self.conexiones)
		while i < largo:
			if self.conexiones[i].soyLaConexion(ip,puerto) :
				return i
			i = i + 1
		return -1

	def cerrarUnaConexion(self, ip,puerto):
		i = 0;
		largo = len(self.conexiones)
		while i < largo:
			if self.conexiones[i].soyLaConexion(ip,puerto) :
				self.conexiones[i].cerrarConexion()
				self.conexiones.remove(self.conexiones[i])
				break
			i = i + 1

	def cerrarConexiones(self):
		while len(self.conexiones) != 0:
			self.conexiones[0].cerrarConexion()
			self.conexiones.remove(self.conexiones[0])

	def tuplaToBytes(self,tupla):
	    tupladiv = tupla.split(' ')
	    numeroip = tupladiv[0]
	    myip = numeroip.split('.')
	    bytesmios = bytearray()
	    for x in range(0, 4):
	        ipnum = int(myip[x])
	        bytesmios += (ipnum).to_bytes(1, byteorder='big')
	    masc = int(tupladiv[1])
	    bytesmios += (masc).to_bytes(1, byteorder='big')
	    costo = int(tupladiv[2])
	    bytesmios += (costo).to_bytes(3, byteorder='big')
	    return bytesmios

	def leerMensaje(self):
		entradas = input()
		vectorBytes = bytearray((int(entradas)).to_bytes(2, byteorder='big'))
		i = 0
		while i < int(entradas):
			tupla = input()
			if entradas == "1" and tupla == "0":
				vectorBytes += (0).to_bytes(1, byteorder='big')
			else:
				vectorBytes += self.tuplaToBytes(tupla)
			i = i + 1
		return vectorBytes

	def imprimirMensaje(self, mensaje):
		ip = mensaje.ip
		puerto = mensaje.puerto
		bytesMensaje = mensaje.mensaje

		cantTuplas = int(codecs.encode(bytesMensaje[0:2], 'hex_codec'))
		i = 0
		print("IPf = " + str(ip) + " Puerto = " + str(puerto) + " Envio el siguiente mensaje: ")
		while i < cantTuplas:
			ipA = int.from_bytes( bytesMensaje[(i*8)+2:(i*8)+3], byteorder='big' )#codecs.encode(bytesMensaje[(i*8)+2:(i*8)+3], 'hex_codec') )
			ipB = int.from_bytes( bytesMensaje[(i*8)+3:(i*8)+4], byteorder='big' )#codecs.encode(bytesMensaje[(i*8)+3:(i*8)+4], 'hex_codec') )
			ipC = int.from_bytes( bytesMensaje[(i*8)+4:(i*8)+5], byteorder='big' )#codecs.encode(bytesMensaje[(i*8)+4:(i*8)+5], 'hex_codec') )
			ipD = int.from_bytes( bytesMensaje[(i*8)+5:(i*8)+6], byteorder='big' )#codecs.encode(bytesMensaje[(i*8)+5:(i*8)+6], 'hex_codec') )
			mascara = int.from_bytes( bytesMensaje[(i*8)+6:(i*8)+7], byteorder='big' )#codecs.encode(bytesMensaje[(i*8)+6:(i*8)+7], 'hex_codec') )
			costo = int.from_bytes( bytesMensaje[(i*8)+7:(i*8)+10], byteorder='big' )#codecs.encode(bytesMensaje[(i*8)+7:(i*8)+10], 'hex_codec') )
			print( str(ipA) + "." + str(ipB) + "." + str(ipC) + "." + str(ipD) + " " + str(mascara) + " " + str(costo) )
			i = i + 1

	def imprimirMensajes(self):
		i = 0
		largo = len(self.mensajesRecibidos)
		while i < largo:
			self.imprimirMensaje( self.mensajesRecibidos[i] )
			i = i + 1

	def enviarMensaje(self):
		ip = input("Digite la ip del destinatario: ")
		puerto = input("Digite el puerto del destinatario: ")

		indice = self.buscarConexion(ip,int(puerto))

		if indice == -1:
			self.hacerConexion(ip,int(puerto))
			print("Nueva conexion")
			mensaje = self.leerMensaje()
			respEnvio = self.conexiones[len(self.conexiones)-1].enviarMensaje(mensaje)
			if respEnvio == False:
				self.cerrarUnaConexion(ip,int(puerto))
			if len(mensaje) == 3:
				self.conexiones.pop(len(self.conexiones)-1)
		else:
			print("Conexion existente")
			mensaje = self.leerMensaje()
			respEnvio = self.conexiones[indice].enviarMensaje(mensaje)
			if respEnvio == False:
				self.cerrarUnaConexion(ip,int(puerto))
			if len(mensaje) == 3:
				self.conexiones.pop(indice)

	def borrarme(self):
		mensaje = bytearray((1).to_bytes(2, byteorder='big'))# cant tuplas
		mensaje += (0).to_bytes(1, byteorder='big')

		i = 0
		cant = len(self.conexiones)
		while i < cant:
			self.conexiones[i].enviarMensaje(mensaje)
			i = i + 1
		self.cerrarConexiones()
		return

	def menu(self):#HACER UN WHILE CON UN MENU 
		print('Menu principal del modulo de Red TCP: \n'
					'\t1. Enviar un mensaje. \n'
					'\t2. Ver mensajes recibidos. \n'
					'\t3. Imprimir tabla de alcanzabilidad. \n'
					'\t4. Cerrar nodo.')
		bandera = True
		while bandera == True:
			taskUsuario = input('Que desea hacer:')
			if taskUsuario == '1':
				self.enviarMensaje()
			elif taskUsuario == '2':
				print("\n\n")
				print('Mensajes recibidos:')
				self.imprimirMensajes()
				print("\n\n")
			elif taskUsuario == '3':
				print("\n\n")
				print('Tabla de alcanzabilidad:')
				self.tablaAlcanzabilidad.imprimirTabla()
				print("\n\n")
			elif taskUsuario == '4':
				bandera = False
				self.borrarme()
				print('Salida.')
				os._exit(1)
				#proceso_repetorTcp.exit()
			else:
				print('Ingrese una opcion valida.')


class NodoTCP:

	def iniciarNodoTCP(self,ip,puerto):
		lockMensajesRecibidos = threading.Lock()

		lockMensajesRecibidos.acquire()
		mensajesRecibidos = list()
		lockMensajesRecibidos.release()

		tablaAlcanzabilidad = TablaAlcanzabilidad()

		repetorTcp = ReceptorTCP(mensajesRecibidos, tablaAlcanzabilidad)
		proceso_repetorTcp = threading.Thread(target=repetorTcp.recibir, args=(ip,puerto,))
		proceso_repetorTcp.start()

		emisorTcp = EmisorTCP(mensajesRecibidos, tablaAlcanzabilidad)
		proceso_emisorTcp = threading.Thread(target=emisorTcp.menu, args=())
		proceso_emisorTcp.start()


def comando(comandosolicitado):
	ip = ""
	puerto = ""
	if comandosolicitado.find("salir") == 0 :
		sys.exit()
	if comandosolicitado.find("creaNodo-") == 0 :
		if comandosolicitado.find("pseudoBGP") == 9:
			finalIp = comandosolicitado[19:].find(" ")
			finalIp = finalIp + 1 + 19
			ip =  comandosolicitado[19:finalIp]
			inicioPuerto = finalIp
			puerto = comandosolicitado[inicioPuerto:]
			nodoTCP = NodoTCP()
			nodoTCP.iniciarNodoTCP(ip,int(puerto))
			return 1
		else:
			if comandosolicitado.find("intAS") == 9:
				finalIp = comandosolicitado[15:].find(" ")
				finalIp = finalIp + 1 + 15
				ip =  comandosolicitado[15:finalIp]
				inicioPuerto = finalIp
				puerto = comandosolicitado[inicioPuerto:]
				nodoUDP = UDPNode()
				thrdRecibeMensaje = threading.Thread(target = nodoUDP.procRecibeMsg, args = (ip, int(puerto),))
				thrdRecibeMensaje.start()
				thrdRecibeMensaje = threading.Thread(target = nodoUDP.despligueMenuUDP, args = ())
				thrdRecibeMensaje.start()
				#udp.despligueMenuUDP()
				return 1
			else:
				print("Comando no valido")
				return -1
	else:
		print("Comando no valido")
		return -1

def consola():
	listo = -1
	while listo == -1:
		comandoDigitado = input(">")
		listo = comando(comandoDigitado)


if __name__ == '__main__':
	consola()