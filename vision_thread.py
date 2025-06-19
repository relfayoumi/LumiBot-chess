import cv2 as cv
import numpy as np
import time
from math import floor
from PyQt6.QtCore import QThread, pyqtSignal

import table # Your lookup table
import chess # Import chess module for board operations

class VisionThread(QThread):
    # Signals to send data to the main UI thread
    new_frame = pyqtSignal(np.ndarray)

    def __init__(self, camera_index=0):
        super().__init__()
        self.camera_index = camera_index
        self.cap = None
        self.corners = []
        self._is_running = True
        self.persisted_board_gray = None # The reference board state for move detection

        # Global lighting settings from reference code
        self.current_alpha = 1.0 # Start with default contrast 1.0
        self.fixed_beta = 0      # Fixed brightness offset

    def run(self):
        #The main loop for the vision thread, primarily for frame capture and display.
        self.cap = cv.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            print("Error: Could not open camera.")
            return

        while self._is_running:
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            if len(self.corners) == 4:
                # Once calibrated, process the board for display
                cropped_color = self._crop_board(frame)
                # Apply current lighting settings for display
                adjusted_display_frame = self._adjust_lighting(cropped_color, alpha=self.current_alpha, beta=self.fixed_beta)
                
                # NEW: Draw the grid on the adjusted color frame before emitting
                # Using a green color (0, 255, 0) and thickness of 1 for better visibility
                adjusted_display_frame_with_grid = self._draw_grid(adjusted_display_frame, color=(0, 255, 0), thickness=1)
                
                self.new_frame.emit(cv.cvtColor(adjusted_display_frame_with_grid, cv.COLOR_BGR2RGB))
            else:
                # Before calibration, just emit the raw frame
                self.new_frame.emit(cv.cvtColor(frame, cv.COLOR_BGR2RGB))
            
            time.sleep(1 / 30) # Limit to ~30 FPS

        self.cap.release()

    def _crop_board(self, image):
        # Crops and transforms the chessboard image to 512x512.
        newCorners = np.float32([[0,0],[512,0],[0,512],[512,512]])
        warpMap = cv.getPerspectiveTransform(np.asarray(self.corners).astype(np.float32), newCorners)
        # Use (512, 512) for the output size of warpPerspective
        return cv.warpPerspective(image, warpMap, (512, 512))

    def _draw_grid(self, img, color=(255,255,255), thickness=2):
        #Draws a chessboard grid on the image.#
        for i in range(0, 513, 64):
            img = cv.line(img, (i, 0), (i, 512), color, thickness)
            img = cv.line(img, (0, i), (512, i), color, thickness)
        return img

    def _board_difference(self, ob, nb, beta=3):
        # Calculates the absolute difference between two grayscale board images.
        return cv.absdiff(cv.GaussianBlur(ob,(beta, beta), 0), cv.GaussianBlur(nb,(beta, beta), 0))

    def _adjust_lighting(self, image, alpha=None, beta=None):
        # Adjusts the contrast (alpha) and brightness (beta) of an image.#
        if beta is None:
            beta = self.fixed_beta
        if alpha is None:
            alpha = self.current_alpha

        if len(image.shape) == 2: # Grayscale image
            image = cv.cvtColor(image, cv.COLOR_GRAY2BGR)

        adjusted = cv.convertScaleAbs(image, alpha=alpha, beta=beta)
        return adjusted

    def square_to_pixels(self, square_index):
        # Converts a chess.Square index (0-63) to pixel coordinates (center of the square)
        # on a 512x512 board image.
        file = chess.square_file(square_index) # 0-7 for file (a-h)
        rank = chess.square_rank(square_index) # 0-7 for rank (1-8)
        
        # In a 512x512 image, each square is 64x64 pixels
        # x-coordinate (file): 0*64 to 7*64
        # y-coordinate (rank): 0*64 to 7*64
        # Board coordinates usually have rank 1 at bottom, 8 at top.
        # Image coordinates have y=0 at top. So, (7-rank) maps 0->7, 7->0.
        center_x = int(file * 64 + 32)
        center_y = int((7 - rank) * 64 + 32) # (7 - rank) to invert y-axis for image
        return (center_x, center_y)

    def _find_uci_move_from_difference_image(self, diff_img, board_obj):
        
        # Analyzes a difference image to identify a chess move.
        # Returns the UCI move string if found and legal, otherwise None.
        
        averages = []
        for x in range(0, 64):
            tile = self._get_tile(diff_img, x + 1)
            averages.append(np.average(tile))
        
        # Sort indices by average difference to find the most changed squares
        sorted_indices = np.argsort(averages)
        # The two squares with highest difference are likely the 'from' and 'to' squares
        from_sq_idx_raw, to_sq_idx_raw = sorted_indices[-2], sorted_indices[-1]

        # Convert 0-based indices to 1-based for lookup table
        origin_sq_idx_1based = from_sq_idx_raw + 1
        dest_sq_idx_1based = to_sq_idx_raw + 1

        print(f"Vision detected potential changed tiles (0-based): {from_sq_idx_raw}, {to_sq_idx_raw}")
        print(f"Corresponding 1-based lookup indices: {origin_sq_idx_1based}, {dest_sq_idx_1based}")
        
        # Check if the change is significant enough for the 'to' square
        if averages[to_sq_idx_raw] < 20: # Heuristic threshold from your original code
            print(f"Change on target square ({averages[to_sq_idx_raw]:.2f}) below threshold (20). No move detected.")
            return None # No significant change, likely not a move

        # Try both permutations of origin and destination, as vision may not distinguish
        # the order of piece pickup vs. drop
        candidate_moves = []
        try:
            origin_sq = table.lookup(origin_sq_idx_1based)
            dest_sq = table.lookup(dest_sq_idx_1based)
            candidate_moves.append(chess.Move(origin_sq, dest_sq))
        except ValueError:
            pass # Invalid square index from lookup table

        try:
            origin_sq = table.lookup(dest_sq_idx_1based)
            dest_sq = table.lookup(origin_sq_idx_1based)
            candidate_moves.append(chess.Move(origin_sq, dest_sq))
        except ValueError:
            pass # Invalid square index from lookup table

        # Try to find a legal move among candidates
        for move in candidate_moves:
            if move in board_obj.legal_moves: # board_obj is passed from ChessController
                print(f"Legal move found: {move.uci()}")
                return move.uci()
            # The explicit castling check found here in original was redundant as
            # `move in board_obj.legal_moves` already handles castling correctly.

        print("No legal move found among detected changes for current board state.")
        return None

    def detect_player_move_cycle(self, board_obj):
        
        # Performs a full move detection cycle, including iterative contrast adjustment,
        # as per the user's original reference code.
        # Returns the detected UCI move string if found and confirmed, otherwise None.
        # Updates self.persisted_board_gray and self.current_alpha on success.
    
        if not self.cap or not self.cap.isOpened():
            print("Camera not open for move detection cycle.")
            return None

        print("\n--- Starting move detection cycle ---")

        # Capture initial frame for comparison
        ret, initial_full_frame = self.cap.read()
        if not ret:
            print("Error: Could not read frame for move detection.")
            return None

        initial_cropped_color = self._crop_board(initial_full_frame)
        
        # Ensure persisted_board_gray is set before comparison, especially on first move
        if self.persisted_board_gray is None:
            initial_adjusted_color = self._adjust_lighting(initial_cropped_color, alpha=self.current_alpha, beta=self.fixed_beta)
            self.persisted_board_gray = cv.cvtColor(initial_adjusted_color, cv.COLOR_BGR2GRAY)
            print("Initial persisted_board_gray set for first detection.")


        # Perform detection with current lighting settings first
        # Capture a new frame for the current board state (after player's physical move)
        ret, current_full_frame = self.cap.read()
        if not ret:
            print("Error: Could not read current frame for move detection.")
            return None
        
        newBoard_current_cropped_color = self._crop_board(current_full_frame)
        newBoard_current_adjusted_color = self._adjust_lighting(newBoard_current_cropped_color, alpha=self.current_alpha, beta=self.fixed_beta)
        newBoard_current_gray = cv.cvtColor(newBoard_current_adjusted_color, cv.COLOR_BGR2GRAY)

        # Ensure oldBoard_for_comparison is correctly aligned with newBoard_current_gray's lighting
        # The stored persisted_board_gray might be from a different alpha if a previous adjustment occurred.
        # So, we adjust it for comparison.
        oldBoard_for_comparison_bgr = cv.cvtColor(self.persisted_board_gray, cv.COLOR_GRAY2BGR)
        adjusted_oldBoard_gray_for_comp = cv.cvtColor(self._adjust_lighting(oldBoard_for_comparison_bgr, alpha=self.current_alpha, beta=self.fixed_beta), cv.COLOR_BGR2GRAY)

        diff_raw = self._board_difference(adjusted_oldBoard_gray_for_comp, newBoard_current_gray, 3)
        ret_thresh, difference = cv.threshold(diff_raw, 20, 255, cv.THRESH_BINARY) # Initial threshold 20

        print(f"Attempting initial detection with alpha={self.current_alpha:.1f}")
        uci_move = self._find_uci_move_from_difference_image(difference, board_obj)

        if uci_move:
            print("Move detected with current lighting settings.")
            self.persisted_board_gray = newBoard_current_gray # Update base image on success
            return uci_move
        else:
            print("No legal move detected with initial settings. Trying iterative contrast adjustment...")
            start_time = time.time()
            tested_alpha = []

            # --- Phase 1: Contrast below 1.0 (from 0.9 down to 0.1) ---
            for alpha_val in np.arange(0.9, 0.0, -0.1): # Starts at 0.9, goes down to 0.1 (exclusive of 0.0)
                if time.time() - start_time > 5:
                    print("Contrast adjustment timeout (Phase 1).")
                    break
                tested_alpha.append(round(alpha_val, 2))

                print(f"Trying contrast alpha: {alpha_val:.1f}")

                ret_rescan, rescan_frame_full = self.cap.read()
                if not ret_rescan:
                    print("Error: Could not read frame for re-scan during contrast adjustment.")
                    break

                adjusted_rescan_frame_color = self._adjust_lighting(rescan_frame_full, alpha=alpha_val, beta=self.fixed_beta)
                newBoard_adjusted_color = self._crop_board(adjusted_rescan_frame_color)
                newBoard_adjusted_gray = cv.cvtColor(newBoard_adjusted_color, cv.COLOR_BGR2GRAY)

                adjusted_oldBoard_gray = cv.cvtColor(self._adjust_lighting(oldBoard_for_comparison_bgr, alpha=alpha_val, beta=self.fixed_beta), cv.COLOR_BGR2GRAY)

                diff_raw_adjusted = self._board_difference(adjusted_oldBoard_gray, newBoard_adjusted_gray, 3)
                ret_adjusted, difference_adjusted = cv.threshold(diff_raw_adjusted, 40, 255, cv.THRESH_BINARY) # Threshold 40 for this phase

                uci_move = self._find_uci_move_from_difference_image(difference_adjusted, board_obj)
                if uci_move:
                    self.current_alpha = alpha_val # Save the successful alpha
                    self.persisted_board_gray = newBoard_adjusted_gray # Update base image on success
                    print(f"Move detected after contrast adjustment with alpha={self.current_alpha:.1f}.")
                    return uci_move
                
            # --- Phase 2: Contrast above 1.0 (from 1.1 up to 2.0) if not detected yet ---
            if not uci_move:
                for alpha_val in np.arange(1.1, 2.2, 0.1): # Starts at 1.1, goes up to 2.0 (exclusive of 2.2)
                    if time.time() - start_time > 10: # Increased timeout for both phases
                        print("Contrast adjustment timeout (Phase 2).")
                        break
                    tested_alpha.append(round(alpha_val, 2))

                    print(f"Trying contrast alpha: {alpha_val:.1f}")

                    ret_rescan, rescan_frame_full = self.cap.read()
                    if not ret_rescan:
                        print("Error: Could not read frame for re-scan during contrast adjustment.")
                        break

                    adjusted_rescan_frame_color = self._adjust_lighting(rescan_frame_full, alpha=alpha_val, beta=self.fixed_beta)
                    newBoard_adjusted_color = self._crop_board(adjusted_rescan_frame_color)
                    newBoard_adjusted_gray = cv.cvtColor(newBoard_adjusted_color, cv.COLOR_BGR2GRAY)

                    adjusted_oldBoard_gray = cv.cvtColor(self._adjust_lighting(oldBoard_for_comparison_bgr, alpha=alpha_val, beta=self.fixed_beta), cv.COLOR_BGR2GRAY)

                    diff_raw_adjusted = self._board_difference(adjusted_oldBoard_gray, newBoard_adjusted_gray, 3)
                    ret_adjusted, difference_adjusted = cv.threshold(diff_raw_adjusted, 70, 255, cv.THRESH_BINARY) # Threshold 70 for this phase

                    uci_move = self._find_uci_move_from_difference_image(difference_adjusted, board_obj)
                    if uci_move:
                        self.current_alpha = alpha_val # Save the successful alpha
                        self.persisted_board_gray = newBoard_adjusted_gray # Update base image on success
                        print(f"Move detected after contrast adjustment with alpha={self.current_alpha:.1f}.")
                        return uci_move
            
            print("No legal move detected after all contrast adjustments.")
            print(f"Tested alphas: {tested_alpha}")
            # If still no move, persisted_board_gray remains unchanged, allowing retry
            return None

    def _get_tile(self, img, tile_idx):
        #Extracts a tile (64x64) from the board image given a 1-based tile index.#
        x = (tile_idx - 1) % 8
        y = floor((tile_idx - 1) / 8)
        return img[y*64:(y+1)*64, x*64:(x+1)*64]

    def set_corners(self, corners):
        #Receives corner points from the UI and resets board state.#
        self.corners = corners
        self.persisted_board_gray = None # Clear persisted board after new calibration
        # After calibration, we need to capture the initial board state.
        # The main thread will call detect_player_move_cycle once game starts for initial read.

    def capture_initial_board_state(self):
        # Captures the very first board state after calibration and sets persisted_board_gray.
        # This is called by MainWindow.start_game.
        
        if not self.cap or not self.cap.isOpened() or not self.corners:
            print("Cannot capture initial board state: camera not open or not calibrated.")
            return False

        ret, initial_frame = self.cap.read()
        if not ret:
            print("Error: Could not read frame for initial board state capture.")
            return False
        
        cropped_color = self._crop_board(initial_frame)
        adjusted_color = self._adjust_lighting(cropped_color, alpha=self.current_alpha, beta=self.fixed_beta)
        self.persisted_board_gray = cv.cvtColor(adjusted_color, cv.COLOR_BGR2GRAY)
        print("Initial board state captured and persisted.")
        return True

    def capture_current_board_state_for_persisted(self):
        # Captures the current board state and sets it as the new persisted_board_gray.
        # This is called by MainWindow after a legal move (player or engine) is made
        # and pushed to the chess.Board object.
        if not self.cap or not self.cap.isOpened() or not self.corners:
            print("Cannot capture current board state: camera not open or not calibrated.")
            return False

        ret, current_frame = self.cap.read()
        if not ret:
            print("Error: Could not read frame for current board state capture.")
            return False
        
        cropped_color = self._crop_board(current_frame)
        adjusted_color = self._adjust_lighting(cropped_color, alpha=self.current_alpha, beta=self.fixed_beta)
        self.persisted_board_gray = cv.cvtColor(adjusted_color, cv.COLOR_BGR2GRAY)
        print("Persisted board state updated after move.")
        return True

    def stop(self):
        #Stops the thread.#
        self._is_running = False