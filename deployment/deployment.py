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

# Create test loads in server
def create_test_loads():
    for size in TEST_LOAD_SIZES:
        f = open(f"{PARENT_DIR}/../server/watch_folder/load_{size}","w")
        for i in range(size):
            if i % 10000 == 0:
                f.write('\n')
            else:
                f.write("b")
        f.close()

# Evaluation 1: One client is able to connect to server and is able to transfer one file properly
def evaluation_1():
    
    N = 1

    # Set up server and clients
    create_server()
    create_clients(N)
    create_test_loads()

    # start server and client and check
    server_process = Popen(['python','server.py'], stdout=PIPE, stdin=PIPE, stderr=PIPE, cwd=f"{PARENT_DIR}/../server")    
    client_process = Popen(['python','client.py','Mr.0',f"download load_{TEST_LOAD_SIZES[-1]}", "quit"], stdout=PIPE, stdin=PIPE, stderr=PIPE, cwd=f"{PARENT_DIR}/../client_0")
    
    # get download confirmation from client before checking
    time.sleep(10)
    client_process.wait()

    if os.path.exists(f"{PARENT_DIR}/../client_0/download_folder/load_{TEST_LOAD_SIZES[-1]}"):
        print("Evaluation 1 passed.")
    else:
        print("Evaluation 1 failed.")

    # clean up 
    delete_server()
    delete_clients(N)
    open(f"{PARENT_DIR}/../results/results.txt", 'w').close()

# Evaluation 2: Four clients are able to connect to server and are able to simultaneously transfer one file properly
def evaluation_2():

    N = 4

    # Set up server and clients
    create_server()
    create_clients(N)
    create_test_loads()

    # start server and client and check
    server_process = Popen(['python','server.py'], stdout=PIPE, stdin=PIPE, stderr=PIPE, cwd=f"{PARENT_DIR}/../server")    
    
    client_processes = [None for _ in range(N)]
    for i in range(N):
        client_processes[i] = Popen(['python','client.py','Mr.{i}',f"download load_{TEST_LOAD_SIZES[-1]}", "quit"], stdout=PIPE, stdin=PIPE, stderr=PIPE, cwd=f"{PARENT_DIR}/../client_{i}")

    # get download confirmation from client before checking
    time.sleep(15)
    for i in range(N):
        client_processes[i].wait()

    checks = 0
    for i in range(N):
        if os.path.exists(f"{PARENT_DIR}/../client_{i}/download_folder/load_{TEST_LOAD_SIZES[-1]}"):
            checks += 1

    print(f"checks for eval 2 {checks}")
    if checks == N:
        print("Evaluation 2 passed.")
    else:
        print("Evaluation 2 failed.")

    # clean up 
    delete_server()
    delete_clients(N)
    open(f"{PARENT_DIR}/../results/results.txt", 'w').close()

# Evaluation 3: Graph parallelized download speeds of all testload files for 2, 4, 8, 16 clients in parallel
def evaluation_3():
    # Test N clients at a time
    N_list = [2,4,8,16]

    # Average Time results
    avg_results = [0 for _ in range(len(N_list))]

    # repeats to get average time
    repeat = 1

    # Set up server
    create_server()
    create_test_loads()
    server_process = Popen(['python','server.py'], stdout=PIPE, stdin=PIPE, stderr=PIPE, cwd=f"{PARENT_DIR}/../server")    
    
    for n in range(len(N_list)):
        create_clients(N_list[n])
        client_processes = [None for _ in range(N_list[n])]

        for _ in range(repeat):

            for i in range(N_list[n]):
                temp_string = " ".join(["load_"+str(t) for t in TEST_LOAD_SIZES])
                client_processes[i] = Popen(['python','client.py','Mr.{i}',f"download -p {temp_string}", "quit"], stdout=PIPE, stdin=PIPE, stderr=PIPE, cwd=f"{PARENT_DIR}/../client_{i}")

            # wait for downloads to finish
            time.sleep(10)
            for i in range(N_list[n]):
                client_processes[i].wait()
            
        
        f = open(f"{PARENT_DIR}/../results/results.txt",'r')
        linecount = 0
        for i, l in enumerate(f):
            avg_results[n] += float(l)
        linecount = i + 1

        avg_results[n] /= float(linecount)
        f.close()
        open(f"{PARENT_DIR}/../results/results.txt", 'w').close()

        delete_clients(N_list[n])

    # f = open(f"{PARENT_DIR}/../results/graph.txt",'w')
    # f.write(str(avg_results))
    # f.close()
    
    delete_server()
    plt.plot(N_list,avg_results)
    plt.title('Parallerized Download Performance through Scaling Numbers of Clients')
    plt.xlabel('Number of Clients Connected To Server')
    plt.ylabel('Parallerized Download Time (ms)')
    plt.savefig(f"{PARENT_DIR}/../results/eval3.png")

    print("Evaluation 3 passed. Check /results/eval3.png for graph")

# Evaluation 4: Graph download speeds of each individual testload files for 4 clients in parallel
def evaluation_4():
    N = 4

    # Average Time results
    avg_results = [0 for _ in range(len(TEST_LOAD_SIZES))]

    # repeats to get average time
    repeat = 1

    # Set up server and clients
    create_server()
    create_test_loads()

    # start server and client and check
    server_process = Popen(['python','server.py'], stdout=PIPE, stdin=PIPE, stderr=PIPE, cwd=f"{PARENT_DIR}/../server")    
    
    for n in range(len(TEST_LOAD_SIZES)):
        create_clients(N)

        client_processes = [None for _ in range(N)]

        for _ in range(repeat):
            for i in range(N):
                client_processes[i] = Popen(['python','client.py','Mr.{i}',f"download load_{TEST_LOAD_SIZES[n]}", "quit"], stdout=PIPE, stdin=PIPE, stderr=PIPE, cwd=f"{PARENT_DIR}/../client_{i}")
            
            # wait for downloads to finish
            time.sleep(10)
            for i in range(N):
                client_processes[i].wait()

        f = open(f"{PARENT_DIR}/../results/results.txt",'r')
        linecount = 0
        for i, l in enumerate(f):
            avg_results[n] += float(l)
        linecount = i + 1

        avg_results[n] /= float(linecount)
        f.close()
        open(f"{PARENT_DIR}/../results/results.txt", 'w').close()

        delete_clients(N)

    delete_server()
    plt.plot(TEST_LOAD_SIZES,avg_results)
    plt.title('Download Performance through Scaling File Size')
    plt.xlabel('Size of Files (btyes)')
    plt.ylabel('Download Time (ms)')
    plt.savefig(f"{PARENT_DIR}/../results/eval4.png")

    print("Evaluation 4 passed. Check /results/eval4.png for graph")


if __name__ == "__main__":
    if sys.argv[1] == "-1":
        evaluation_1()
    elif sys.argv[1] == "-2":
        evaluation_2()
    elif sys.argv[1] == "-3":
        evaluation_3()
    elif sys.argv[1] == "-4":
        evaluation_4()
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
