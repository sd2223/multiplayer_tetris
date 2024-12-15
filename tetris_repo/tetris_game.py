import pygame
import random
from network import UDPNetwork
import time
import json
from datetime import datetime
from collections import deque

class TetrisGame:
    def __init__(self, screen, network, partner_address):
        self.screen = screen
        self.network = network
        self.partner_address = partner_address
        
        # Constants
        self.PLAYER_DATA = {
            1: {
                'GRID_SIZE': 10,
                'COLUMNS': 10,
                'ROWS': 20,
                'GRID_X': 10,
                'GRID_Y': 30,
                'NEXT_BLOCK_X': 10,
                'NEXT_BLOCK_Y': 5,
                'BORDER_THICKNESS': 3,
            },
            2: {
                'GRID_SIZE': 6,
                'COLUMNS': 10,
                'ROWS': 20,
                'GRID_X': 250,
                'GRID_Y': 30,
                'NEXT_BLOCK_X': 250,
                'NEXT_BLOCK_Y': 5,
                'BORDER_THICKNESS': 2,
            }
        }
        
        # Colors
        self.BLACK = (0, 0, 0)
        self.WHITE = (255, 255, 255)
        self.GRAY = (63, 63, 63)
        self.SHAPE_COLORS = [(255, 0, 0), (255, 125, 0), (255, 200, 0), (0, 255, 0), (0, 255, 255), (0, 0, 255), (127, 0, 127)]
        self.P2_COLOR = (5, 67, 200)

        # Shapes
        self.SHAPES = [
            [[1, 1, 1, 1]],     # I
            [[1, 1], 
             [1, 1]],           # O
            [[0, 1, 0], 
             [1, 1, 1]],        # T
            [[1, 0, 0], 
             [1, 1, 1]],        # J
            [[0, 0, 1], 
             [1, 1, 1]],        # L
            [[0, 1, 1],
             [1, 1, 0]],        # S
            [[1, 1, 0],
             [0, 1, 1]]         # Z
        ]
        
        # Game variables
        self.p1_grid = self.create_grid(1)
        self.p2_grid = self.create_grid(2)
        self.p1_current_shape = random.choice(self.SHAPES)
        self.p1_current_color = random.choice(self.SHAPE_COLORS)
        self.p1_next_shape = random.choice(self.SHAPES)
        self.p1_next_color = random.choice(self.SHAPE_COLORS)
        self.p2_next_shape = random.choice(self.SHAPES)
        self.shape_pos = [self.PLAYER_DATA[1]['COLUMNS'] // 2 - len(self.p1_current_shape[0]) // 2, 0]
        self.frames_per_move = 30
        self.curr_frame = 0
        self.score = 0
        self.p2_score = 0
        self.frame_number = 0
        self.last_received_frame = -1

        self.last_sync_time = time.time()
        self.sync_interval = 10  # 10 seconds
        self.sync_frame_number = 0
        self.grid_bitmap = self.create_grid_bitmap()

        self.game_over = False 
        self.message_queue = None 

        self.sabotage_meter = 0
        self.sabotage_thresholds = [300, 600, 900]  # Adjust these values as needed
        self.max_sabotage_meter = 1000
        self.sabotage_increase_rate = 1  # Increase by 1 point per frame
        self.available_sabotages = []

        self.sabotage_timer = 0
        self.sabotage_duration = 10 * 60  # 10 seconds * 60 frames per second
        self.original_frames_per_move = self.frames_per_move
        self.control_mapping = {
            pygame.K_UP: 'rotate',
            pygame.K_DOWN: 'hard_drop',
            pygame.K_LEFT: 'move_left',
            pygame.K_RIGHT: 'move_right'
        }
        self.scramble_duration = 40 * 60  # 10 seconds * 60 frames per second
        self.scramble_timer = 0

        self.show_leaderboard = False
        self.font_large = pygame.font.Font(None, 48)
        self.font_medium = pygame.font.Font(None, 36)
        self.font_small = pygame.font.Font(None, 24)

        self.entering_initials = False
        self.initials = ["A", "A", "A"]  # Default initials
        self.initials_index = 0  # Current letter index being modified
        self.alphabet = [chr(i) for i in range(ord('A'), ord('Z') + 1)]

        self.button_queue = deque(maxlen=5)  # Limit queue size to prevent overflow

    # Create an empty grid for the specified player
    def create_grid(self, player):
        return [[self.BLACK for _ in range(self.PLAYER_DATA[player]['COLUMNS'])] 
                for _ in range(self.PLAYER_DATA[player]['ROWS'])]

    # Draw the border around the player's grid
    def draw_grid_border(self, player):
        player_data = self.PLAYER_DATA[player]
        border_thickness = player_data['BORDER_THICKNESS']
        border_rect = pygame.Rect(
            player_data['GRID_X'] - border_thickness,
            player_data['GRID_Y'],
            player_data['COLUMNS'] * player_data['GRID_SIZE'] + border_thickness * 2,
            player_data['ROWS'] * player_data['GRID_SIZE'] + border_thickness
        )
        pygame.draw.rect(self.screen, self.GRAY, border_rect, border_thickness)
    
    # Draw the game grid for the specified player
    def draw_grid(self, grid, player):
        player_data = self.PLAYER_DATA[player]
        for row in range(player_data['ROWS']):
            for col in range(player_data['COLUMNS']):
                x = player_data['GRID_X'] + col * player_data['GRID_SIZE']
                y = player_data['GRID_Y'] + row * player_data['GRID_SIZE']
                pygame.draw.rect(self.screen, grid[row][col], 
                                 (x, y, player_data['GRID_SIZE'], player_data['GRID_SIZE']))
                pygame.draw.rect(self.screen, self.GRAY, 
                                 (x, y, player_data['GRID_SIZE'], player_data['GRID_SIZE']), 1)

        # Draw grid border
        self.draw_grid_border(player)

    # Check if the current position is valid for the given shape
    def valid_position(self, grid, shape, offset, player):
        off_x, off_y = offset
        player_data = self.PLAYER_DATA[player]
        for y, row in enumerate(shape):
            for x, cell in enumerate(row):
                if cell:
                    if (x + off_x < 0 or x + off_x >= player_data['COLUMNS'] or
                        y + off_y >= player_data['ROWS'] or 
                        grid[y + off_y][x + off_x] != self.BLACK):
                        return False
        return True

    # Add the current shape to the grid and return its coordinates
    def add_shape_to_grid(self, grid, shape, offset, color):
        off_x, off_y = offset
        piece_coordinates = []
        for y, row in enumerate(shape):
            for x, cell in enumerate(row):
                if cell:
                    grid[y + off_y][x + off_x] = color
                    piece_coordinates.append((x + off_x, y + off_y))
        return piece_coordinates

    # Clear completed lines and return the new grid and number of cleared lines
    def clear_lines(self, grid, player):
        player_data = self.PLAYER_DATA[player]
        new_grid = [row for row in grid if any(cell == self.BLACK for cell in row)]
        cleared = player_data['ROWS'] - len(new_grid)
        new_grid = [[self.BLACK for _ in range(player_data['COLUMNS'])] for _ in range(cleared)] + new_grid
        return new_grid, cleared

    # Rotate the given shape 90 degrees clockwise
    def rotate_shape(self, shape):
        return [list(row) for row in zip(*shape[::-1])]

    # Draw the next block for the specified player
    def draw_next_block(self, shape, color, player):
        player_data = self.PLAYER_DATA[player]
        for y, row in enumerate(shape):
            for x, cell in enumerate(row):
                if cell:
                    pygame.draw.rect(self.screen, color,
                        (player_data['NEXT_BLOCK_X'] + x * player_data['GRID_SIZE'],
                         player_data['NEXT_BLOCK_Y'] + y * player_data['GRID_SIZE'],
                         player_data['GRID_SIZE'], player_data['GRID_SIZE']))
                    pygame.draw.rect(self.screen, self.GRAY,
                        (player_data['NEXT_BLOCK_X'] + x * player_data['GRID_SIZE'],
                         player_data['NEXT_BLOCK_Y'] + y * player_data['GRID_SIZE'],
                         player_data['GRID_SIZE'], player_data['GRID_SIZE']), 1)
        
        font = pygame.font.Font(None, 20)
        text = font.render("Next", True, self.WHITE)
        self.screen.blit(text, (player_data['NEXT_BLOCK_X'], player_data['NEXT_BLOCK_Y'] - 20))

    # Calculate the maximum fall distance for the current shape
    def calculate_max_fall_distance(self, shape, current_pos):
        max_distance = 0
        while self.valid_position(self.p1_grid, shape, (current_pos[0], current_pos[1] + max_distance + 1), 1):
            max_distance += 1
        return max_distance

    # Send the current game state to the other player
    def send_game_state(self, piece_coordinates):
        self.frame_number += 1
        game_state = {
            "type": "game_state",
            "frame_number": self.frame_number,
            "piece_coordinates": piece_coordinates,
            "next_shape": self.SHAPES.index(self.p1_next_shape)
        }
        self.network.send_message(game_state, self.partner_address)

    # Apply the specified sabotage effect
    def apply_sabotage(self, sabotage_index):
        if sabotage_index == 0:  # First sabotage
            self.p1_current_shape = random.choice(self.SHAPES)
            self.p1_current_color = random.choice(self.SHAPE_COLORS)
        elif sabotage_index == 1:  # Second sabotage
            self.original_frames_per_move = self.frames_per_move
            self.frames_per_move = max(1, self.frames_per_move - 15)
            self.sabotage_timer = self.sabotage_duration    
        elif sabotage_index == 2:  # Third sabotage
            actions = list(self.control_mapping.values())
            random.shuffle(actions)
            self.control_mapping = dict(zip(self.control_mapping.keys(), actions))
            self.scramble_timer = self.scramble_duration
    
    # Update Player 2's grid based on the received bitmap
    def update_p2_grid(self, grid_bitmap):
        for row in range(self.PLAYER_DATA[2]['ROWS']):
            for col in range(self.PLAYER_DATA[2]['COLUMNS']):
                if grid_bitmap[row] & (1 << (self.PLAYER_DATA[2]['COLUMNS'] - 1 - col)):
                    self.p2_grid[row][col] = self.P2_COLOR
                else:
                    self.p2_grid[row][col] = self.BLACK

    # Update Player 2's grid with the new piece and next shape
    def update_p2_grid_piece(self, piece_coordinates, next_shape_index):
        piece_color = self.P2_COLOR  
        for x, y in piece_coordinates:
            if 0 <= y < self.PLAYER_DATA[2]['ROWS'] and 0 <= x < self.PLAYER_DATA[2]['COLUMNS']:
                self.p2_grid[y][x] = piece_color
        
        # Clear lines if necessary
        self.p2_grid, cleared_lines = self.clear_lines(self.p2_grid, 2)
        
        # Update the next shape for Player 2
        self.p2_next_shape = self.SHAPES[next_shape_index]

    # Create an empty grid bitmap
    def create_grid_bitmap(self):
        return [0 for _ in range(self.PLAYER_DATA[1]['ROWS'])]

    # Update the grid bitmap based on the current grid state
    def update_grid_bitmap(self):
        for row in range(self.PLAYER_DATA[1]['ROWS']):
            bitmap_row = 0
            for col in range(self.PLAYER_DATA[1]['COLUMNS']):
                if self.p1_grid[row][col] != self.BLACK:
                    bitmap_row |= (1 << (self.PLAYER_DATA[1]['COLUMNS'] - 1 - col))
            self.grid_bitmap[row] = bitmap_row

    # Send a synchronization frame to the other player
    def send_sync_frame(self):
        self.sync_frame_number += 1
        sync_data = {
            "type": "sync_frame",
            "frame_number": self.sync_frame_number,
            "grid_bitmap": self.grid_bitmap,
            "score": self.score  
        }
        self.network.send_sync_frame(sync_data, self.partner_address)

    # Process received messages from the message queue
    def process_messages(self):
        while not self.message_queue.empty():
            message_type, message = self.message_queue.get()
            if message_type == "game_state":
                self.update_p2_grid_piece(message["piece_coordinates"], message["next_shape"])
            elif message_type == "sync_frame":
                self.update_p2_grid(message["grid_bitmap"]) 
                self.p2_score = message["score"]
            elif message_type == "sabotage":
                self.apply_sabotage(message["index"])    

    # Calculate the score based on the number of lines cleared
    def calculate_score(self, lines_cleared):
        base_score = 40
        if lines_cleared == 1:
            return base_score
        elif lines_cleared == 2:
            return base_score * 2 * 2
        elif lines_cleared == 3:
            return base_score * 3 * 3
        elif lines_cleared == 4:
            return base_score * 4 * 10
        return 0

    # Send a sabotage action to the other player
    def send_sabotage(self, sabotage_index):
        if sabotage_index in self.available_sabotages:
            sabotage_message = {
                "type": "sabotage",
                "index": sabotage_index
            }
            self.network.send_message(sabotage_message, self.partner_address)
            self.sabotage_meter = 0  # Reset the meter after sending a sabotage
            self.available_sabotages = []

    # Update the list of available sabotages based on the current meter value
    def update_available_sabotages(self):
        self.available_sabotages = [i for i, threshold in enumerate(self.sabotage_thresholds) if self.sabotage_meter >= threshold]

    # Reset the control mapping to default values
    def reset_control_mapping(self):
        self.control_mapping = {
            pygame.K_UP: 'rotate',
            pygame.K_DOWN: 'hard_drop',
            pygame.K_LEFT: 'move_left',
            pygame.K_RIGHT: 'move_right'
        }    

    # Perform the specified action (move, rotate, or sabotage)
    def perform_action(self, action):
        if action == 'rotate':
            if not self.game_over:
                rotated_shape = self.rotate_shape(self.p1_current_shape)
                if self.valid_position(self.p1_grid, rotated_shape, self.shape_pos, 1):
                    self.p1_current_shape = rotated_shape
            elif self.entering_initials:
                if self.initials_index < 2:
                    self.initials_index += 1
                else:  # All letters are confirmed
                    self.finalize_leaderboard_entry()
            else:
                self.show_leaderboard = True
        elif action == 'hard_drop':
            self.frames_per_move = 1
        elif action == 'move_left':
            if self.entering_initials:
                self.initials[self.initials_index] = self.alphabet[(self.alphabet.index(self.initials[self.initials_index]) - 1) % len(self.alphabet)]                
            elif self.valid_position(self.p1_grid, self.p1_current_shape, (self.shape_pos[0] - 1, self.shape_pos[1]), 1):
                self.shape_pos[0] -= 1
        elif action == 'move_right':
            if self.entering_initials:
                self.initials[self.initials_index] = self.alphabet[(self.alphabet.index(self.initials[self.initials_index]) + 1) % len(self.alphabet)]
            elif self.valid_position(self.p1_grid, self.p1_current_shape, (self.shape_pos[0] + 1, self.shape_pos[1]), 1):
                self.shape_pos[0] += 1 
        elif action == 'sabotage':
            if self.sabotage_meter > self.sabotage_thresholds[2]:
                self.send_sabotage(2)
            elif self.sabotage_meter > self.sabotage_thresholds[1]:
                self.send_sabotage(1)
            elif self.sabotage_meter > self.sabotage_thresholds[0]:
                self.send_sabotage(0)

    # Check if the current score qualifies for the leaderboard
    def check_leaderboard_entry(self):
        scores = self.load_scores()
        if self.score > min(score["score"] for score in scores):
            return True
        return False
    
    # Finalize the leaderboard entry and save it to the file
    def finalize_leaderboard_entry(self):
        self.entering_initials = False
        scores = self.load_scores()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        score_entry = {
            "date": timestamp,
            "score": self.score,
            "initials": "".join(self.initials)
        }

        scores.append(score_entry)
        scores.sort(key=lambda x: x["score"], reverse=True)
        scores = scores[:5]  # Keep only the top 5 scores

        with open("highscores.json", "w") as file:
            json.dump(scores, file, indent=2)

    # Load the high scores from the JSON file
    def load_scores(self):
        try:
            with open("highscores.json", "r") as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return []
    
    # Handle key events for game controls
    def handle_key_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in self.control_mapping:
                action = self.control_mapping[event.key]
                if self.game_over:
                    self.button_queue.append(action)
                elif not self.button_queue or self.button_queue[-1] != action:
                    self.button_queue.append(action)
            elif event.key == pygame.K_1:
                self.button_queue.append("sabotage")


    # Update the game state, process messages, and handle game logic
    def update(self, message_queue):
        if self.game_over:
            return False 

        # Check for received messages and perform corresponding actions
        self.message_queue = message_queue
        self.process_messages()

        # Handle sabotage timer
        if self.sabotage_timer > 0:
            self.sabotage_timer -= 1
            if self.sabotage_timer == 0:
                self.frames_per_move = self.original_frames_per_move

        # Handle scramble timer
        if self.scramble_timer > 0:
            self.scramble_timer -= 1
        if self.scramble_timer == 0:
            self.reset_control_mapping()        

        # Increase sabotage meter
        self.sabotage_meter = min(self.sabotage_meter + self.sabotage_increase_rate, self.max_sabotage_meter)
        self.update_available_sabotages()

        # Process button queue
        while self.button_queue:
            action = self.button_queue.popleft()
            self.perform_action(action)

        if self.curr_frame % self.frames_per_move == 0:
            max_fall_distance = self.calculate_max_fall_distance(self.p1_current_shape, self.shape_pos)    

            if max_fall_distance > 0:
                if self.frames_per_move == 1:
                    # When down key is pressed, fall to the maximum distance
                    self.shape_pos[1] += max_fall_distance
                    self.frames_per_move = self.original_frames_per_move
                else:
                    # In normal gameplay, fall by 2 units or to the maximum distance, whichever is smaller
                    self.shape_pos[1] += min(2, max_fall_distance)
            else:
                # Lock the piece in place
                piece_coordinates = self.add_shape_to_grid(self.p1_grid, self.p1_current_shape, self.shape_pos, self.p1_current_color)
                self.send_game_state(piece_coordinates)
                self.update_grid_bitmap()
                self.p1_grid, cleared = self.clear_lines(self.p1_grid, 1)
                self.score += self.calculate_score(cleared)
                self.p1_current_shape = self.p1_next_shape
                self.p1_current_color = self.p1_next_color
                self.p1_next_shape = random.choice(self.SHAPES)
                self.p1_next_color = random.choice(self.SHAPE_COLORS)
                self.shape_pos = [self.PLAYER_DATA[1]['COLUMNS'] // 2 - len(self.p1_current_shape[0]) // 2, 0]

                if not self.valid_position(self.p1_grid, self.p1_current_shape, self.shape_pos, 1):
                    print(f"Game Over! Final Score: {self.score}")
                    self.game_over = True
                    if self.check_leaderboard_entry():
                        self.entering_initials = True
                    self.send_sync_frame()
                    return True

        self.curr_frame = (self.curr_frame + 1) % 60

        # Check if it's time to send a sync frame
        current_time = time.time()
        if current_time - self.last_sync_time >= self.sync_interval:
            self.send_sync_frame()
            self.last_sync_time = current_time

        return False 

    # Draw the score for Player 2
    def draw_p2_score(self):
        font = pygame.font.Font(None, 18)
        score_text = font.render(f"Score: {self.p2_score}", True, self.BLACK)
        score_rect = score_text.get_rect()
        score_rect.topleft = (self.PLAYER_DATA[2]['GRID_X'] + 20, self.PLAYER_DATA[2]['NEXT_BLOCK_Y'])
        self.screen.blit(score_text, score_rect)

    # Draw the game over screen
    def draw_game_over(self):
        # Create a semi-transparent overlay
        overlay = pygame.Surface((320, 240))
        overlay.set_alpha(128)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        # Draw "GAME OVER" text with background
        game_over_text = self.font_large.render("GAME OVER", True, (255, 0, 0))
        text_rect = game_over_text.get_rect(center=(160, 120))
        
        # Draw background rectangle for text
        bg_rect = text_rect.inflate(20, 20)
        pygame.draw.rect(self.screen, (50, 50, 50), bg_rect)
        
        # Draw text
        self.screen.blit(game_over_text, text_rect)

    # Draw the button to check the leaderboard
    def draw_check_leaderboard_button(self):
        button_rect = pygame.Rect(180, 180, 120, 40)
        pygame.draw.rect(self.screen, (100, 100, 100), button_rect)
        
        # Draw an inner border to show the button is active
        pygame.draw.rect(self.screen, (200, 200, 200), button_rect.inflate(-4, -4), 2)

        button_text = self.font_small.render("Check Leaderboard", True, (255, 255, 255))
        text_rect = button_text.get_rect(center=button_rect.center)
        self.screen.blit(button_text, text_rect)

        # Check for rotate button being pressed to go to the next screen
        while self.button_queue:
            action = self.button_queue.popleft()
            if action == 'rotate':
                self.perform_action(action)

    # Draw the initials input screen for high scores
    def draw_initials_input(self):
        self.screen.fill(self.BLACK)

        font = pygame.font.Font(None, 36)
        prompt = font.render("Enter Your Initials:", True, self.WHITE)
        self.screen.blit(prompt, (50, 50))

        initials_text = "".join(self.initials)
        initials_rendered = font.render(initials_text, True, self.WHITE)
        self.screen.blit(initials_rendered, (50, 100))

        # Draw cursor for current letter being set
        underline_x = 50 + self.initials_index * 15
        pygame.draw.line(self.screen, self.WHITE, (underline_x, 130), (underline_x + 20, 130), 2)

        # Loop to scroll and select letters
        while self.button_queue:
            action = self.button_queue.popleft()
            if action == 'rotate':
                self.perform_action(action)
            elif action == 'move_left':
                self.perform_action(action)
            elif action == 'move_right':
                self.perform_action(action)            

    # Draw the leaderboard screen
    def draw_leaderboard(self):
        # Create a semi-transparent overlay
        overlay = pygame.Surface((320, 240))
        overlay.set_alpha(200)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        # Draw leaderboard background
        leaderboard_rect = pygame.Rect(40, 20, 240, 200)
        pygame.draw.rect(self.screen, (50, 50, 50), leaderboard_rect)

        # Draw leaderboard title
        title_text = self.font_medium.render("Leaderboard", True, (255, 255, 255))
        title_rect = title_text.get_rect(centerx=160, top=30)
        self.screen.blit(title_text, title_rect)

        # Draw high scores from the JSON file
        scores = self.load_scores()
        for i, score in enumerate(scores[:10], 1):
            score_text = self.font_small.render(f"{i}. {score['initials']} - {score['score']}", True, (255, 255, 255))
            self.screen.blit(score_text, (60, 60 + i * 30))

    # Main drawing function to render the game state
    def draw(self):
        self.screen.fill(self.WHITE)
        self.draw_grid(self.p1_grid, 1)
        self.draw_grid(self.p2_grid, 2)
        self.draw_next_block(self.p1_next_shape, self.p1_next_color, 1)
        self.draw_next_block(self.p2_next_shape, self.GRAY, 2) 
        self.draw_p2_score()
        
        for y, row in enumerate(self.p1_current_shape):
            for x, cell in enumerate(row):
                if cell:
                    pygame.draw.rect(self.screen, self.p1_current_color, 
                        (self.PLAYER_DATA[1]['GRID_X'] + (self.shape_pos[0] + x) * self.PLAYER_DATA[1]['GRID_SIZE'], 
                         self.PLAYER_DATA[1]['GRID_Y'] + (self.shape_pos[1] + y) * self.PLAYER_DATA[1]['GRID_SIZE'], 
                         self.PLAYER_DATA[1]['GRID_SIZE'], self.PLAYER_DATA[1]['GRID_SIZE']))
                    pygame.draw.rect(self.screen, self.GRAY, 
                        (self.PLAYER_DATA[1]['GRID_X'] + (self.shape_pos[0] + x) * self.PLAYER_DATA[1]['GRID_SIZE'], 
                         self.PLAYER_DATA[1]['GRID_Y'] + (self.shape_pos[1] + y) * self.PLAYER_DATA[1]['GRID_SIZE'], 
                         self.PLAYER_DATA[1]['GRID_SIZE'], self.PLAYER_DATA[1]['GRID_SIZE']), 1)

        if self.entering_initials:
            # Draw initials entry screen if the player is entering initials
            self.draw_initials_input()
            return  

        # Draw game over screen
        if self.game_over:
            self.draw_game_over()
            self.draw_check_leaderboard_button()

            if self.show_leaderboard:
                self.draw_leaderboard()

        else:
            # Draw score
            font = pygame.font.Font(None, 24)
            score_text = font.render(f"Score: {self.score}", True, self.BLACK)
            score_rect = score_text.get_rect()
            score_rect.topleft = (self.PLAYER_DATA[1]['GRID_X'] + 50, 5)
            self.screen.blit(score_text, score_rect)    

            # Draw vertical sabotage meter
            meter_width = 20
            meter_height = 150
            meter_x = self.PLAYER_DATA[1]['GRID_X'] + self.PLAYER_DATA[1]['COLUMNS'] * self.PLAYER_DATA[1]['GRID_SIZE'] + 20
            meter_y = self.PLAYER_DATA[1]['GRID_Y'] + 50

            # Draw meter outline
            pygame.draw.rect(self.screen, self.GRAY, (meter_x, meter_y, meter_width, meter_height), 1)

            # Calculate fill height based on sabotage meter value
            fill_height = int(self.sabotage_meter / self.max_sabotage_meter * meter_height)

            # Draw meter fill
            pygame.draw.rect(self.screen, (255, 0, 0), (meter_x, meter_y + meter_height - fill_height, meter_width, fill_height))

            # Draw threshold indicators
            threshold_color = (0, 255, 255)  # Cyan color for threshold lines
            threshold_thickness = 2
            for threshold in self.sabotage_thresholds:
                threshold_y = meter_y + meter_height - int(threshold / self.max_sabotage_meter * meter_height)
                pygame.draw.line(self.screen, threshold_color, 
                                (meter_x, threshold_y), 
                                (meter_x + meter_width, threshold_y), 
                                threshold_thickness)

            # Draw available sabotages
            font = pygame.font.Font(None, 24)
            for i, sabotage in enumerate(self.available_sabotages):
                text = font.render(f"Sabotage {sabotage + 1}", True, (255, 0, 0))
                self.screen.blit(text, (meter_x + meter_width + 5, meter_y + i * 25))    