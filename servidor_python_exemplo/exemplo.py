#import socket module 
from socket import * 
import threading

# Create a thread to handle each client connection, what used to be done via
# while loop will now be done via threads, so that the server can handle multiple clients at the same time
def handle_client(connectionSocket, addr):
    print("Starting client handling:", addr)

    # debugging threading
    threadName = threading.current_thread().name
    print(f"[{threadName}] Handling {addr}")

    try:
        messageBytes = connectionSocket.recv(1024)

        if not messageBytes:
            print("Connection closed by client:", addr)
            return

        message = messageBytes.decode("utf-8")
        print('Received message:', message)

        method = message.split()[0]
        filename = message.split()[1]
        version = message.split()[2]

        print('Method:', method)
        print('Filename:', filename[1:])
        print('Version:', version)

        # now, let's try to open the file and send the response
        try:
            f = open(filename[1:]) 
            outputdata = f.read()
            f.close()

            responseHeader = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: text/html; charset=utf-8\r\n"
                "Connection: close\r\n"
                "\r\n"
            )
            responseHeader = responseHeader.encode("utf-8")
            body = outputdata.encode("utf-8")
            response = responseHeader + body
            connectionSocket.sendall(response)

        except FileNotFoundError:
            responseHeader = (
                "HTTP/1.1 404 Not Found\r\n"
                "Content-Type: text/html; charset=utf-8\r\n"
                "Connection: close\r\n"
                "\r\n"
            )
            errorBody = "<h1>404 Not Found</h1>"
            responseHeader = responseHeader.encode("utf-8")
            body = errorBody.encode("utf-8")
            response = responseHeader + body
            connectionSocket.sendall(response)

    except (OSError, IOError, UnicodeDecodeError) as e:
        print("Error processing request from", addr, ":", e)

    finally:
        connectionSocket.close()
        print("Connection closed with:", addr)

 # af_ifnet deals with ipv4 adresses
 # sock_stream creates a tcp socket
serverSocket = socket(AF_INET, SOCK_STREAM) # socket that will deal with connections
#Prepare a server socket
# defining server port
serverPort = 8080 
# reuse adress
serverSocket.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
# then we bind the server socket to the port
# '' means all network interfaces, so the server will be accessible from any network interface on the machine
serverSocket.bind(('', serverPort))

# the server socket will listen to 5 connections, for now
serverSocket.listen(5)
print('Server listening on port: ', serverPort)

try:
    # now, the while loop should only accept connections and create a new thread for each connection, so that the server can handle multiple clients at the same time
    while True: 
        #Establish the connection 
        print('Ready to serve...') 
        # this will block the program until a connection is established
        # connectionSocket is the socket that will be used to communicate with the client
        # addr is the address of the client
        connectionSocket, addr = serverSocket.accept() # accept the connection
        # create a new thread for each connection
        clientThread = threading.Thread(target=handle_client, args=(connectionSocket, addr))
        clientThread.start()

except KeyboardInterrupt:
    print("\nServer shutting down...")
finally:
    serverSocket.close()
    print("Server stopped.")
