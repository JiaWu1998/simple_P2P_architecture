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

# get configurations 
config = json.load(open(f"{os.path.dirname(os.path.abspath(__file__))}/config.json"))

IP = config['client']['ip_address']
PORT = config['client']['server_port']
HEADER_LENGTH = config['header_length']
META_LENGTH = config['meta_length']
NUM_THREAD_SOCKETS = config['thread_sockets']['num_thread_sockets']
THREAD_PORTS = [PORT] + config['thread_sockets']['ports']
LOG = open(f"{os.path.dirname(os.path.abspath(__file__))}/{config['client']['log_file']}", "a")
DOWNLOAD_FOLDER_NAME = config['client']['download_folder_name']
REDOWNLOAD_TIME = config['redownload_times']

# Logs messages
def log_this(msg):
    print(msg)
    LOG.write(f"{datetime.datetime.now()} {msg}")
    LOG.flush()

# Waiting for a list of directories from the server
def wait_for_list(full_command):
    # Encode command to bytes, prepare header and convert to bytes, like for username above, then send
    full_command = full_command.encode('utf-8')
    command_header = f"{len(full_command):<{HEADER_LENGTH}}".encode('utf-8')
    meta = f"{'':<{META_LENGTH}}".encode('utf-8')
    client_sockets[0].send(command_header + meta + full_command)

    log_this(f"Client sent command: {full_command}")

    # Keep trying to recieve until client recieved returns from the server
    while True:
        try:
            # Receive our "header" containing username length, it's size is defined and constant
            header = client_sockets[0].recv(HEADER_LENGTH)

            # If we received no data, server gracefully closed a connection, for example using socket.close() or socket.shutdown(socket.SHUT_RDWR)
            if not len(header):
                log_this(f"Connection closed by the server")
                return

            # Convert header to int value
            header = int(header.decode('utf-8').strip())

            # Get meta data
            meta = client_sockets[0].recv(META_LENGTH)
            meta = meta.decode('utf-8').strip()

            # Receive and decode msg
            dir_list = client_sockets[0].recv(header).decode('utf-8')
            dir_list = dir_list.split('\n')

            # Print List
            for d in dir_list:
                print(d)

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
def wait_for_file_download(full_command, files):
    parallelize = False

    if parameters[0] == '-p':
        if len(parameters) == 1:
            log_this("ParameterError: Too less parameters")
            return
        else:
            parallelize = True
            files = files[1:]

    start = time.time()

    if parallelize:       
        for i in range(0, len(files), NUM_THREAD_SOCKETS):
            thread_idx = 0
            threads = []
            for j in range(i,i+NUM_THREAD_SOCKETS):
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



# Verbose function
def help():
    print("\n*** INFO ON FUNCTIONS ***\n")
    print("[function_name] [options] [parameters] - [description]\n")
    print("get_files_list - gets the file names from the watch directory of the server\n")
    print("download -p <file_name> ... <file_name> - downloads one or more files serially or parallely. To download serially, use it without the -p option\n")
    print("help - prints verbose for functions\n")
    print("quit - exits client interface\n")

if __name__ == "__main__":
    
    if len(sys.argv) == 0:
        # Create list of sockets connection
        client_sockets = []

        # create username to connect to the server
        my_username = input("Username: ")
        username = my_username.encode('utf-8')
        username_header = f"{len(username):<{HEADER_LENGTH}}".encode('utf-8')
        meta = f"{'':<{META_LENGTH}}".encode('utf-8')

        for i in range(len(THREAD_PORTS)):
            temp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            temp.connect((IP, THREAD_PORTS[i]))
            temp.setblocking(False)

            # Initialize conneciton with the server
            temp.send(username_header + meta + username)
            client_sockets.append(temp)
        
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
                    wait_for_file_download(full_command, parameters)
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
    else:
        #Args
        #python client.py username command1 command2 ... commandn

        # Create list of sockets connection
        client_sockets = []

        # create username to connect to the server
        my_username = sys.argv[0]
        username = my_username.encode('utf-8')
        username_header = f"{len(username):<{HEADER_LENGTH}}".encode('utf-8')
        meta = f"{'':<{META_LENGTH}}".encode('utf-8')

        for i in range(len(THREAD_PORTS)):
            temp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            temp.connect((IP, THREAD_PORTS[i]))
            temp.setblocking(False)

            # Initialize conneciton with the server
            temp.send(username_header + meta + username)
            client_sockets.append(temp)

        # Does Client Things
        for i in sys.argv[1:]:

            # Wait for user to input a command
            full_command = i
            command = full_command.split(' ')[0]
            parameters = full_command.split(' ')[1:]

            if command == "download":
                if len(parameters) != 0:
                    wait_for_file_download(full_command, parameters)
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
