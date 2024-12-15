import pygame, pigame
import random
from network import UDPNetwork
from tetris_game import TetrisGame
import os
import time
import socket
import RPi.GPIO as GPIO
import threading 
from queue import Queue

# Set up environment variables for Raspberry Pi display
os.putenv('SDL_VIDEODRV','fbcon')
os.putenv('SDL_FBDEV', '/dev/fb0')
os.putenv('SDL_MOUSEDRV','dummy')
os.putenv('SDL_MOUSEDEV','/dev/null')
os.putenv('DISPLAY','')

# Configuration constants
PLAYER2_IP = '10.49.243.13'
MATCH_TIMEOUT = 5

# GPIO setup
GPIO.setmode(GPIO.BCM)
GPIO_PINS = {
    'quit': 17,
    'rotate': 5,
    'down': 12,
    'left': 16,
    'right': 6,
    'sabotage': 4
}
for pin in GPIO_PINS.values():
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)

# Game state variables
game_started = False
countdown_started = False
connected = False
partner_address = None
matchmaking_failed = False
matchmaking_tried = False
game_over = False
running = True

# Game objects and threads
tetris_game = None
message_thread = None

# Network and messaging
network = None
message_queue = Queue()

# Attempt to establish a connection with another player.
def start_matchmaking():
    global connected, partner_address, screen, matchmaking_failed, matchmaking_tried

    matchmaking_tried = True  
    start_time = time.time()
    last_request_time = 0
    request_interval = 1  # Send a request every 1 second

    while time.time() - start_time < MATCH_TIMEOUT:
        current_time = time.time()

        # Send request periodically
        if current_time - last_request_time >= request_interval:
            network.send_message({"type": "request"}, (PLAYER2_IP, 5000))
            print("request sent")
            last_request_time = current_time

        # Check for incoming messages
        try:
            result = network.receive_message()
            if result and result[0] is not None:
                message, addr = result
                if message["type"] == "request":
                    # Respond to incoming request
                    network.send_message({"type": "request_ack"}, addr)
                elif message["type"] == "request_ack":
                    # Respond to acknowledgment
                    network.send_message({"type": "ack_ack"}, addr)
                    partner_address = addr
                    connected = True
                    message_thread.start()
                    return
                elif message["type"] == "ack_ack":
                    # Connection confirmed
                    partner_address = addr
                    connected = True
                    message_thread.start()
                    return
        except socket.error:
            pass

        # Small delay to prevent busy-waiting
        time.sleep(0.01)

    matchmaking_failed = True 
    matchmaking_tried = False

# Callback for the quit button
def quit_callback(channel):
    global running
    running = False

# Callback for the rotate button
def rotate_callback(channel):
    global game_started, countdown_started, partner_address, tetris_game
    if not connected:
        start_matchmaking()
    elif not game_started and not countdown_started:
        countdown_started = True
        network.send_message({"type": "start_game"}, partner_address)
    elif tetris_game:
        tetris_game.handle_key_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))

# Callback for the down button
def down_callback(channel):
    global tetris_game
    if tetris_game:
        tetris_game.handle_key_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))

# Callback for the left button
def left_callback(channel):
    global tetris_game
    if tetris_game:
        tetris_game.handle_key_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_LEFT))

# Callback for the right button
def right_callback(channel):
    global tetris_game
    if tetris_game:
        tetris_game.handle_key_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))

# Callback for the sabotage button
def sab_callback(channel):
    global tetris_game
    if tetris_game:
        tetris_game.handle_key_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_1))                

# Set up GPIO event detection
GPIO.add_event_detect(GPIO_PINS['quit'], GPIO.FALLING, callback=quit_callback)
GPIO.add_event_detect(GPIO_PINS['rotate'], GPIO.FALLING, callback=rotate_callback, bouncetime=100)
GPIO.add_event_detect(GPIO_PINS['down'], GPIO.FALLING, callback=down_callback, bouncetime=100)
GPIO.add_event_detect(GPIO_PINS['left'], GPIO.FALLING, callback=left_callback, bouncetime=100)
GPIO.add_event_detect(GPIO_PINS['right'], GPIO.FALLING, callback=right_callback, bouncetime=100)
GPIO.add_event_detect(GPIO_PINS['sabotage'], GPIO.FALLING, callback=sab_callback)

