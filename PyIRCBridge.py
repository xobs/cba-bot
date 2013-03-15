#Based on http://www.osix.net/modules/article/?id=780

import sys
from socket import socket
import string
import os
from Queue import Queue
from threading import Thread
from time import sleep

IDENT='CBA Testbot'
REALNAME='Cloudboat Armada'
OWNER='mrasmus' #The bot owner's nick
EOL='\r\n'
DEBUG=True

def sendtosocket(s,msg):
	print 'DEBUG:Sending message on socket ' + str(s.fileno()) + ':' + msg 
	s.send(msg+EOL)

class Server(Thread):
	def __init__(self,host,channel,nick='cbirc',port=6667,**kwargs):
		self.host = host
		self.port = port
		self.nick = nick
		self.channel = channel
		self.s = socket()
		self.targets = []
		super(Server, self).__init__(**kwargs)

	def run(self):
		self.s.connect((self.host, self.port))
		sendtosocket(self.s,'NICK '+self.nick)
		sendtosocket(self.s,'USER '+IDENT+' '+self.host+' bla :'+REALNAME)
		done = False
		while not done:
			line = self.s.recv(4096)
			print '****RAW:'+line
			if line == '':
				done = True
				print '****Socket on ' + self.host + ' closed.'
			elif line.find('NickServ') != -1:
				sendtosocket(self.s,'JOIN '+self.channel)
				print '****Joined channel '+self.channel+' on '+self.host
			elif (line.split()[0]=='PING'):
				sendtosocket(self.s,'PONG '+line.rstrip().split()[1])
				print '****Sending:'+'PONG '+line.rstrip().split()[1][1:]
			else:
				for t in self.targets:
					t.put(line)

class Repeater(Thread):
	def run(self):
		while True:
			sendtosocket(self.s,'PRIVMSG '+self.channel+' :'+self.q.get()+EOL)
			print 'Message sent to '+self.channel

server1=Server('irc.chatspike.net','#cbatest')
server2=Server('irc.chatspike.net','#cbatest1',nick='cbirc1')
repeater1 = Repeater()
repeater1.q = Queue()
repeater1.s = server2.s
repeater1.channel = server2.channel
server1.start()
server2.start()
repeater1.start()

sleep(5)
server1.targets+=[repeater1.q]
print 'Queue following server1, repeated to server2'

while True:
	x = 0
	#print '++++Received line: ||' + q1.get()

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
