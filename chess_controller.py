import chess
import chess.engine

class ChessController:
    def __init__(self, stockfish_path):
        self.board = chess.Board()
        self.engine = None
        self.stockfish_path = stockfish_path
        self.analysis_engine = None

    def start_game(self, player_color, elo_level):
        #Starts a new game with the specified settings.
        self.board.reset()
        self.player_color = player_color
        
        # Configure the main game engine
        self.engine = chess.engine.SimpleEngine.popen_uci(self.stockfish_path)
        self.engine.configure({"UCI_LimitStrength": True, "UCI_Elo": elo_level})

        # Configure a separate, powerful engine for analysis
        self.analysis_engine = chess.engine.SimpleEngine.popen_uci(self.stockfish_path)
        self.analysis_engine.configure({"UCI_Elo": 3000})

    def get_engine_move(self):
        #Gets the best move from Stockfish.
        if not self.board.is_game_over() and self.engine:
            result = self.engine.play(self.board, chess.engine.Limit(time=1.0))
            return result.move
        return None

    def validate_and_push_move(self, uci_move):
        #Validates a move from the vision system and pushes it to the board.
        try:
            move = chess.Move.from_uci(uci_move)
            if move in self.board.legal_moves:
                self.board.push(move)
                return True
            else:
                # Try to handle castling, which can be detected as king moving two squares
                king_move = self.board.find_move(move.from_square, move.to_square)
                if king_move:
                    self.board.push(king_move)
                    return True
                return False
        except Exception:
            return False
            
    def get_analysis(self, fen):
        #Analyzes a board position using the high-elo engine.
        if self.analysis_engine:
            info = self.analysis_engine.analyse(chess.Board(fen), chess.engine.Limit(depth=20))
            return info
        return None

    def close_engines(self):
        #Properly closes the engine processes.
        if self.engine:
            self.engine.quit()
        if self.analysis_engine:
            self.analysis_engine.quit()