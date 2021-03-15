import socket
import select
import errno
import os
import time
from threading import Thread
import json
import hashlib
import sys
import hashlib
import datetime
from pathlib import Path
from _thread import *

# get configurations 
config = json.load(open(f"{os.path.dirname(os.path.abspath(__file__))}/config.json"))

CLIENT_ID = int(os.path.basename(Path(os.path.realpath(__file__)).parent).split('_')[1])
IP = config['client']['ip_address']
PORT = config['server']['ports'][CLIENT_ID]
HEADER_LENGTH = config['header_length']
META_LENGTH = config['meta_length']
THREAD_PORTS = config['client']['ports']
LOG = open(f"{os.path.dirname(os.path.abspath(__file__))}/{config['client']['log_file']}", "a")
DOWNLOAD_FOLDER_NAME = config['client']['download_folder_name']
REDOWNLOAD_TIME = config['redownload_times']

# Logs messages
def log_this(msg):
    # print(msg)
    LOG.write(f"{datetime.datetime.now()} {msg}\n")
    LOG.flush()

# Verbose function
def help():
    print("\n*** INFO ON FUNCTIONS ***\n")
    print("[function_name] [options] [parameters] - [description]\n")
    print("get_files_list - gets the file names from all the clients\n")
    print("download -p <file_name> ... <file_name> - downloads one or more files serially or parallely. To download serially, use it without the -p option\n")
    print("help - prints verbose for functions\n")
    print("quit - exits client interface\n")

# send updated directory to server
def update_server():
    try:
        list_of_dir = os.listdir(f"{os.path.dirname(os.path.abspath(__file__))}/{DOWNLOAD_FOLDER_NAME}/")
        list_of_dir = '\n'.join(list_of_dir)
        list_of_dir = f"update_list {list_of_dir}".encode('utf-8')
        list_of_dir_header = f"{len(list_of_dir):<{HEADER_LENGTH}}".encode('utf-8')
        meta = f"{f'{CLIENT_ID}':<{META_LENGTH}}".encode('utf-8')
        central_socket.send(list_of_dir_header + meta + list_of_dir)

    except:
        # client closed connection, violently or by user
        return False

# daemon that updates the directory to the server whenever a new file is added or an file is deleted
def folder_watch_daemon(current_file_directory):
    while True:
        temp = os.listdir(f"{os.path.dirname(os.path.abspath(__file__))}/{DOWNLOAD_FOLDER_NAME}/")
        if current_file_directory != temp:
            update_server()
            current_file_directory = temp

# Waiting for a list of directories from the server
def wait_for_list(full_command):
    # Encode command to bytes, prepare header and convert to bytes, like for username above, then send
    full_command = full_command.encode('utf-8')
    command_header = f"{len(full_command):<{HEADER_LENGTH}}".encode('utf-8')
    meta = f"{'':<{META_LENGTH}}".encode('utf-8')
    central_socket.send(command_header + meta + full_command)

    log_this(f"Client sent command: {full_command}")

    # Keep trying to recieve until client recieved returns from the server
    while True:
        try:
            # Receive our "header" containing username length, it's size is defined and constant
            header = central_socket.recv(HEADER_LENGTH)

            # If we received no data, server gracefully closed a connection, for example using socket.close() or socket.shutdown(socket.SHUT_RDWR)
            if not len(header):
                log_this(f"Connection closed by the server")
                return

            # Convert header to int value
            header = int(header.decode('utf-8').strip())

            # Get meta data
            meta = central_socket.recv(META_LENGTH)
            meta = meta.decode('utf-8').strip()

            # Receive and decode msg
            dir_list = central_socket.recv(header).decode('utf-8')
            dir_list = json.loads(dir_list)

            # Print List
            for client in dir_list:
                print(f"Client {client}:")
                for file in dir_list[client]:
                    print(f"\t{file}")

            # Break out of the loop when list is recieved                
            break

        except IOError as e:

            if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:
                log_this('Reading error: {}'.format(str(e)))
                return

            # We just did not receive anything
            continue

        except Exception as e:
            # Any other exception - something happened, exit
            log_this('Reading error: '.format(str(e)))
            return

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
        return {'header': command_header, 'meta': meta, 'data': client_socket.recv(command_length)}

    except:
        # client closed connection, violently or by user
        return False

