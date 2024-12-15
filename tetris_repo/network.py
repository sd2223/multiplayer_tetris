import socket
import json
import select 
import threading
import time

class UDPNetwork:
    def __init__(self, host, port):
        # Initialize UDP socket with given host and port
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((host, port))
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.sock.settimeout(0.2) 
        self.last_sync_frame_ack = 0

    def send_message(self, message, target_address):
        # Send a JSON-encoded message to the target address
        self.sock.sendto(json.dumps(message).encode(), target_address)

    def receive_message(self):
        # Receive and decode a JSON message, handling timeouts and blocking errors  
        try:
            data, addr = self.sock.recvfrom(1024)
            return json.loads(data.decode()), addr
        except socket.timeout:
            return None, None  # Indicate timeout with None values
        except BlockingIOError:
            return None, None  
    
    def send_sync_frame(self, sync_data, target_address):
        # Start a new thread to send a sync frame and wait for acknowledgment
        thread = threading.Thread(target=self._send_sync_frame_thread, args=(sync_data, target_address))
        thread.start()
        return True

    def _send_sync_frame_thread(self, sync_data, target_address):
        # Send sync frame and wait for acknowledgment, with timeout
        start_time = time.time()
        while True:
            self.sock.sendto(json.dumps(sync_data).encode(), target_address)
            try:
                ack_data, _ = self.receive_message()
                if ack_data and ack_data["type"] == "sync_frame_ack" and ack_data["frame_number"] == sync_data["frame_number"]:
                    self.last_sync_frame_ack = ack_data["frame_number"]
                    break
            except:
                pass
            
            if time.time() - start_time > 5:  # Give up after 5 seconds
                print("Failed to receive acknowledgment for sync frame")
                break
            
            time.sleep(0.2)  # Wait 200ms before retrying

    def close(self):
        # Close the UDP socket
        self.sock.close()