# Handle incoming network messages
def message_handler():
    global network, message_queue, countdown_started
    while True:
        result = network.receive_message()
        if result and result[0] is not None:
            message, addr = result
            if message["type"] == "start_game":
                countdown_started = True
            elif message["type"] == "game_state":
                message_queue.put(("game_state", message))
            elif message["type"] == "sync_frame":
                ack_message = {
                    "type": "sync_frame_ack",
                    "frame_number": message["frame_number"]
                }
                network.send_message(ack_message, addr)
                message_queue.put(("sync_frame", message))
            elif message["type"] == "sabotage":
                message_queue.put(("sabotage", message))   

# Main game loop 
def main():
    global screen, network, partner_address

    pygame.init()
    pitft = pigame.PiTft()
    screen = pygame.display.set_mode((320, 240))
    pygame.display.set_caption("Tetris - Multiplayer")

    # Initialize UDP network
    network = UDPNetwork('0.0.0.0', 5000)

    # Define fonts
    font_large = pygame.font.Font(None, 48)  # Large font for titles
    font_medium = pygame.font.Font(None, 36)  # Medium font for buttons and smaller text

    global running, game_over, game_started, matchmaking_failed, matchmaking_tried
    global countdown_started, tetris_game

    # FPS and clock setup
    FPS = 60
    clock = pygame.time.Clock()

    # Start the message handler thread
    global message_thread
    message_thread = threading.Thread(target=message_handler)
    message_thread.daemon = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        screen.fill((0, 0, 0))

        if not connected and not game_started:
            if not matchmaking_failed and not matchmaking_tried:
                # Landing page with "Find a match" button
                title_text = font_large.render("Tetris - Multiplayer", True, (255, 255, 255))
                button_text = font_medium.render("Find a match", True, (255, 255, 255))
                screen.blit(title_text, (10, 50))
                screen.blit(button_text, (10, 150))
            elif matchmaking_tried:
                # Landing page after the "Find a match" button is pressed
                font = pygame.font.Font(None, 36)
                text = font.render("Looking for a partner...", True, (255, 255, 255))
                screen.blit(text, (10, 100))
                pygame.display.flip()
            else:
                # Display "Could not find a match" and "Try again" button if no connection is established
                text = font_medium.render("Could not find a match", True, (255, 0, 0))
                retry_text = font_medium.render("Try again", True, (255, 255, 255))
                screen.blit(text, (10, 100))
                screen.blit(retry_text, (10, 150))
        elif connected and not game_started and not countdown_started:
            # Match found; display "Start Match" button
            text = font_medium.render("Start Match", True, (255, 255, 255))
            screen.blit(text, (10, 150))
        elif countdown_started and not game_started:
            # Display countdown to the start of the game 
            tetris_game = TetrisGame(screen, network, partner_address)
            game_started = True 
            font = pygame.font.Font(None, 48)
            for countdown_time in range(3, 0, -1):  # Countdown from 3 to 1
                screen.fill((0, 0, 0))  # Clear screen
                countdown_text = font.render(str(countdown_time), True, (255, 255, 255))
                text_rect = countdown_text.get_rect(center=(160, 120))
                screen.blit(countdown_text, text_rect)
                pygame.display.flip()
                pygame.time.delay(1000)  # Wait for 1 second   
        elif connected and game_started:
            # Game play loop 
            if not game_over: 
                game_over = tetris_game.update(message_queue)
            tetris_game.draw()

        pygame.display.flip()
        clock.tick(FPS)  # Ensure the loop runs at the specified FPS

    network.close()
    pygame.quit()

if __name__ == "__main__":
    main()