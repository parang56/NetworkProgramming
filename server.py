import socket
import ssl
import random
import json
import pickle
import zlib
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Function to show history of previous games
def load_and_display_history(filename='game_history.pkl'):
    try:
        with open(filename, 'rb') as f:
            data = zlib.decompress(f.read())
            history = pickle.loads(data)
            logging.info("Loaded game history successfully.")
            for session in history:
                for item in session:
                    print(item)
    except FileNotFoundError:
        logging.info("No previous game history found.")
    except (zlib.error, EOFError, pickle.UnpicklingError) as e:
        logging.error(f"Error while loading or decompressing game history: {e}")


# Function to return response according to relations between guess and answer
def determine_response(guess, number):
    if guess == number:
        return "Congratulations, you did it!"
    elif guess < number:
        return "Hint: You guessed too small! Guess again: "
    else:
        return "Hint: You guessed too high! Guess again: "


# Function to compress and save game history using pickle and zlib.
def compress_and_save_history(history, filename='game_history.pkl'):
    try:
        existing_history = []
        try:
            with open(filename, 'rb+') as f:
                data = f.read()
                if data:
                    existing_history = pickle.loads(zlib.decompress(data))
        except FileNotFoundError:
            logging.info("No existing history. Creating new history file.")
        except (EOFError, pickle.UnpicklingError) as e:
            logging.warning(f"Failed to load existing history: {e}")

        # Extend(append) new history to existing_history
        existing_history.extend(history)

        # Write the new data to the server pickle file
        with open(filename, 'wb') as f:
            compressed_data = zlib.compress(pickle.dumps(existing_history))
            f.write(compressed_data)
        logging.info("Game history saved successfully.")
    except Exception as e:
        logging.error(f"Failed to save history: {e}")


# Function for playing game in server
def guess_the_number_server(host='127.0.0.1', port=65432):
    # Load and display the history of all the msgs exchanged during previous games.
    load_and_display_history()
    try:
        # Create default context of server
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        # Use the certificate and pem file that I generated
        context.load_cert_chain(certfile='cert.crt', keyfile='key.pem')

        # Create socket as IPv4, TCP
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
            sock.listen()

            # Wrap socket in SSL context to create server socket
            with context.wrap_socket(sock, server_side=True) as server_socket:
                logging.info(f"SSL server listening on {host}:{port}")

                while True:
                    try:
                        # Client has connected to the server.
                        connection, address = server_socket.accept()
                        with connection:
                            # Log : show the address of client
                            logging.info(f"Connected by {address}")
                            game_history = []

                            # Client has sent 'start' msg.
                            data = connection.recv(1024).decode('utf-8').strip()
                            data_json = json.loads(data)
                            game_history.append(f"Client: {data_json}")

                            # Init for game
                            number = random.randint(1, 10)
                            attempts = 0
                            msg = json.dumps({"message": "Guess a number between 1 to 10:"})
                            connection.sendall(msg.encode('utf-8'))
                            game_history.append(f"Server: {msg}")

                            while True:
                                data = connection.recv(1024).decode('utf-8').strip()
                                game_history.append(f"Client: {data}")
                                if not data:
                                    raise ConnectionError("Unexpected disconnection from client.")

                                try:
                                    # Deserialize json data
                                    data_json = json.loads(data)
                                    guess = int(data_json['guess'])

                                    # Guess was correctly given between 1 ~ 10
                                    if 1 <= guess <= 10:
                                        # Get corresponding response based on relations of guess and answer
                                        response = determine_response(guess, number)
                                        attempts += 1
                                        # If maximum attempts (5) was reached
                                        if attempts >= 5:
                                            # If fifth guess was correct
                                            if response.startswith("Congratulations"):
                                                msg = json.dumps({"message": response})
                                                connection.sendall(msg.encode('utf-8'))
                                                game_history.append(f"Server: {msg}")
                                                break
                                            # Fifth guess was incorrect
                                            response = "Sorry, you've used all of your attempts!"

                                    # Guess was an OOB number
                                    else:
                                        response = "Number needs to be between 1 to 10! Guess again: "

                                    msg = json.dumps({"message": response})
                                    connection.sendall(msg.encode('utf-8'))
                                    game_history.append(f"Server: {msg}")

                                    if response.startswith("Congratulations") or "Sorry" in response:
                                        break
                                except (ValueError, KeyError):
                                    msg = json.dumps({"message": "Please enter a valid number. Guess again: "})
                                    connection.sendall(msg.encode('utf-8'))
                                    game_history.append(f"Server: {msg}")

                            # Game ended -> Compress (pickle and zlib)
                            compress_and_save_history([game_history])
                            logging.info("Game session ended and history saved.")
                            break
                    # Various error handling
                    except socket.timeout:
                        logging.error("Connection timed out. Closing connection.")
                    except ConnectionError as e:
                        logging.error(f"Unexpected disconnection. Closing game. {e}")
                    except ssl.SSLError as e:
                        logging.error(f"SSL error occurred: {e}")
                    except socket.error as e:
                        logging.error(f"Socket error occurred: {e}")
                    finally:
                        if 'connection' in locals():
                            connection.close()
                            logging.info("Connection closed.")
                        break
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    guess_the_number_server()