# waiting function for parallelized/serial file download
def parallelize_wait_for_file_download(client_socket, files):

    # Encode command to bytes, prepare header and convert to bytes, like for username above, then send
    full_command = f"download {' '.join(files)}".encode('utf-8')
    command_header = f"{len(full_command):<{HEADER_LENGTH}}".encode('utf-8')
    meta = f"{'':<{META_LENGTH}}".encode('utf-8')
    client_socket.send(command_header + meta + full_command)

    log_this(f"Client sent command: {full_command}")

    # open files
    fds = [open(f"{os.path.dirname(os.path.abspath(__file__))}/{DOWNLOAD_FOLDER_NAME}/{files[i]}",'w') for i in range(len(files))]
    files_closed = 0
    redownload_count = 0

    # md5 reconstruction
    m = [hashlib.md5() for _ in range(len(files))]

    # Keep trying to recieve until client recieved returns from the server
    while True:
        try:

            header = client_socket.recv(HEADER_LENGTH)  

            # If we received no data, server gracefully closed a connection, for example using socket.close() or socket.shutdown(socket.SHUT_RDWR)
            if not len(header):
                log_this('Connection closed by the server')
                return
            
            # Convert header to int value
            header = int(header.decode('utf-8').strip())

            # Get meta data
            meta = client_socket.recv(META_LENGTH)
            meta = meta.decode('utf-8').strip()
            meta = meta.split(' ')

            # Recieve line and convert to string
            line = client_socket.recv(header).decode('utf-8') 

            # if there is any error, remove all files
            if meta[0] == 'ERROR':
                log_this(line)
                
                for i in range(len(files)):
                    fds[i].flush()
                    fds[i].close()
                    os.remove(f"{os.path.dirname(os.path.abspath(__file__))}/{DOWNLOAD_FOLDER_NAME}/{files[i]}")
                break
            
            # Flush and close and files is finished recieving
            elif meta[0] == 'END':
                fds[int(meta[1])].flush()
                fds[int(meta[1])].close()
                files_closed += 1

                # if there is contamination in the checksum, log and delete file
                if m[int(meta[1])].hexdigest() != line:
                    log_this(f"Incorrect checksum for file : {files[int(meta[1])]}")
                    log_this(f"Deleting file : {files[int(meta[1])]}")
                    os.remove(f"{os.path.dirname(os.path.abspath(__file__))}/{DOWNLOAD_FOLDER_NAME}/{files[int(meta[1])]}")
 
            # continue to write and flush to files
            else:
                m[int(meta[0])].update(line.encode('utf-8'))
                fds[int(meta[0])].write(line)
                fds[int(meta[0])].flush()
            
            # when all files are closed/downloaded sucessfully then we can break from the loop
            if files_closed == len(fds):
                break

        except IOError as e:

            if e.errno != errno.EAGAIN and e.errno != errno.EWOULDBLOCK:

                if redownload_count < REDOWNLOAD_TIME:
                    redownload_count += 1
                    continue
                
                log_this('Reading error: {}'.format(str(e)))
                return 

            # We just did not receive anything
            continue

        except Exception as e:
            # Any other exception - something happened, exit
            log_this('Reading error: {}'.format(str(e)))
            return

