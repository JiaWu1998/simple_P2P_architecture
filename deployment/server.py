import socket
import select
import os
import datetime
from _thread import *
import json
import hashlib


# get configurations
config = json.load(open(f"{os.path.dirname(os.path.abspath(__file__))}/config.json"))

IP = config['server']['ip_address']
PORT = config['server']['port']
HEADER_LENGTH = config['header_length']
META_LENGTH = config['meta_length']
NUM_THREAD_SOCKETS = config['thread_sockets']['num_thread_sockets']
THREAD_PORTS = [PORT] + config['thread_sockets']['ports']
LOG = open(f"{os.path.dirname(os.path.abspath(__file__))}/{config['server']['log_file']}", "a")
WATCH_FOLDER_NAME = config['server']['watch_folder_name']

# Logs messages
def log_this(msg):
    print(msg)
    LOG.write(f"{datetime.datetime.now()} {msg}")
    LOG.flush()

# Handles command receiving
def receive_command(client_socket):

    try:

        # Receive our "header" containing command length, it's size is defined and constant
        command_header = client_socket.recv(HEADER_LENGTH)

        # If we received no data, client gracefully closed a connection, for example using socket.close() or socket.shutdown(socket.SHUT_RDWR)
        if not len(command_header):
            return False

        # Get meta data
        meta = client_socket.recv(META_LENGTH)
        meta = meta.decode('utf-8').strip()

        # Convert header to int value
        command_length = int(command_header.decode('utf-8').strip())

        # Return an object of command header and command data
        return {'header': command_header, 'data': client_socket.recv(command_length)}

    except:
        # client closed connection, violently or by user
        return False

# Sends file directory to client
def send_file_directory(client_socket):
    try:
        list_of_dir = os.listdir(f"{os.path.dirname(os.path.abspath(__file__))}/{WATCH_FOLDER_NAME}/")
        list_of_dir = '\n'.join(list_of_dir).encode('utf-8')
        list_of_dir_header = f"{len(list_of_dir):<{HEADER_LENGTH}}".encode('utf-8')
        meta = f"{'':<{META_LENGTH}}".encode('utf-8')
        client_socket.send(list_of_dir_header + meta + list_of_dir)

    except:
        # client closed connection, violently or by user
        return False

# Sends file to the client
def send_files(client_socket, files):
    try:
        fds = [open(f"{os.path.dirname(os.path.abspath(__file__))}/{WATCH_FOLDER_NAME}/{files[i]}",'r') for i in range(len(files))]
        
        for i in range(len(files)):
            # using md5 checksum
            m = hashlib.md5()
            
            while True:

                # read line
                line = fds[i].readline()

                if not line:
                    line = m.hexdigest().encode('utf-8')
                    line_header = f"{len(line):<{HEADER_LENGTH}}".encode('utf-8')
                    meta = f"{f'END {i}':<{META_LENGTH}}".encode('utf-8')
                    client_socket.send(line_header + meta + line)

                    log_this(f"{files[i]} was sent to {clients[client_socket]['data']}")
                    break
                
                line = line.encode('utf-8')

                # update md5 checksum
                m.update(line)

                line_header = f"{len(line):<{HEADER_LENGTH}}".encode('utf-8')
                meta = f"{f'{i}':<{META_LENGTH}}".encode('utf-8')
                client_socket.send(line_header + meta + line)

            fds[i].close()

    except Exception as e:
        # client closed connection, violently or by user
        error = str(e).encode('utf-8')
        header = f"{len(error):<{HEADER_LENGTH}}".encode('utf-8')
        meta = f"{'ERROR':<{META_LENGTH}}".encode('utf-8')
        client_socket.send(header + meta + error)
        return False

if __name__ == "__main__":
    # Create list of server sockets
    server_sockets = []

    for i in range(len(THREAD_PORTS)):
        temp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        temp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        temp.bind((IP, THREAD_PORTS[i]))
        temp.listen()
        server_sockets.append(temp)

    # Create list of sockets for select.select()
    sockets_list = [i for i in server_sockets]

    # List of connected clients - socket as a key, user header and name as data
    clients = {}

    log_this(f'Listening for connections on {IP}:{PORT}...')

    # Does Server Things
    while True:
        read_sockets, _, exception_sockets = select.select(sockets_list, [], sockets_list)

        for notified_socket in read_sockets:

            # If notified socket is a server socket - new connection, accept it
            if notified_socket in server_sockets:

                client_socket, client_address = server_sockets[server_sockets.index(notified_socket)].accept()

                # Client should send his name right away, receive it
                user = receive_command(client_socket)

                # If False - client disconnected before he sent his name
                if user is False:
                    continue

                # Add accepted socket to select.select() list
                sockets_list.append(client_socket)

                # Also save username and username header
                clients[client_socket] = user

                # logging 
                log_msg = 'Accepted new connection from {}:{}, username: {}\n'.format(*client_address, user['data'].decode('utf-8'))
                log_this(log_msg)
            
            # Else existing socket is sending a command
            else:

                # Receive command
                command = receive_command(notified_socket)

                # If False, client disconnected, cleanup
                if command is False:
                    log_msg = '{} Closed connection from: {}\n'.format(datetime.datetime.now(), clients[notified_socket]['data'].decode('utf-8'))                 
                    log_this(log_msg)
                    
                    # remove connections
                    sockets_list.remove(notified_socket)
                    del clients[notified_socket]
                    continue

                # Get user by notified socket, so we will know who sent the command
                user = clients[notified_socket]

                # Get command
                command_msg = command["data"].decode("utf-8")
                command_msg = command_msg.split(' ')

                # logging
                log_msg = f'{datetime.datetime.now()} Received command from {user["data"].decode("utf-8")}: {command_msg[0]}\n'
                log_this(log_msg)

                # Handle commands
                if command_msg[0] == 'get_files_list':
                    start_new_thread(send_file_directory, (notified_socket,))

                elif command_msg[0] == 'download':
                    start_new_thread(send_files, (notified_socket,command_msg[1:],))

        # handle some socket exceptions just in case
        for notified_socket in exception_sockets:

            # remove connections
            sockets_list.remove(notified_socket)
            del clients[notified_socket]