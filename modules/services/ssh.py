import util, os, socket
from threading import Thread
from time import sleep

#
# emulate a basic SSH service; store usernames/passwords but reject them all.
# Certs too.
#
class SSHService:
	def __init__(self):
		self.running = False
		self.priv_key = None
		self.dump = False
		self.log_data = False
		self.log_file = None
		self.fail = False

	#
	# If we weren't given a private key, remove the temp we generated
	#
	def cleanup(self):
		if self.priv_key is None:
			os.system('rm -f privkey.key')
	
	# dispatch as a thread; this is called from gui
	def initialize_bg(self):
		try:
			# try importing here so we can catch it right away
			import paramiko
		except ImportError:
			util.Error('Paramiko libraries required for this module.')
			return False

		while True:
			try:
				self.priv_key = raw_input('Enter private key path or [enter] to generate: ')
				if len(self.priv_key) < 2:
					self.priv_key = None
				break
			except:
				pass
			
		util.Msg('Initializing SSH server...')
		thread = Thread(target=self.initialize)
		thread.start()
		return True
	
	# initialization
	def initialize(self):
		try:
			# try importing here so we can catch it right away
			import paramiko
		except ImportError:
			util.Error('Paramiko libraries required for this module.')
			return

		level = getattr(paramiko.common, 'CRITICAL')
		paramiko.common.logging.basicConfig(level=level)
		# if the user did not specify a key, generate one
		if self.priv_key is None:
			if not util.check_program('openssl'):
				util.Error('OpenSSL required to generate cert/key files.')
				return
			if not util.does_file_exist('./privkey.key'):
				util.debug('Generating RSA private key...')
				tmp = util.init_app('openssl genrsa -out privkey.key 2048', True)
				util.debug('privkey.key was generated.')

		try:
			server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
			server_socket.bind(('0.0.0.0', 22))
			server_socket.listen(1)
			self.running = True

			while self.running:
				con, addr = server_socket.accept()
				
				pkey = paramiko.RSAKey.from_private_key_file('./privkey.key')
				transport = paramiko.Transport(con)
				transport.add_server_key(pkey)
				transport.set_subsystem_handler('handler', paramiko.SFTPServer, SSHStub)

				context = { 'dump' : self.dump, 'log_data' : self.log_data,
							'log_file': self.log_file }
				server = SSHStub(context)
				try:
					transport.start_server(server=server)
					channel = transport.accept()
					while transport.is_active():
						sleep(1)
				except socket.error as j:
					if j.errno == 104:
					 	# just means we've got a broken pipe, or
						# the peer dropped unexpectedly
					 	continue
					else:
						raise Exception()
				except EOFError:
					# thrown when we dont get the key correctly, or
					# remote host gets mad because the key changed
					continue
				except:
					raise Exception()
		except KeyboardInterrupt:
			pass
		except Exception as j:
			util.Error('Error with server: %s'%j)
		finally:
			self.running = False
			self.cleanup()
	
	# dump connections/passwords
	def view(self):
		try:
			while True:
				self.dump = True
		except KeyboardInterrupt:
			self.dump = False

	# logging
	def log(self, opt, log_loc):
		if opt and not self.log_data:
			try:
				util.debug('Starting SSH logger.')
				self.log_file = open(log_loc, 'w+')
			except Exception, j:
				util.Error('Error opening log file: %s'%j)
				self.log_file = None
				return
			self.log_data = True
		elif not opt and self.log_data:
			try:
				self.log_file.close()
				self.log_file = None
				self.log_data = False
				util.debug('SSH logger shutdown complete.')
			except Exception, j:
				util.Error('Error closing logger: %s'%j)

	# stop the server
	def shutdown(self):
		util.Msg('Shutting SSH server down...')
		self.running = False
		if self.log_data:
			self.log(False, None)
		util.Msg('SSH server shutdown.')

#
# Handler for credentials
#
try:
	class SSHStub (paramiko.ServerInterface):
		def __init__(self, context, *args):
			self.context = context
			paramiko.ServerInterface.__init__(self, *args)
	
		# handle credentials and always reject 
		def check_auth_password(self, username, password):
			if self.context['dump']:
				util.Msg('Received login attempt: %s:%s'%(username, password))
			if self.context['log_data']:
				self.context['log_file'].write('Received login: %s:%s\n'%(username, password))
			return paramiko.AUTH_FAILED
		def check_channel_request(self, kind, chanid):
			return paramiko.OPEN_SUCCEEDED
except NameError as j:
	if 'paramiko' in j.message:
		# we're going to catch this later, but with the way python parses classes
		# we need to skip it for now.
		pass
	else:
		util.Error('Error: %s'%j.message)