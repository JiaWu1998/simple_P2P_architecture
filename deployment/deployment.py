import os
import shutil
from subprocess import Popen, PIPE
import time
import matplotlib.pyplot as plt
import sys

# Test File Load Sizes
TEST_LOAD_SIZES = [128,512,2000,8000,32000]

# Get parent directory
PARENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Create server directory
def create_server():
    if not os.path.exists(f"{PARENT_DIR}/../server"):
        os.mkdir(f"{PARENT_DIR}/../server")
    if not os.path.exists(f"{PARENT_DIR}/../server/watch_folder"):
        os.mkdir(f"{PARENT_DIR}/../server/watch_folder")
    
    shutil.copyfile(f"{PARENT_DIR}/config.json", f"{PARENT_DIR}/../server/config.json")
    shutil.copyfile(f"{PARENT_DIR}/server.py", f"{PARENT_DIR}/../server/server.py")

# Create N client directories
def create_clients(N):
    for i in range(N):
        if not os.path.exists(f"{PARENT_DIR}/../client_{i}"):
            os.mkdir(f"{PARENT_DIR}/../client_{i}")
        if not os.path.exists(f"{PARENT_DIR}/../client_{i}/download_folder"):
            os.mkdir(f"{PARENT_DIR}/../client_{i}/download_folder")

        shutil.copyfile(f"{PARENT_DIR}/config.json", f"{PARENT_DIR}/../client_{i}/config.json")
        shutil.copyfile(f"{PARENT_DIR}/client.py", f"{PARENT_DIR}/../client_{i}/client.py")

# Delete server directory
def delete_server():
    shutil.rmtree(f"{PARENT_DIR}/../server")

# Delete N client directories
def delete_clients(N):
    for i in range(N):
        shutil.rmtree(f"{PARENT_DIR}/../client_{i}")

# Create test loads for client_idx
def create_test_loads(idx):
    for size in TEST_LOAD_SIZES:
        f = open(f"{PARENT_DIR}/../client_{idx}/download_folder/load_{size}","w")
        for i in range(size):
            if i % 10000 == 0:
                f.write('\n')
            else:
                f.write("b")
        f.close()

# Evaluation 1:
def evaluation_1():
    N = 3

    create_server()
    create_clients(N)
    create_test_loads(0)

    # start server and client and check
    server_process = Popen(['python','server.py'], stdout=PIPE, stdin=PIPE, stderr=PIPE, cwd=f"{PARENT_DIR}/../server")    

    client_process_1 = Popen(['python','client.py','Mr.0',f"download 1 load_{TEST_LOAD_SIZES[-1]}", "quit"], stdout=PIPE, stdin=PIPE, stderr=PIPE, cwd=f"{PARENT_DIR}/../client_0")
    client_process_2 = Popen(['python','client.py','Mr.1',f"download 2 load_{TEST_LOAD_SIZES[-1]}", "quit"], stdout=PIPE, stdin=PIPE, stderr=PIPE, cwd=f"{PARENT_DIR}/../client_1")
    client_process_3 = Popen(['python','client.py','Mr.2',f"download 0 load_{TEST_LOAD_SIZES[-1]}", "quit"], stdout=PIPE, stdin=PIPE, stderr=PIPE, cwd=f"{PARENT_DIR}/../client_2")

    client_process_1.wait()
    client_process_2.wait()
    client_process_3.wait()
    server_process.kill()

    delete_clients(N)
    delete_server()
    pass

# Evaluation 2:
def evaluation_2():
    pass

# Evaluation 3:
def evaluation_3():
    pass

if __name__ == "__main__":
    if sys.argv[1] == "-1":
        evaluation_1()
    elif sys.argv[1] == "-2":
        evaluation_2()
    elif sys.argv[1] == "-3":
        evaluation_3()
    elif sys.argv[1] == "-c" and len(sys.argv) == 3:
        try: 
            N = int(sys.argv[2])
            create_server()
            create_clients(N)
        except Exception as e:
            print(e)
    elif sys.argv[1] == "-d" and len(sys.argv) == 3:
        try:
            N = int(sys.argv[2])
            delete_server()
            delete_clients(N)
        except Exception as e:
            print(e)

    pass
