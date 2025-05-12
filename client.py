import argparse
import socket
import ssl
import json
import pickle
import zlib
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Function to show history of previous games
def load_and_display_history(filename='client_history.pkl'):
    try:
        with open(filename, 'rb') as f:
            data = zlib.decompress(f.read())
            history = pickle.loads(data)
            logging.info("Loaded game history:")
            for session in history:
                for item in session:
                    print(item)
    except FileNotFoundError:
        logging.info("No previous game history found.")
    except (zlib.error, EOFError, pickle.UnpicklingError) as e:
        logging.error(f"Error while loading or decompressing game history: {e}")


# Function to compress and save game history using pickle and zlib.
def compress_and_save_history(history, filename='client_history.pkl'):
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

        # Write the new data to the client pickle file
        with open(filename, 'wb') as f:
            compressed_data = zlib.compress(pickle.dumps(existing_history))
            f.write(compressed_data)
        logging.info("Game history saved successfully.")
    except Exception as e:
        logging.error(f"Failed to save history: {e}")


# Function for playing game in client
def guess_the_number_client(server_host='127.0.0.1', server_port=65432, cafile=None):
    # Load and display the history of all the msgs exchanged during previous games.
    load_and_display_history()

    # Create default context of client
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=cafile)
    context.check_hostname = False
    # Certificate required
    context.verify_mode = ssl.CERT_REQUIRED

    # Create socket as IPv4, TCP
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.settimeout(10)
            # Wrap socket in SSL context to create client socket
            with context.wrap_socket(sock, server_hostname=server_host) as client_socket:
                # Connect client to server
                client_socket.connect((server_host, server_port))
                logging.info("SSL connection established. The game has started.")
                game_history = []

                # Send 'start' message serialized with json
                start_message = json.dumps({"message": "start."})
                client_socket.sendall(start_message.encode('utf-8'))
                game_history.append("Client: start.")

                # While connected, send guesses to server
                while True:
                    response = client_socket.recv(1024).decode('utf-8')
                    if not response:
                        raise ConnectionError("Unexpected disconnection from server.")

                    # Append game history and print server's message
                    game_history.append(f"Server: {response}")
                    response_json = json.loads(response)
                    print("Server:", response_json['message'])

                    # End session if game ends
                    if "Congratulations" in response_json['message'] or "Sorry" in response_json['message']:
                        break

                    # Input guess and append to game history
                    guess = input("Your guess: ")
                    guess_json = json.dumps({"guess": guess})
                    client_socket.sendall(guess_json.encode('utf-8'))
                    game_history.append(f"Client: {guess}")

                # Game ended -> Compress (pickle and zlib)
                compress_and_save_history([game_history])
                logging.info("Game session ended and history saved.")
        # Various error handling
        except socket.gaierror:
            logging.error("GAI error.")
        except ssl.SSLCertVerificationError as e:
            logging.error(f"SSL Certificate Verification Failed: {e}")
        except socket.timeout:
            logging.error("Connection timed out.")
        except ConnectionError as e:
            logging.error(f"Unexpected disconnection. Closing game. {e}")
        except ssl.SSLError as e:
            logging.error(f"SSL error occurred: {e}")
        except socket.error as e:
            logging.error(f"Socket error occurred: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Connect to the number guessing game server.')
    # Using -a option to specify CA certificate file to trust that cert file
    parser.add_argument('-a', metavar='cafile', default=None)
    args = parser.parse_args()
    guess_the_number_client('127.0.0.1', 65432, args.a)