# Waiting for the file contents from the server
def wait_for_file_download(full_command):
    parallelize = False

    parameters = full_command.split(' ')[1:]
    target_client = int(parameters[0])
    files = parameters[1:]

    # check for parallelism option
    if parameters[0] == '-p':
        if len(parameters) <= 2:
            log_this("ParameterError: Too less parameters")
            return
        else:
            parallelize = True
            target_client = int(parameters[1])
            files = files[2:]

    # if the target client is itself, don't do anything
    if target_client == CLIENT_ID:
        return

    start = time.time()

    # Compute ports that 'this' peer will try to connect
    client_thread_ports = [i+((len(config['client']['ports'])+1)*target_client) for i in THREAD_PORTS]

    # initialize connections with the other peer
    client_sockets = []

    for i in range(len(client_thread_ports)):
        temp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        temp.connect((IP, client_thread_ports[i]))
        temp.setblocking(False)

        # Initialize conneciton with the server
        temp.send(username_header + meta + username)
        client_sockets.append(temp)

    # starts waiting for file download
    if parallelize:       
        for i in range(0, len(files), len(client_thread_ports)):
            thread_idx = 0
            threads = []
            for j in range(i,i+ len(client_thread_ports)):
                if j < len(files):
                    t = Thread(target=parallelize_wait_for_file_download, args=(client_sockets[thread_idx], [files[j]],))
                    t.start()
                    threads.append(t)
                    thread_idx += 1
            
            for t in threads:
                t.join()

    else:
        parallelize_wait_for_file_download(client_sockets[0], files)

    end = time.time()
    print(f"Time: {end - start}")

    # For data collection
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    results_file = open(f"{parent_dir}/../results/results.txt", 'a')
    # results_file.write(f"{parent_dir},{(end-start)*1000} ms\n")
    results_file.write(f"{(end-start)*1000}\n")

# Sends file to the peer
def send_files(peer_socket, peers, files):
    try:
        fds = [open(f"{os.path.dirname(os.path.abspath(__file__))}/{DOWNLOAD_FOLDER_NAME}/{files[i]}",'r') for i in range(len(files))]
        
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
                    peer_socket.send(line_header + meta + line)

                    log_this(f"{files[i]} was sent to {peers[peer_socket]['data']}")
                    break
                
                line = line.encode('utf-8')

                # update md5 checksum
                m.update(line)

                line_header = f"{len(line):<{HEADER_LENGTH}}".encode('utf-8')
                meta = f"{f'{i}':<{META_LENGTH}}".encode('utf-8')
                peer_socket.send(line_header + meta + line)

            fds[i].close()

    except Exception as e:
        # client closed connection, violently or by user
        error = str(e).encode('utf-8')
        header = f"{len(error):<{HEADER_LENGTH}}".encode('utf-8')
        meta = f"{'ERROR':<{META_LENGTH}}".encode('utf-8')
        peer_socket.send(header + meta + error)
        return False

# A daemon that listens for download requests from any other clients/peers 
def server_daemon():
    
    # Create list of listening server sockets 
    server_sockets = []

    # Compute ports that 'this' peer will listen to as a server
    server_thread_ports = [i+((len(config['client']['ports'])+1)*CLIENT_ID) for i in THREAD_PORTS]

    for i in range(len(server_thread_ports)):
        temp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        temp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        temp.bind((IP, server_thread_ports[i]))
        temp.listen()
        server_sockets.append(temp)
    
    # Create list of sockets for select.select()
    sockets_list = [i for i in server_sockets]

    # List of connected clients - socket as a key, user header and name as data
    peers = {}

    for port in server_thread_ports:
        log_this(f'Listening for connections on {IP}:{port}...')
    
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
                peers[client_socket] = user

                #logging
                log_msg = 'Accepted new connection from {}:{}, username: {}\n'.format(*client_address, user['data'].decode('utf-8'))
                log_this(log_msg)

            # Else existing socket is sending a command
            else:

                # Recieve command
                command = receive_command(notified_socket)

                # If False, client disconnected, cleanup
                if command is False:
                    log_msg = '{} Closed connection from: {}\n'.format(datetime.datetime.now(), peers[notified_socket]['data'].decode('utf-8'))
                    log_this(log_msg)

                    # remove connections
                    sockets_list.remove(notified_socket)
                    del peers[notified_socket]
                    continue
                
                # Get user by notified socket, so we will know who sent the command
                user = peers[notified_socket]

                # Get command
                command_msg = command["data"].decode("utf-8")
                command_msg = command_msg.split(' ')

                # logging
                log_msg = f'{datetime.datetime.now()} Recieved command from {user["data"].decode("utf-8")}: {command_msg[0]}\n'
                log_this(log_msg)

                # Handle commands
                if command_msg[0] == 'download':
                    start_new_thread(send_files, (notified_socket,peers,command_msg[1:],))
            
            # handle some socket exceptions just in case
            for notified_socket in exception_sockets:
                
                # remove connections
                sockets_list.remove(notified_socket)
                del peers[notified_socket]
                
