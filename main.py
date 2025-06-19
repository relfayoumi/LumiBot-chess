import sys
from PyQt6.QtWidgets import QApplication
from ui_mainwindow import MainWindow

if __name__ == '__main__':
    app = QApplication(sys.argv)
    stockfish_path = "D:\\Ai vision\\chessvision-main\\stockfish\\stockfish.exe"
    window = MainWindow(stockfish_path)
    window.show()
    sys.exit(app.exec())