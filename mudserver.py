"""    
Basic MUD server module for creating text-based Multi-User Dungeon (MUD) games.

Contains one class, MudServer, which can be instantiated to start a server running
then used to send and receive messages from players.

author: Mark Frimston - mfrimston@gmail.com
"""


import socket
import select
import time


class MudServer(object):    
    """    
    A basic server for text-based Multi-User Dungeon (MUD) games. 
    
    Once created, the server will listen for players connecting using Telnet. 
    Messages can then be sent to and from multiple connected players.
    
    The 'update' method should be called in a loop to keep the server running.
    """

    # An inner class which is instantiated for each connected client to store
    # info about them
    
    class Client(object):
        "Holds information about a connected player"
        
        socket = None   # the socket object used to communicate with this client
        address = ""    # the ip address of this client
        buffer = ""     # holds data send from the client until a full message is received
        lastcheck = 0   # the last time we checked if the client was still connected
        named = False   # whether or not the client has entered their name yet
        
        def __init__(self,socket,address,buffer,lastcheck):
            self.socket = socket
            self.address = address
            self.buffer = buffer
            self.lastcheck = lastcheck
            self.named = False


    # Used to store different types of occurences            
    EVENT_NEW_PLAYER = 1
    EVENT_PLAYER_LEFT = 2
    EVENT_COMMAND = 3
    
    # Different states we can be in while reading data from client
    # See _process_sent_data function
    READ_STATE_NORMAL = 1
    READ_STATE_COMMAND = 2
    READ_STATE_SUBNEG = 3
    
    # Command codes used by Telnet protocol
    # See _process_sent_data function
    TN_INTERPRET_AS_COMMAND = 255
    TN_ARE_YOU_THERE = 246
    TN_WILL = 251
    TN_WONT = 252
    TN_DO = 253
    TN_DONT = 254
    TN_SUBNEGOTIATION_START = 250
    TN_SUBNEGOTIATION_END = 240

    listen_socket = None  # socket used to listen for new clients
    clients = {}          # holds info on clients. Maps client id to Client object
    nextid = 0            # counter for assigning each client a new id
    events = []           # list of occurences waiting to be handled by the code
    new_events = []       # list of newly-added occurences
    
    
    def __init__(self):
        """    
        Constructs the MudServer object and starts listening for new players.
        """
        
        self.clients = {}
        self.nextid = 0
        self.events = []
        self.new_events = []
        
        # create a new tcp socket which will be used to listen for new clients
        self.listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # set a special option on the socket which allows the port to be immediately
        # without having to wait
        self.listen_socket.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR, 1)
        
        # bind the socket to an ip address and port. Port 23 is the standard telnet port
        # which telnet clients will use. Address 0.0.0.0 means that we will bind to all
        # of the available network interfaces
        self.listen_socket.bind(("0.0.0.0",23))
        
        # set to non-blocking mode. This means that when we call 'accept', it will 
        # return immediately without waiting for a connection
        self.listen_socket.setblocking(False)
        
        # start listening for connections on the socket
        self.listen_socket.listen(1)


    def update(self):
        """    
        Checks for new players, disconnected players, and new messages sent from players.
        This method must be called before up-to-date info can be obtained from the 
        'get_new_players', 'get_disconnected_players' and 'get_commands' methods. 
        It should be called in a loop to keep the game running.
        """
                
        # check for new stuff
        self._check_for_new_connections()
        self._check_for_disconnected()
        self._check_for_messages()
        
        # move the new events into the main events list so that they can be obtained
        # with 'get_new_players', 'get_disconnected_players' and 'get_commands'. The
        # previous events are discarded
        self.events = list(self.new_events)
        self.new_events = []

        
    def get_new_players(self):
        """    
        Returns a list containing info on any new players that have entered the game 
        since the last call to 'update'. Each item in the list is a 2-tuple containing 
        the new player id number and their chosen name.
        """
        retval = []
        # go through all the events in the main list
        for ev in self.events:
            # if the event is a new player occurence, add the info to the list
            if ev[0] == self.EVENT_NEW_PLAYER: retval.append((ev[1],ev[2]))
        # return the info list
        return retval

        
    def get_disconnected_players(self):
        """    
        Returns a list containing info on any players that have left the game since 
        the last call to 'update'. Each item in the list is a player id number.
        """
        retval = []
        # go through all the events in the main list
        for ev in self.events:
            # if the event is a player disconnect occurence, add the info to the list
            if ev[0] == self.EVENT_PLAYER_LEFT: retval.append(ev[1])
        # return the info list
        return retval

    
    def get_commands(self):
        """    
        Returns a list containing any commands sent from players since the last call
        to 'update'. Each item in the list is a 3-tuple containing the id number of
        the sending player, a string containing the command (i.e. the first word of 
        what they typed), and another string containing the text after the command
        """
        retval = []
        # go through all the events in the main list
        for ev in self.events:
            # if the event is a command occurence, add the info to the list
            if ev[0] == self.EVENT_COMMAND: retval.append((ev[1],ev[2],ev[3]))
        # return the info list
        return retval


    def send_message(self,to,message):
        """    
        Sends the text in the 'message' parameter to the player with the id number 
        given in the 'to' parameter. The text will be printed out in the player's
        terminal.
        """
        # we make sure to put a newline on the end so the client receives the
        # message on its own line
        self._attempt_send(to,message+"\n")

        
    def shutdown(self):
        """    
        Closes down the server, disconnecting all clients and closing the 
        listen socket.
        """
        # for each client
        for cl in self.clients.values():
            # close the socket, disconnecting the client
            cl.socket.shutdown()
            cl.socket.close()
        # stop listening for new clients
        self.listen_socket.close()

    
    def _attempt_send(self,clid,data):
        try:
            # look up the client in the client map and use 'sendall' to send
            # the message string on the socket. 'sendall' ensures that all of 
            # the data is sent
            self.clients[clid].socket.sendall(bytes(data,"latin1"))
        # KeyError will be raised if there is no client with the given id in 
        # the map
        except KeyError: pass
        # If there is a connection problem with the client (e.g. they have
        # disconnected) a socket error will be raised
        except socket.error:
            self._handle_disconnect(clid)

    
    def _check_for_new_connections(self):
    
        # 'select' is used to check whether there is data waiting to be read
        # from the socket. We pass in 3 lists of sockets, the first being those 
        # to check for readability. It returns 3 lists, the first being 
        # the sockets that are readable. The last parameter is how long to wait - 
        # we pass in 0 so that it returns immediately without waiting
        rlist,wlist,xlist = select.select([self.listen_socket],[],[],0)
        
        # if the socket wasn't in the readable list, there's no data available,
        # meaning no clients waiting to connect, and so we can exit the method here
        if self.listen_socket not in rlist: return
        
        # 'accept' returns a new socket and address info which can be used to 
        # communicate with the new client
        joined_socket,addr = self.listen_socket.accept()
        
        # set non-blocking mode on the new socket. This means that 'send' and 
        # 'recv' will return immediately without waiting
        joined_socket.setblocking(False)
        
        # construct a new Client object to hold info about the newly connected
        # client. Use 'nextid' as the new client's id number
        self.clients[self.nextid] = MudServer.Client(joined_socket,addr[0],"",time.time())
        
        # send new client the prompt for their name
        self._attempt_send(self.nextid,"What is your name?\n")
        
        # add 1 to 'nextid' so that the next client to connect will get a unique 
        # id number
        self.nextid += 1        


    def _check_for_disconnected(self):
    
        # go through all the clients 
        for id,cl in list(self.clients.items()):
        
            # if we last checked the client less than 5 seconds ago, skip this 
            # client and move on to the next one
            if time.time() - cl.lastcheck < 5.0: continue
            
            # send the client the special "are you there" telnet command. It doesn't
            # actually matter what we send, we're really just checking that data can
            # still be written to the socket. If it can't, an error will be raised
            # and we'll know that the client has disconnected.
            self._attempt_send(id,""+chr(self.TN_INTERPRET_AS_COMMAND)+chr(self.TN_ARE_YOU_THERE))
            
            # update the last check time
            cl.lastcheck = time.time()
        
                
    def _check_for_messages(self):
    
        # go through all the clients
        for id,cl in list(self.clients.items()):
        
            # we use 'select' to test whether there is data waiting to be read from 
            # the client socket. The function takes 3 lists of sockets, the first being
            # those to test for readability. It returns 3 list of sockets, the first being
            # those that are actually readable.
            rlist,wlist,xlist = select.select([cl.socket],[],[],0)
            
            # if the client socket wasn't in the readable list, there is no new data from
            # the client - we can skip it and move on to the next one 
            if cl.socket not in rlist: continue
                        
            try:
                # read data from the socket, using a max length of 4096
                data = str(cl.socket.recv(4096),"latin1")
                
                # process the data, stripping out any special Telnet commands
                message = self._process_sent_data(cl,data)
                
                # if there was a message in the data
                if message:
                
                    # remove any spaces, tabs etc from the start and end of the message
                    message = message.strip()
                    
                    # if we haven't received the client's name yet (it's their first 
                    # message)
                    if not cl.named:
                        
                        # add a 'new player' occurence to the new events list, with the new
                        # player's id number and name
                        self.new_events.append((self.EVENT_NEW_PLAYER,id,message))
                        
                        # set the 'named' flag
                        cl.named = True
                        
                    else:
                        
                        # separate the message into the command (the first word) and
                        # its parameters (the rest of the message)
                        command,params = (message.split(" ",1)+["",""])[:2]
                        
                        # add a command occurence to the new events list with the 
                        # player's id number, the command and its parameters
                        self.new_events.append((self.EVENT_COMMAND,id,command.lower(),params))
                        
            # if there is a problem reading from the socket (e.g. the client has 
            # disconnected) a socket error will be raised
            except socket.error:
                self._handle_disconnect(id)
        
                
    def _handle_disconnect(self,clid):
        
        # remove the client from the clients map
        del(self.clients[clid])
        
        # add a 'player left' occurence to the new events list, with the player's 
        # id number
        self.new_events.append((self.EVENT_PLAYER_LEFT,clid))
        
                
    def _process_sent_data(self,client,data):
    
        # the Telnet protocol allows special command codes to be inserted into 
        # messages. For our very simple server we don't need to response to any
        # of these codes, but we must at least detect and skip over them so that 
        # we don't interpret them as text data.
        # More info on the Telnet protocol can be found here: 
        # http://pcmicro.com/netfoss/telnet.html
    
        # start with no message and in the normal state
        message = None
        state = self.READ_STATE_NORMAL
        
        # go through the data a character at a time
        for c in data:
        
            # handle the character differently depending on the state we're in:
        
            # normal state
            if state == self.READ_STATE_NORMAL:
            
                # if we received the special 'interpret as command' code, switch
                # to 'command' state so that we handle the next character as a 
                # command code and not as regular text data
                if ord(c) == self.TN_INTERPRET_AS_COMMAND:
                    state = self.READ_STATE_COMMAND
                    
                # if we get a newline character, this is the end of the message.
                # Set 'message' to the contents of the buffer and clear the buffer
                elif c == "\n":
                    message = client.buffer
                    client.buffer = ""
                    
                # otherwise it's just a regular character - add it to the buffer
                # where we're building up the received message
                else:
                    client.buffer += c
                    
            # command state
            elif state == self.READ_STATE_COMMAND:
            
                # the special 'start of subnegotiation' command code indicates that
                # the following characters are a list of options until we're told
                # otherwise. We switch into 'subnegotiation' state to handle this
                if ord(c) == self.TN_SUBNEGOTIATION_START:
                    state = self.READ_STATE_SUBNEG
                    
                # if the command code is one of the 'will', 'wont', 'do' or 'dont'
                # commands, the following character will be an option code so we 
                # must remain in the 'command' state
                elif ord(c) in (self.TN_WILL,self.TN_WONT,self.TN_DO,self.TN_DONT):
                    state = self.READ_STATE_COMMAND
                    
                # for all other command codes, there is no accompanying data so 
                # we can return to 'normal' state.
                else:
                    state = self.READ_STATE_NORMAL
                    
            # subnegotiation state
            elif state == self.READ_STATE_SUBNEG:
                
                # if we reach an 'end of subnegotiation' command, this ends the
                # list of options and we can return to 'normal' state. Otherwise
                # we must remain in this state
                if ord(c) == self.TN_SUBNEGOTIATION_END:
                    state = self.READ_STATE_NORMAL
                    
        # return the contents of 'message' which is either a string or None
        return message
        
        