# LumiBot Chess

A computer vision-based chess application that allows you to play chess against Stockfish AI using a physical chessboard and a camera. The application uses computer vision to detect moves on a real chessboard and displays the game state in real-time.

## Features

- **Computer Vision Move Detection**: Uses OpenCV to detect chess moves from a camera feed of a physical board
- **Stockfish Integration**: Play against the powerful Stockfish chess engine with adjustable ELO ratings (1320-3190)
- **Real-time Board Analysis**: Visual feedback with move arrows displayed on the camera feed
- **Adaptive Lighting**: Automatically adjusts contrast to detect moves in various lighting conditions
- **Board Calibration**: Easy 4-corner calibration system for accurate board tracking
- **Interactive GUI**: Built with PyQt6 for a user-friendly interface
- **Flexible Game Setup**: Choose to play as White or Black

## Requirements

### System Requirements
- Python 3.7 or higher
- Webcam or USB camera
- Physical chess set with a standard 8x8 board

### Python Dependencies
- `PyQt6` - GUI framework
- `opencv-python` (cv2) - Computer vision and image processing
- `numpy` - Numerical computations
- `python-chess` - Chess logic and Stockfish engine interface

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/relfayoumi/LumiBot-chess.git
   cd LumiBot-chess
   ```

2. **Install Python dependencies**
   ```bash
   pip install PyQt6 opencv-python numpy python-chess
   ```

3. **Configure Stockfish path**
   
   Edit `main.py` and update the `stockfish_path` variable to point to your Stockfish executable:
   
   ```python
   # For Windows:
   stockfish_path = "path/to/stockfish/stockfish.exe"
   
   # For Linux/Mac:
   stockfish_path = "path/to/stockfish/stockfish"
   ```
   
   The repository includes Stockfish in the `stockfish/` directory. You may need to compile it from source or download a pre-compiled binary for your platform.

## Usage

### Starting the Application

Run the main application:
```bash
python main.py
```

### Setting Up a Game

1. **Position your camera**: Mount your camera above the chessboard with a clear, unobstructed view of all 64 squares.

2. **Calibrate the board**:
   - Click the "Calibrate Board" button
   - Click the four corners of the chessboard in this order:
     1. Top-Left corner
     2. Top-Right corner
     3. Bottom-Left corner
     4. Bottom-Right corner
   - The board will be warped to a 512x512 pixel square for analysis

3. **Configure game settings**:
   - Adjust the ELO slider to set Stockfish's difficulty (1320-3190)
   - Choose your color using the radio buttons (Play as White or Play as Black)

4. **Start the game**:
   - Click "Start Game"
   - The application captures the initial board state
   - If you're playing as White, make your first move; if Black, Stockfish will move first

### Playing the Game

#### Your Turn
1. Make your move on the physical board
2. Click "Confirm My Move"
3. The application will detect your move using computer vision
4. If the move is legal, it will be accepted and Stockfish will respond

#### Stockfish's Turn
1. Stockfish calculates its move
2. A green arrow appears on the video feed showing the suggested move
3. Click "Confirm Stockfish Move"
4. Execute Stockfish's move on the physical board

### Tips for Best Results

- **Lighting**: Ensure consistent, even lighting on the chessboard
- **Camera Position**: Keep the camera stable and perpendicular to the board
- **Piece Contrast**: Use pieces with good contrast against the board for better detection
- **Move Clearly**: Make single, deliberate moves and avoid touching multiple pieces
- **Wait for Detection**: Give the system a moment to process each move

## Project Structure

```
LumiBot-chess/
├── main.py                 # Application entry point
├── ui_mainwindow.py        # Main window and UI logic
├── chess_controller.py     # Chess game logic and Stockfish integration
├── vision_thread.py        # Computer vision processing and move detection
├── table.py                # Chess square lookup table for coordinate conversion
├── stockfish/              # Stockfish chess engine directory
│   ├── src/                # Stockfish source code
│   └── README.md           # Stockfish documentation
└── README.md               # This file
```

### Component Overview

- **main.py**: Initializes the Qt application and launches the main window
- **ui_mainwindow.py**: Handles all GUI elements, user interactions, and game flow coordination
- **chess_controller.py**: Manages the chess board state, validates moves, and interfaces with Stockfish engines (both game engine at selected ELO and analysis engine at ELO 3000)
- **vision_thread.py**: Runs in a separate thread to capture video frames, perform board calibration, detect moves through image differencing, and adaptively adjust contrast for various lighting conditions
- **table.py**: Provides lookup functions to convert between tile indices (1-64) and chess square coordinates

## How It Works

### Computer Vision Pipeline

1. **Board Calibration**: Four corner points are used to create a perspective transformation matrix, warping the board to a perfect 512x512 square
2. **Move Detection**: The system compares the current board state with a reference image to detect changes
3. **Difference Analysis**: Changed squares are identified using Gaussian blur and thresholding
4. **Move Validation**: The two most-changed squares are tested as potential move origins/destinations against legal moves
5. **Adaptive Lighting**: If no legal move is detected, the system iteratively adjusts contrast (0.1-2.0) to find the optimal settings
6. **State Persistence**: Once a move is confirmed, the current board state becomes the new reference for the next move

### Chess Engine Integration

- **Dual Engine Setup**: One engine plays at the user-selected ELO (1320-3190), while a separate high-strength engine (ELO 3000) is available for analysis
- **Move Confirmation**: Stockfish's moves are displayed visually before being executed, allowing the user to physically make the move on the board
- **Legal Move Validation**: All detected moves are validated against the current legal moves before being accepted

## Acknowledgments

This project uses [Stockfish](https://stockfishchess.org/), a powerful open-source chess engine, licensed under the GNU General Public License v3.0.

## Troubleshooting

### Move Detection Issues
- **Problem**: Moves are not being detected
- **Solutions**: 
  - Ensure good lighting on the board
  - Recalibrate the board if the camera has moved
  - Make clear, deliberate moves
  - Check that pieces have good contrast with the board

### Camera Not Found
- **Problem**: "Error: Could not open camera"
- **Solutions**:
  - Check that your camera is connected
  - Verify no other application is using the camera
  - Try changing the camera index in `vision_thread.py` (line 28)

### Stockfish Not Found
- **Problem**: Engine fails to start
- **Solutions**:
  - Verify the `stockfish_path` in `main.py` points to a valid Stockfish executable
  - Check file permissions on the Stockfish binary
  - Try using an absolute path instead of a relative path

## License

This project includes Stockfish, which is licensed under the GNU General Public License v3.0. See `stockfish/Copying.txt` for details.

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests to improve the application.
