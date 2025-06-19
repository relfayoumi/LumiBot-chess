# ui_mainwindow.py - The main application window
import sys
import numpy as np
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLabel, QSlider, QComboBox, QRadioButton, QMessageBox)
from PyQt6.QtGui import QImage, QPixmap, QPainter, QPen
from PyQt6.QtCore import Qt, QPoint
import cv2 as cv

from vision_thread import VisionThread
from chess_controller import ChessController
import chess

class MainWindow(QMainWindow):
    def __init__(self, stockfish_path):
        super().__init__()
        self.setWindowTitle("Vision Chess")
        self.setGeometry(100, 100, 1200, 800)

        # State variables
        self.is_calibrating = False
        self.corners = []
        self.game_in_progress = False
        self.player_turn = False
        self.engine_last_move = None # To store the last move made by the engine for drawing
        self.awaiting_engine_confirmation = False # State to indicate if we're waiting for engine move confirmation
        self._pending_engine_move = None # Store the engine's calculated move before confirmation

        # Core Components
        self.chess_controller = ChessController(stockfish_path)
        self.vision_thread = VisionThread()
        self.vision_thread.new_frame.connect(self.update_video_feed)
        # self.vision_thread.move_detected.connect(self.on_move_detected) # NO LONGER CONNECTED: Manual detection

        self.init_ui()
        self.vision_thread.start()

    def init_ui(self):
        # --- Layouts ---
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        self.setCentralWidget(central_widget)

        controls_layout = QVBoxLayout()
        video_layout = QVBoxLayout()

        # --- Controls Widgets ---
        self.elo_slider = QSlider(Qt.Orientation.Horizontal)
        self.elo_slider.setRange(1320, 3190)
        self.elo_slider.setValue(1500)
        self.elo_slider.valueChanged.connect(self.update_elo_label)
        self.elo_label = QLabel(f"Stockfish Elo: {self.elo_slider.value()}")

        self.color_white_radio = QRadioButton("Play as White")
        self.color_black_radio = QRadioButton("Play as Black")
        self.color_white_radio.setChecked(True)

        self.calibrate_button = QPushButton("Calibrate Board")
        self.calibrate_button.clicked.connect(self.start_calibration)

        self.start_game_button = QPushButton("Start Game")
        self.start_game_button.clicked.connect(self.start_game)
        self.start_game_button.setEnabled(False) # Disabled until calibration is done

        self.confirm_move_button = QPushButton("Confirm My Move")
        self.confirm_move_button.clicked.connect(self.on_confirm_move_clicked)
        self.confirm_move_button.setEnabled(False) # Disabled until game starts and it's player's turn

        self.status_label = QLabel("Welcome! Calibrate the board to begin.")

        # Add controls to layout
        controls_layout.addWidget(self.elo_label)
        controls_layout.addWidget(self.elo_slider)
        controls_layout.addWidget(self.color_white_radio)
        controls_layout.addWidget(self.color_black_radio)
        controls_layout.addWidget(self.calibrate_button)
        controls_layout.addWidget(self.start_game_button)
        controls_layout.addWidget(self.confirm_move_button)
        controls_layout.addWidget(self.status_label)
        controls_layout.addStretch()

        # --- Video Feed Widget ---
        self.video_label = QLabel("Connecting to camera...")
        self.video_label.setFixedSize(640, 480)
        self.video_label.setStyleSheet("border: 1px solid black;")
        self.video_label.mousePressEvent = self.video_feed_clicked
        video_layout.addWidget(self.video_label)

        # --- Combine Layouts ---
        main_layout.addLayout(controls_layout, 1) # 1/3 of space
        main_layout.addLayout(video_layout, 2)    # 2/3 of space

    # --- UI Event Handlers ---
    def update_elo_label(self, value):
        self.elo_label.setText(f"Stockfish Elo: {value}")

    def start_calibration(self):
        self.is_calibrating = True
        self.corners = []
        self.vision_thread.set_corners([]) # Clear corners in vision thread
        self.status_label.setText("Click the 4 corners of the board in the video feed:\nTop-Left, Top-Right, Bottom-Left, Bottom-Right.")
        self.update()

    def video_feed_clicked(self, event):
        if self.is_calibrating and len(self.corners) < 4:
            # Scale click coordinates if video feed is resized
            # Using the video_label's current size for accurate scaling
            video_width = self.vision_thread.cap.get(cv.CAP_PROP_FRAME_WIDTH)
            video_height = self.vision_thread.cap.get(cv.CAP_PROP_FRAME_HEIGHT)
            
            # Calculate actual displayed video dimensions within the QLabel
            label_w = self.video_label.width()
            label_h = self.video_label.height()
            
            aspect_ratio_video = video_width / video_height
            aspect_ratio_label = label_w / label_h

            if aspect_ratio_label > aspect_ratio_video: # Label is wider than video
                displayed_h = label_h
                displayed_w = int(label_h * aspect_ratio_video)
                offset_x = (label_w - displayed_w) / 2
                offset_y = 0
            else: # Label is taller or same aspect ratio as video
                displayed_w = label_w
                displayed_h = int(label_w / aspect_ratio_video)
                offset_x = 0
                offset_y = (label_h - displayed_h) / 2

            # Map click coordinates back to original video frame coordinates
            x_click_on_video = int((event.pos().x() - offset_x) * (video_width / displayed_w))
            y_click_on_video = int((event.pos().y() - offset_y) * (video_height / displayed_h))
            
            # Ensure coordinates are within bounds
            x_click_on_video = max(0, min(int(video_width - 1), x_click_on_video))
            y_click_on_video = max(0, min(int(video_height - 1), y_click_on_video))

            self.corners.append([x_click_on_video, y_click_on_video])
            self.status_label.setText(f"Corner {len(self.corners)}/4 captured. Click the next corner.")
            if len(self.corners) == 4:
                self.vision_thread.set_corners(self.corners)
                self.is_calibrating = False
                self.start_game_button.setEnabled(True)
                self.status_label.setText("Calibration complete! Ready to start the game.")
            self.update() # Redraw to show corners

    def start_game(self):
        elo = self.elo_slider.value()
        color = chess.WHITE if self.color_white_radio.isChecked() else chess.BLACK
        
        # Capture initial board state for vision system AFTER calibration is done
        if not self.vision_thread.capture_initial_board_state():
            QMessageBox.warning(self, "Game Start Error", "Failed to capture initial board state. Ensure camera is working and calibrated.")
            return

        self.chess_controller.start_game(color, elo)

        self.game_in_progress = True
        self.start_game_button.setEnabled(False)
        self.calibrate_button.setEnabled(False)

        # Disable ELO and color selection after game start
        self.elo_slider.setEnabled(False)
        self.color_white_radio.setEnabled(False)
        self.color_black_radio.setEnabled(False)
        self.engine_last_move = None # Reset engine move display at start of new game
        self.awaiting_engine_confirmation = False # Reset confirmation state
        self._pending_engine_move = None # Clear pending move

        if self.chess_controller.player_color == self.chess_controller.board.turn:
            self.player_turn = True
            self.status_label.setText("Game started. It's your turn. Make your move then click 'Confirm My Move'.")
            self.confirm_move_button.setText("Confirm My Move") # Ensure correct text
            self.confirm_move_button.setEnabled(True) # Enable confirm button for player
        else:
            self.player_turn = False
            self.status_label.setText("Game started. Stockfish is thinking...")
            self.confirm_move_button.setEnabled(False) # Disable confirm button for Stockfish's turn
            self.request_engine_move()

    def on_confirm_move_clicked(self):
        if not self.game_in_progress:
            return # Should not happen if button is correctly enabled/disabled

        if self.awaiting_engine_confirmation:
            if self._pending_engine_move:
                # Push the engine's move to the board
                self.chess_controller.board.push(self._pending_engine_move)
                self.status_label.setText(f"Stockfish played {self._pending_engine_move.uci()}. Your turn.")
                
                # NEW: Capture current board state AFTER engine move for vision system's new base
                if not self.vision_thread.capture_current_board_state_for_persisted():
                    QMessageBox.warning(self, "Vision Error", "Failed to update vision system's board state after engine move.")
                    # Depending on severity, might need more robust error handling
                
                # Reset engine confirmation state
                self.awaiting_engine_confirmation = False
                self._pending_engine_move = None # Clear pending move
                self.engine_last_move = None # FIX: Clear the engine's last move display once confirmed and it's player's turn

                # Reset button text and check game status
                self.confirm_move_button.setText("Confirm My Move")
                self.player_turn = True # It's now player's turn

                # Check for game over conditions
                if self.chess_controller.board.is_checkmate():
                    self.status_label.setText("Checkmate! Stockfish wins.")
                    self.game_in_progress = False
                    self.confirm_move_button.setEnabled(False)
                    self.engine_last_move = None # Clear engine move arrow on game over
                elif self.chess_controller.board.is_stalemate():
                    self.status_label.setText("Stalemate! Game is a draw.")
                    self.game_in_progress = False
                    self.confirm_move_button.setEnabled(False)
                    self.engine_last_move = None
                elif self.chess_controller.board.is_insufficient_material():
                    self.status_label.setText("Draw by insufficient material.")
                    self.game_in_progress = False
                    self.confirm_move_button.setEnabled(False)
                    self.engine_last_move = None
                elif self.chess_controller.board.can_claim_fifty_moves():
                    self.status_label.setText("Draw by fifty-move rule.")
                    self.game_in_progress = False
                    self.confirm_move_button.setEnabled(False)
                    self.engine_last_move = None
                elif self.chess_controller.board.can_claim_threefold_repetition():
                    self.status_label.setText("Draw by threefold repetition.")
                    self.game_in_progress = False
                    self.confirm_move_button.setEnabled(False)
                    self.engine_last_move = None
                else: # Check for check after any move, if game is still in progress
                    if self.chess_controller.board.is_check():
                        self.status_label.setText(self.status_label.text() + " Your King is in CHECK!")
                
                # Only enable confirm button if game is still going and it's player's turn
                if self.game_in_progress and self.player_turn:
                    self.confirm_move_button.setEnabled(True)
                else:
                    self.confirm_move_button.setEnabled(False)

            else:
                # This state should ideally not be reached if button enabling is correct
                self.status_label.setText("Error: No pending Stockfish move to confirm.")
                self.confirm_move_button.setEnabled(True) # Allow user to try again
            self.update() # Refresh display to clear engine arrow if game over or turn changed
            return # Exit function, as engine confirmation handled
        
        # --- Existing logic for player move confirmation ---
        elif self.player_turn: # Only proceed if it's the player's turn
            self.status_label.setText("Detecting your move... Please wait.")
            self.confirm_move_button.setEnabled(False) # Disable button while detecting
            self.engine_last_move = None # Clear any previous engine move arrow
            self.update() # Update UI to remove arrow immediately

            # Call the new robust detection cycle in vision_thread
            detected_uci_move = self.vision_thread.detect_player_move_cycle(self.chess_controller.board)

            if detected_uci_move:
                if self.chess_controller.validate_and_push_move(detected_uci_move):
                    self.status_label.setText(f"You played {detected_uci_move}. Stockfish is thinking...")
                    # Check for check after player move
                    if self.chess_controller.board.is_check():
                        self.status_label.setText(self.status_label.text() + " Your King is in CHECK!")
                    self.player_turn = False
                    self.request_engine_move()
                else:
                    self.status_label.setText(f"Move '{detected_uci_move}' detected by vision, but it's illegal. Please make a legal move and click 'Confirm My Move' again.")
                    self.confirm_move_button.setEnabled(True) # Re-enable for retry
            else:
                self.status_label.setText("No legal move detected. Please ensure piece is clearly moved and click 'Confirm My Move' again.")
                self.confirm_move_button.setEnabled(True) # Re-enable for retry
        
    def request_engine_move(self):
        # Ensure it's not already awaiting confirmation to prevent double calls or issues
        if self.awaiting_engine_confirmation:
            return

        engine_move = self.chess_controller.get_engine_move()
        if engine_move:
            self._pending_engine_move = engine_move # Store, but don't push yet
            self.engine_last_move = engine_move # Set for drawing the arrow

            self.awaiting_engine_confirmation = True # Set state
            self.confirm_move_button.setText("Confirm Stockfish Move")
            self.confirm_move_button.setEnabled(True)
            self.status_label.setText(f"Stockfish suggests {engine_move.uci()}. Confirm move?")
            self.update() # Force update to show arrow and new button text
        else:
            # This case happens if engine doesn't return a move (e.g., game over already)
            if self.chess_controller.board.is_game_over():
                self.status_label.setText("Game over.")
                self.game_in_progress = False
                self.confirm_move_button.setEnabled(False)
                self.engine_last_move = None # Clear arrow on game over


    def update_video_feed(self, frame):
        #Updates the video label with a new frame from the VisionThread.#
        h, w, ch = frame.shape
        bytes_per_line = ch * w
        
        qt_image = QImage(frame.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qt_image)
        scaled_pixmap = pixmap.scaled(self.video_label.size(), Qt.AspectRatioMode.KeepAspectRatio)
        editable_image = scaled_pixmap.toImage()

        painter = QPainter(editable_image)

        # Draw calibration corners on the editable_image
        if self.is_calibrating and self.corners:
            pen = QPen(Qt.GlobalColor.green, 3)
            painter.setPen(pen)

            # These dimensions are for the original video frame
            video_width_orig = self.vision_thread.cap.get(cv.CAP_PROP_FRAME_WIDTH)
            video_height_orig = self.vision_thread.cap.get(cv.CAP_PROP_FRAME_HEIGHT)
            
            label_w = self.video_label.width()
            label_h = self.video_label.height()
            
            aspect_ratio_video = video_width_orig / video_height_orig
            aspect_ratio_label = label_w / label_h

            if aspect_ratio_label > aspect_ratio_video: # Label is wider than video
                displayed_h = label_h
                displayed_w = int(label_h * aspect_ratio_video)
                offset_x = (label_w - displayed_w) / 2
                offset_y = 0
            else: # Label is taller or same aspect ratio as video
                displayed_w = label_w
                displayed_h = int(label_w / aspect_ratio_video)
                offset_x = 0
                offset_y = (label_h - displayed_h) / 2

            # Calculate scaling factors for drawing from original video frame to QLabel's displayed area
            scale_factor_x = displayed_w / video_width_orig
            # scale_factor_y would be the same as scale_factor_x due to KeepAspectRatio

            for corner in self.corners:
                # Apply scaling and offset for drawing the captured corners
                draw_x = int(corner[0] * scale_factor_x + offset_x)
                draw_y = int(corner[1] * scale_factor_x + offset_y)
                painter.drawEllipse(QPoint(draw_x, draw_y), 5, 5) # Draw a circle for visibility
        
        # Draw Stockfish's move as a green arrow
        # Draw if game is in progress and there's a last engine move OR a pending engine move
        if self.game_in_progress and (self.engine_last_move or self._pending_engine_move):
            move_to_draw = self.engine_last_move if self.engine_last_move else self._pending_engine_move

            board_dim = 512 # The cropped board image size
            label_w = self.video_label.width()
            label_h = self.video_label.height()

            # Determine the scaling factor and offset for the 512x512 board image displayed in QLabel
            aspect_ratio_board = 1.0 # 512x512 is square
            aspect_ratio_label = label_w / label_h

            if aspect_ratio_label > aspect_ratio_board: # Label is wider than square board
                displayed_h_board = label_h
                displayed_w_board = int(label_h * aspect_ratio_board)
                offset_x_board = (label_w - displayed_w_board) / 2
                offset_y_board = 0
            else: # Label is taller or same aspect ratio as square board
                displayed_w_board = label_w
                displayed_h_board = int(label_w / aspect_ratio_board)
                offset_x_board = 0
                offset_y_board = (label_h - displayed_h_board) / 2

            scale_factor_board = displayed_w_board / board_dim

            # Get pixel coordinates for the 512x512 board from vision_thread
            from_pixels = self.vision_thread.square_to_pixels(move_to_draw.from_square)
            to_pixels = self.vision_thread.square_to_pixels(move_to_draw.to_square)

            # Apply scaling and offset to map to QLabel coordinates
            start_x = int(from_pixels[0] * scale_factor_board + offset_x_board)
            start_y = int(from_pixels[1] * scale_factor_board + offset_y_board)
            end_x = int(to_pixels[0] * scale_factor_board + offset_x_board)
            end_y = int(to_pixels[1] * scale_factor_board + offset_y_board)

            # Adjust end_x to be one tile (64 pixels on the 512x512 board) to the left
            # This adjustment needs to be scaled to the QLabel's displayed dimensions
            adjusted_tile_offset = int(64 * scale_factor_board) # 64 pixels is one tile width
            
            # Adjust start_x to be one tile to the left
            start_x -= adjusted_tile_offset

            # Adjust end_x to be one tile to the left (from the previous request)
            end_x -= adjusted_tile_offset

            painter.setPen(QPen(Qt.GlobalColor.green, 4)) # Green, 4 pixels thick
            painter.drawLine(start_x, start_y, end_x, end_y)

            # Draw arrowhead (simple triangle)
            arrow_size = 15
            angle = np.arctan2(end_y - start_y, end_x - start_x)

            p1 = QPoint(end_x, end_y)
            p2 = QPoint(int(end_x - arrow_size * np.cos(angle - np.pi/6)),
                        int(end_y - arrow_size * np.sin(angle - np.pi/6)))
            p3 = QPoint(int(end_x - arrow_size * np.cos(angle + np.pi/6)),
                        int(end_y - arrow_size * np.sin(angle + np.pi/6)))

            painter.drawLine(p1, p2)
            painter.drawLine(p1, p3)

        painter.end() # End painter session after all drawing

        # Set the modified QImage back to the QLabel as a QPixmap
        self.video_label.setPixmap(QPixmap.fromImage(editable_image))


    def closeEvent(self, event):
        #Ensure threads are stopped when the window closes.
        self.vision_thread.stop()
        self.chess_controller.close_engines()
        event.accept()