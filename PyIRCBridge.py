#Based on http://www.osix.net/modules/article/?id=780

import sys
from socket import socket
import string
import os
from Queue import Queue
from threading import Thread
from time import sleep
from json import loads, dumps
from re import search, split, sub

IDENT='CBA Testbot'
REALNAME='Cloudboat Armada'
OWNER='mrasmus' #The bot owner's nick
EOL='\r\n'
DEBUG=True

def sendtosocket(s,msg):
	print 'DEBUG:Sending message on socket ' + str(s.fileno()) + ':' + msg 
	s.send(msg+EOL)

class Server(Thread):
	def __init__(self,name,host,channels,nick='cbirc',port=6667,serverpass=None,nspass=None,**kwargs):
		self.servername = name
		self.host = host
		self.serverpass = serverpass
		self.nspass = nspass
		self.port = port
		self.nick = nick
		self.channels = channels
		self.s = socket()
		self.targets = []
		super(Server, self).__init__(**kwargs)

	def run(self):
		self.s.connect((self.host, self.port))
		if (self.serverpass is not None):
			sendtosocket(self.s, 'PASS '+self.serverpass)
		sendtosocket(self.s,'NICK '+self.nick)
		sendtosocket(self.s,'USER '+IDENT+' '+self.host+' bla :'+REALNAME)
		done = False
		while not done:
			line = self.s.recv(4096)
			print '****RAW:'+line
			if line == '':
				done = True
				print '****Socket on ' + self.host + ' closed.'
			if line.find('NOTICE ' + self.nick + ' :This nickname is registered.')!=-1:
				print "Identify to nickserv...\n"
				sendtosocket(self.s,'PRIVMSG NickServ IDENTIFY '+self.nspass+'\r\n')
			if (line.find('You are now identified for') != -1) or (line.find('End of /MOTD command') != -1):
				print '**************JOINING CHANNELS ON ' + self.host
				for chan in self.channels:
					sendtosocket(self.s,'JOIN '+chan)
					print '****Joined channel '+chan+' on '+self.host
			elif (line.split()[0]=='PING'):
				sendtosocket(self.s,'PONG '+line.rstrip().split()[1])
				print '****Sending:'+'PONG '+line.rstrip().split()[1][1:]
			else:
				for l in [l for l in split('\r\n',line) if 'PRIVMSG #' in l]:
					m = search(':(.*?)!.* PRIVMSG (#[^ ,]+) :(.+)',l)
					if (m.group(3)[:7] == "\x01ACTION"):
						msg = '{'+m.group(1)+'} '+m.group(3)[8:]
					else:
						msg = '{'+m.group(1)+'}: '+m.group(3)
					print "Message on " + self.servername + m.group(2) + ": " + msg
					for t in self.targets:
						t.put(msg)

class Repeater(Thread):
	def __init__(self,sock,chan,**kwargs):
		self.q = Queue()
		self.s = sock
		self.channel = chan
		super(Repeater, self).__init__(**kwargs)

	def run(self):
		while True:
			sendtosocket(self.s,'PRIVMSG '+self.channel+' :'+self.q.get()+EOL)
			print 'Message sent to '+self.channel

servers = {} 
srvdict = loads(os.environ["IRCSERVERS"])
for key in srvdict.keys():
	srv=srvdict[key]
	servers[key] = Server(key,srv['host'],srv['channels'],srv['nick'],srv['port'],srv['serverpass'],srv['nspass'])
for server in servers.values():
	server.start()

sleep(5)

for sub in loads(os.environ['IRCSUBS']):
	print 'sending messages from ' + servers[sub[1]].servername + ' to '+servers[sub[0]].servername + sub[2]
	r = Repeater(servers[sub[0]].s,sub[2])
	r.start()
	servers[sub[1]].targets+=[r.q]

while True:
	#print '++++Received line: ||' + q1.get()
	pass

HOST='irc.chatspike.net' #The server we want to connect to
PORT=6667 #The connection port which is usually 6667
NICK='testbot001' #The bot's nickname
IDENT='CBA Testbot'
REALNAME='Cloudboat Armada'
OWNER='mrasmus' #The bot owner's nick
CHANNELINIT='#cbatest' #The default channel for the bot
readbuffer='' #Here we store all the messages from server 

s=socket( ) #Create the socket
s.connect((HOST, PORT)) #Connect to server
s.send('NICK '+NICK+'\r\n') #Send the nick to server
s.send('USER '+IDENT+' '+HOST+' bla :'+REALNAME+'\r\n') #Identify to server 

while 1:
  line=s.recv(500) #recieve server messages
  splitup = line.rstrip().split()
  print line #server message is output
  if line.find('Welcome to ChatSpike, ')!=-1: #This is Crap(I wasn't sure about it but it works)
    s.send('JOIN '+CHANNELINIT+'\r\n') #Join a channel
    print "========Joining channel"
  elif (splitup[0]=='PING'): #If server pings then pong
    s.send('PONG '+splitup[1]+'\r\n') 
    print "========Sending PONG"
  elif line.find('PRIVMSG')!=-1: #Call a parsing function
    parsemsg(line)
    line=line.rstrip() #remove trailing 'rn'
    line=line.split()

def parsemsg(msg):
  complete=msg[1:].split(':',1) #Parse the message into useful data
  info=complete[0].split(' ')
  msgpart=complete[1]
  sender=info[0].split('!')
  if msgpart[0]=='`' and sender[0]==OWNER: #Treat all messages starting with '`' as command
    cmd=msgpart[1:].split(' ')
    if cmd[0]=='op':
      s.send('MODE '+info[2]+' +o '+cmd[1]+'n')
    if cmd[0]=='deop':
      s.send('MODE '+info[2]+' -o '+cmd[1]+'n')
    if cmd[0]=='voice':
      s.send('MODE '+info[2]+' +v '+cmd[1]+'n')
    if cmd[0]=='devoice':
      s.send('MODE '+info[2]+' -v '+cmd[1]+'n')
    if cmd[0]=='sys':
      syscmd(msgpart[1:],info[2])

  if msgpart[0]=='-' and sender[0]==OWNER : #Treat msgs with - as explicit command to send to server
    cmd=msgpart[1:]
    s.send(cmd+'n')
    print 'cmd='+cmd 

def syscmd(commandline,channel):
  cmd=commandline.replace('sys ','')
  cmd=cmd.rstrip()
  os.system(cmd+' >temp.txt')
  a=open('temp.txt')
  ot=a.read()
  ot.replace('n','|')
  a.close()
  s.send('PRIVMSG '+channel+' :'+ot+'n')
  return 0 
