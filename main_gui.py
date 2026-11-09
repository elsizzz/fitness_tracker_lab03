import sys
from PySide6.QtWidgets import QApplication
from app.database import DatabaseManager
from app.gui import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    db_manager = DatabaseManager()
    window = MainWindow(db_manager)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()