import argparse
import socket
import ssl
import json
import threading
import logging
import zmq

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class GameClient:
    def __init__(self, server_host='127.0.0.1', server_port=65432, zmq_pub_port=5557, cafile=None):
        # Initialize client with SSL context and ZeroMQ subscriber socket
        self.listen_thread = None
        self.receive_thread = None
        self.server_host = server_host
        self.server_port = server_port
        self.zmq_pub_port = zmq_pub_port
        self.cafile = cafile
        self.context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=self.cafile)
        self.context.check_hostname = False
        self.context.verify_mode = ssl.CERT_REQUIRED
        self.client_socket = None
        self.zmq_context = zmq.Context()
        self.mode = None
        self.mode_selected = False
        self.stop_event = threading.Event()

    def start(self):
        # Start the SSL client and connect to the server
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                self.client_socket = self.context.wrap_socket(sock, server_hostname=self.server_host)
                self.client_socket.connect((self.server_host, self.server_port))
                logging.info("SSL connection established with server.")
                self.receive_thread = threading.Thread(target=self.receive_messages)
                self.receive_thread.start()
                self.send_messages()
        except ssl.SSLError as e:
            logging.error(f"SSL error: {e}")
        except Exception as e:
            logging.error(f"Connection error: {e}")

    def listen_for_broadcasts(self):
        # Listen for broadcast messages from the server
        sub_socket = self.zmq_context.socket(zmq.SUB)
        sub_socket.connect(f"tcp://localhost:{self.zmq_pub_port}")
        sub_socket.setsockopt_string(zmq.SUBSCRIBE, '')
        while not self.stop_event.is_set():
            try:
                message = sub_socket.recv_string(flags=zmq.NOBLOCK)
                logging.info(f"Broadcast message received: {message}")
            except zmq.Again:
                pass

    def receive_messages(self):
        # Receive messages from the server and print them to the console
        while not self.stop_event.is_set():
            try:
                response = self.client_socket.recv(1024).decode('utf-8')
                if not response:
                    break
                response_json = json.loads(response)
                print("Server:", response_json['message'])

                if "Choose game mode" in response_json['message']:
                    self.mode_selected = False
                elif "Multi player game started" in response_json['message']:
                    self.mode_selected = True
                    self.mode = '2'
                    self.listen_thread = threading.Thread(target=self.listen_for_broadcasts)
                    self.listen_thread.start()
                elif "Exiting" in response_json['message']:
                    self.mode_selected = False
                else:
                    self.mode_selected = True

            except Exception as e:
                logging.error(f"Error receiving message: {e}")
                break

    def send_messages(self):
        # Send user input messages to the server
        while True:
            try:
                message = input()
                if message.lower() == 'exit':
                    if not self.mode_selected:
                        message_json = json.dumps({"mode": "exit"})
                        self.client_socket.sendall(message_json.encode('utf-8'))
                        break  # Exit the loop and close the connection
                    else:
                        message_json = json.dumps({"exit": "exit"})
                        self.client_socket.sendall(message_json.encode('utf-8'))
                        self.mode_selected = False  # Reset the mode selection to allow main menu interaction
                        continue  # Continue the loop to return to main menu
                elif not self.mode_selected:
                    message_json = json.dumps({"mode": message})
                else:
                    message_json = json.dumps({"guess": message})

                self.client_socket.sendall(message_json.encode('utf-8'))

            except Exception as e:
                logging.error(f"Error sending message: {e}")
                break
        self.shutdown_connection()  # Ensure the connection is properly closed

    def shutdown_connection(self):
        # Shutdown the client connection and cleanup
        self.stop_event.set()
        self.receive_thread.join()
        try:
            self.client_socket.shutdown(socket.SHUT_RDWR)
        except Exception as e:
            logging.error(f"Error shutting down socket: {e}")
        finally:
            self.client_socket.close()
            logging.info("Connection closed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Connect to the number guessing game server.')
    parser.add_argument('-a', metavar='cafile', default=None)
    args = parser.parse_args()
    client = GameClient('127.0.0.1', 65432, 5557, args.a)
    try:
        client.start()
    except Exception as e:
        logging.error(f"Client error: {e}")