if __name__ == "__main__":

    # Start the peer's server daemon
    start_new_thread(server_daemon,())

    # Manual Mode of Client Interface
    if len(sys.argv) == 1:
        
        # create username to connect to the server
        my_username = input("Username: ")
        username = my_username.encode('utf-8')
        username_header = f"{len(username):<{HEADER_LENGTH}}".encode('utf-8')
        meta = f"{'':<{META_LENGTH}}".encode('utf-8')

        # Initialize connection with the server with central socket
        central_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        central_socket.connect((IP, PORT))
        central_socket.setblocking(False)
        central_socket.send(username_header + meta + username)

        # Initialize file directory to server
        update_server()

        # get current file directories
        current_file_directory = os.listdir(f"{os.path.dirname(os.path.abspath(__file__))}/{DOWNLOAD_FOLDER_NAME}/")

        # Start folder watch daemon to automatically update to server
        start_new_thread(folder_watch_daemon,(current_file_directory,))
        
        # Print verbose client shell begins
        help()

        # Does Client Things
        while True:

            # Wait for user to input a command
            full_command = input(f'{my_username} > ').strip()
            command = full_command.split(' ')[0]
            parameters = full_command.split(' ')[1:]

            if command == "download":
                if len(parameters) != 0:
                    wait_for_file_download(full_command)
                else:
                    
                    log_this("ParameterError: Too less parameters")

            elif command == "get_files_list":
                if len(parameters) == 0:
                    wait_for_list(full_command)
                else:
                    log_this("ParameterError: Too many parameters")

            elif command == "help":
                help()
            
            elif command == "quit":
                sys.exit()
    
    # Automatic Mode of Client Interface
    
    #Args
    #python client.py username command1 command2 ... commandn

    else:

        # create username to connect to the server
        my_username = sys.argv[0]
        username = my_username.encode('utf-8')
        username_header = f"{len(username):<{HEADER_LENGTH}}".encode('utf-8')
        meta = f"{'':<{META_LENGTH}}".encode('utf-8')

        # Initialize connection with the server with central socket
        central_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        central_socket.connect((IP, PORT))
        central_socket.setblocking(False)
        central_socket.send(username_header + meta + username)

        # Initialize file directory to server
        update_server()

        # get current file directories
        current_file_directory = os.listdir(f"{os.path.dirname(os.path.abspath(__file__))}/{DOWNLOAD_FOLDER_NAME}/")

        # Start folder watch daemon to automatically update to server
        start_new_thread(folder_watch_daemon,(current_file_directory,))

        # Does Client Things
        for i in sys.argv[1:]:

            # Wait for user to input a command
            full_command = i
            command = full_command.split(' ')[0]
            parameters = full_command.split(' ')[1:]

            if command == "download":
                if len(parameters) != 0:
                    wait_for_file_download(full_command)
                else:
                    log_this("ParameterError: Too less parameters")

            elif command == "get_files_list":
                if len(parameters) == 0:
                    wait_for_list(full_command)
                else:
                    log_this("ParameterError: Too many parameters")

            elif command == "help":
                help()
            
            elif command == "quit":
                sys.exit()