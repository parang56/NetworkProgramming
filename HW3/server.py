import socket
import ssl
import random
import json
import threading
import logging
import zmq

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def determine_response(guess, number):
    if guess == number:
        return "Congratulations, you did it!"
    elif guess < number:
        return "Hint: You guessed too small! Guess again: "
    else:
        return "Hint: You guessed too high! Guess again: "


class GameServer:
    def __init__(self, host='127.0.0.1', port=65432, zmq_pub_port=5557):
        # Initialize server with SSL context and ZeroMQ publisher socket
        self.host = host
        self.port = port
        self.context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        self.context.load_cert_chain(certfile='cert.crt', keyfile='key.pem')
        self.server_socket = None
        self.clients = []
        self.multi_player_clients = []  # List to track multiplayer clients
        self.multi_player_attempts = {}  # Dictionary to track attempts for each client
        self.multi_player_number = None
        self.multi_player_lock = threading.Lock()
        self.multi_player_active = False
        self.zmq_context = zmq.Context()
        self.pub_socket = self.zmq_context.socket(zmq.PUB)
        self.pub_socket.bind(f"tcp://*:{zmq_pub_port}")

    def start(self):
        # Start the SSL server and listen for incoming connections
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.host, self.port))
            sock.listen()
            self.server_socket = self.context.wrap_socket(sock, server_side=True)
            logging.info(f"SSL server listening on {self.host}:{self.port}")
            while True:
                try:
                    connection, address = self.server_socket.accept()
                    logging.info(f"Connected by {address}")
                    client_thread = threading.Thread(target=self.handle_client, args=(connection,))
                    client_thread.start()
                except ssl.SSLError as e:
                    logging.error(f"SSL error: {e}")
                except Exception as e:
                    logging.error(f"Error accepting connection: {e}")

    def handle_client(self, connection):
        with connection:
            try:
                while True:
                    mode_message = json.dumps({
                        "message": "Choose game mode: '1' for single player, '2' for multi player, 'exit' to terminate:"
                    })
                    connection.sendall(mode_message.encode('utf-8'))
                    mode_data = connection.recv(1024).decode('utf-8').strip()
                    if not mode_data:
                        raise ConnectionError("Client disconnected unexpectedly.")

                    mode_json = json.loads(mode_data)
                    mode = mode_json.get('mode')

                    # Go to single play, multi play, or exit based on client input
                    if mode == '1':
                        self.single_player_game(connection)
                    elif mode == '2':
                        self.multi_player_game(connection)
                    elif mode and mode.lower() == 'exit':
                        logging.info("Client chose to exit. Closing connection between the client.")
                        break
            except ConnectionError as e:
                logging.info(f"Unexpected Error: {e}")
            except Exception as e:
                logging.error(f"Error handling client: {e}")

    def single_player_game(self, connection):
        # Start a single player game session with the client
        logging.info("Single player game session started.")
        number = random.randint(1, 10)
        attempts = 0
        max_attempts = 5
        # Tell client the rules of the game.
        msg = json.dumps({"message": f"You have a total of {max_attempts} attempts. "
                                     "Enter 'exit' to prematurely leave the game. "
                                     "Guess a number between 1 to 10:"})
        connection.sendall(msg.encode('utf-8'))

        # If all attempts are exhausted, or if client enters exit, or if client guesses correct number,
        # tell the message accordingly to the client and exit the game to reprompt the client to choose a gamemode.
        while attempts < max_attempts:
            try:
                data = connection.recv(1024).decode('utf-8').strip()
                if not data:
                    raise ConnectionError("Client disconnected unexpectedly.")
                data_json = json.loads(data)
                if 'guess' in data_json:
                    guess = int(data_json['guess'])
                    # Incorrect number guess
                    if guess > 10 or guess <= 0:
                        response = "Choose a number between 1 to 10! Guess again: "
                    else:
                        response = determine_response(guess, number)
                        attempts += 1
                        # If used all attempts and response wasn't the correct guess response send "Sorry..."
                        if attempts >= max_attempts and not response.startswith("Congratulations"):
                            response = "Sorry, you've used all of your attempts!"
                    msg = json.dumps({"message": response})
                    connection.sendall(msg.encode('utf-8'))
                    # If response had "Congratulations" or "Sorry" indicating game is over, break from guessing
                    if response.startswith("Congratulations") or "Sorry" in response:
                        break
                # If client entered "exit" leave game.
                elif 'exit' in data_json:
                    logging.info("Client chose to exit the single player game.")
                    break
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                logging.error(f"JSON decode error or invalid guess: {e}")
                msg = json.dumps({"message": "Invalid input! Choose a number between 1 to 10 or type 'exit' to quit."})
                connection.sendall(msg.encode('utf-8'))
            except ConnectionError as e:
                logging.info(f"Unexpected error: {e}")
                break
            except Exception as e:
                logging.error(f"Unexpected error: {e}")
                break
        logging.info("Single player game session ended.")

    def multi_player_game(self, connection):
        logging.info("Multi player game session started.")
        max_attempts = 5
        with self.multi_player_lock:
            if not self.multi_player_active:
                self.multi_player_number = random.randint(1, 10)
                self.multi_player_active = True
            self.multi_player_clients.append(connection)  # Add to multiplayer clients
            self.multi_player_attempts[connection] = max_attempts  # Set max attempts for each client

        msg = json.dumps({"message": f"Multi player game started! Each player has {max_attempts} attempts. "
                                     "Enter 'exit' to prematurely leave the game. Guess a number between 1 to 10:"})
        connection.sendall(msg.encode('utf-8'))

        while True:
            try:
                data = connection.recv(1024).decode('utf-8').strip()
                if not data:
                    raise ConnectionError("Client disconnected unexpectedly.")
                data_json = json.loads(data)
                if data_json.get('guess'):
                    try:
                        guess = int(data_json.get('guess'))
                        with self.multi_player_lock:
                            # Check if all clients have exhausted their attempts
                            if all(attempts <= 0 for attempts in self.multi_player_attempts.values()):
                                for client in self.multi_player_clients:
                                    msg = json.dumps({
                                        "message": "Everyone has used all of their attempts without guessing the "
                                                   "correct number! Enter 'exit' to prematurely leave the game. \n"
                                                   "Starting a new game with a new number. All clients have"
                                                   f" {max_attempts} new attempts!\nGuess a number between 1 to 10: "})
                                    try:
                                        client.sendall(msg.encode('utf-8'))
                                    except Exception as e:
                                        logging.error(f"Error sending message to client: {e}")
                                self.multi_player_number = random.randint(1, 10)  # Reset number
                                self.multi_player_attempts = {c: max_attempts for c in
                                                              self.multi_player_clients}  # Reset attempts
                                continue

                            # If all clients had not used all their attempts and the particular client has used all of its attempts
                            if self.multi_player_attempts[connection] <= 0:
                                response = "Sorry, you've used all of your attempts!"
                                individual_msg = json.dumps({"message": response})
                                connection.sendall(individual_msg.encode('utf-8'))
                                continue  # Skip the rest of the loop to avoid processing the guess

                            if guess > 10 or guess <= 0:
                                response = "Choose a number between 1 to 10! Guess again: "
                            else:
                                self.multi_player_attempts[connection] -= 1
                                response = determine_response(guess, self.multi_player_number)
                                if response.startswith("Congratulations"):
                                    self.multi_player_number = random.randint(1, 10)  # Reset number
                                    for client in self.multi_player_clients:
                                        # Send "you did it" message to the client who guessed the correct message
                                        if client == connection:
                                            msg = json.dumps({"message": "Congratulations, you did it! Starting a new game "
                                                                         "with a new number.\nEnter 'exit' to prematurely leave the game.\n"
                                                                         "All clients have "
                                                                         f"{max_attempts} new attempts! Guess a number "
                                                                         "between 1 to 10:"})
                                        # If not the client who guessed the correct message, send
                                        # "someone guessed the correct ... " message
                                        else:
                                            msg = json.dumps({"message": "Congratulations, someone guessed the correct "
                                                                         "number! Starting a new game with a new number."
                                                                         "\nEnter 'exit' to prematurely leave the game.\n"
                                                                         f"All clients have {max_attempts} new attempts!"
                                                                         " Guess a number between 1 to 10: "})
                                        try:
                                            client.sendall(msg.encode('utf-8'))
                                        except Exception as e:
                                            logging.error(f"Error sending message to client: {e}")
                                    self.multi_player_attempts = {c: max_attempts for c in
                                                                  self.multi_player_clients}  # Reset attempts
                                    continue
                                # Check if all clients have exhausted their attempts
                                if all(attempts <= 0 for attempts in self.multi_player_attempts.values()):
                                    for client in self.multi_player_clients:
                                        msg = json.dumps({
                                            "message": "Everyone has used all of their attempts without guessing the "
                                                       "correct number!\nEnter 'exit' to prematurely leave the game.\n"
                                                       "Starting a new game with a new number. All clients have"
                                                       f" {max_attempts} new attempts!\nGuess a number between 1 to 10: "})
                                        try:
                                            client.sendall(msg.encode('utf-8'))
                                        except Exception as e:
                                            logging.error(f"Error sending message to client: {e}")
                                    self.multi_player_number = random.randint(1, 10)  # Reset number
                                    self.multi_player_attempts = {c: max_attempts for c in
                                                                  self.multi_player_clients}  # Reset attempts
                                    continue
                            # If all clients haven't exhausted all their attempts and the guess wasn't correct,
                            # send message "Sorry, you've ..."
                            if self.multi_player_attempts[connection] <= 0:
                                response = "Sorry, you've used all of your attempts!"
                                individual_msg = json.dumps({"message": response})
                                connection.sendall(individual_msg.encode('utf-8'))
                            else:
                                individual_msg = json.dumps({"message": response})
                                connection.sendall(individual_msg.encode('utf-8'))
                    except (ValueError, KeyError):
                        response = "Choose a number between 1 to 10! Guess again: "
                        individual_msg = json.dumps({"message": response})
                        connection.sendall(individual_msg.encode('utf-8'))
                # If client enters "exit", multiplayer exits multiplayer session and
                # server takes the client out of the clients that are in multiplayer session
                elif data_json.get('exit'):
                    logging.info("Client chose to exit multiplayer session.")
                    with self.multi_player_lock:
                        self.multi_player_clients.remove(connection)
                        del self.multi_player_attempts[connection]
                        if not self.multi_player_clients:
                            self.multi_player_active = False
                    break
            # If error from client, take that client out of the clients in multiplayer session
            except ConnectionError as e:
                logging.info(f"Unexpected Error: {e}")
                with self.multi_player_lock:
                    if connection in self.multi_player_clients:
                        self.multi_player_clients.remove(connection)
                        del self.multi_player_attempts[connection]
                        if not self.multi_player_clients:
                            self.multi_player_active = False
                break
            except Exception as e:
                logging.error(f"Unexpected error: {e}")
                break

        logging.info("Multi player game session ended.")


if __name__ == "__main__":
    try:
        server = GameServer()
        server.start()
    except Exception as e:
        logging.error(f"Server error: {e}")
