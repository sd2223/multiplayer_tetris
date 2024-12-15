# Multiplayer Tetris

A two-player Tetris game designed for Raspberry Pi with PiTFT display, featuring network play and sabotage mechanics.

## Features
- Two-player networked gameplay
- Sabotage system to affect opponent's game
- High score leaderboard
- GPIO button controls for Raspberry Pi

## Components
The game consists of three main Python files:
- **`main.py`**: Handles game initialization, matchmaking, and the main game loop.
- **`network.py`**: Manages network communication between players using UDP.
- **`tetris_game.py`**: Implements the core Tetris game logic and rendering.

## Requirements
- Raspberry Pi with PiTFT display
- Python 3.x
- Pygame library
- RPi.GPIO library

## Setup
1. Clone the repository to your Raspberry Pi:
    ```bash
    git clone https://github.com/sd2223/multiplayer_tetris.git
    ```
2. Install required libraries:
    ```bash
    pip install pygame RPi.GPIO
    ```
3. Connect buttons to the specified GPIO pins (see **GPIO Setup** section).

## GPIO Setup
Connect buttons to the following GPIO pins:
- **Quit**: GPIO 17
- **Rotate**: GPIO 5
- **Move Down**: GPIO 12
- **Move Left**: GPIO 16
- **Move Right**: GPIO 6
- **Sabotage**: GPIO 4

## How to Play
1. Run the game:
    ```bash
    python main.py
    ```
2. The game will attempt to find an opponent on the network.
3. Once connected, the Tetris game will begin.
4. Use the GPIO buttons to control your Tetris piece.
5. Clear lines to score points and fill your sabotage meter.
6. Use sabotages to hinder your opponent's gameplay.

## Network Setup
Ensure both Raspberry Pis are on the same network. Update the `PLAYER2_IP` in `main.py` with the IP address of the second player's Raspberry Pi.

## Sabotage System
The game features a sabotage meter that fills as you play. When it reaches certain thresholds, you can activate sabotages against your opponent:
- Randomize current piece
- Increase piece fall speed
- Scramble controls

## High Scores
High scores are saved in a `highscores.json` file. The top 5 scores are displayed on the leaderboard.

## Contributing
Feel free to fork this repository and submit pull requests for any improvements or bug fixes.
