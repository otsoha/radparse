import sys
from PySide6.QtCore import QSize, Qt, QSettings
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from radparse.parser import (
    parse_and_write,
)
from pathlib import Path
import json


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # load config
        self.settings = QSettings("MustelidaeSoftware", "RadParse")
        self.default_dir = self.settings.value("default_path", str(Path.home()))

        self.create_menu_bar()

        self.setWindowTitle("Data File Parser")
        self.setMinimumSize(QSize(700, 250))
        self.setMaximumSize(QSize(1200, 400))

        # Main container layout
        main_layout = QVBoxLayout()

        self.setWindowIcon(QIcon("src/radparse/static/android-chrome-512x512.png"))

        # Explanatory Label
        info_label = QLabel(
            "Select the Sample and / or Blank data files below, then run the parser."
        )
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)

        # File Input 1: Sample File
        sample_layout = QHBoxLayout()
        self.sample_input = QLineEdit()
        self.sample_input.setPlaceholderText("Select Sample File...")
        sample_btn = QPushButton("Browse")
        sample_btn.clicked.connect(lambda: self.browse_file(self.sample_input))
        clear_sample_btn = QPushButton("Clear")
        clear_sample_btn.clicked.connect(lambda: self.sample_input.clear())
        sample_layout.addWidget(QLabel("Sample Data:"))
        sample_layout.addWidget(self.sample_input)
        sample_layout.addWidget(sample_btn)
        sample_layout.addWidget(clear_sample_btn)

        main_layout.addLayout(sample_layout)

        # File Input 2: Blank File
        blank_layout = QHBoxLayout()
        self.blank_input = QLineEdit()
        self.blank_input.setPlaceholderText("Select Blank File...")
        blank_btn = QPushButton("Browse")
        blank_btn.clicked.connect(lambda: self.browse_file(self.blank_input))
        clear_blank_btn = QPushButton("Clear")
        clear_blank_btn.clicked.connect(lambda: self.blank_input.clear())
        blank_layout.addWidget(QLabel("Blank Data:"))
        blank_layout.addWidget(self.blank_input)
        blank_layout.addWidget(blank_btn)
        blank_layout.addWidget(clear_blank_btn)

        main_layout.addLayout(blank_layout)

        # Run Button
        run_btn = QPushButton("Run Parser")
        run_btn.setStyleSheet("font-weight: bold; padding: 6px;")  # Optional styling
        run_btn.clicked.connect(self.run_parsing)
        main_layout.addWidget(run_btn)

        # Status Label
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.status_label)

        # Set central widget
        central_widget = QWidget()
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

        # author label
        # author label
        author_label = QLabel("Made by 🦦 at Mustelidae Software")
        main_layout.addWidget(author_label, alignment=Qt.AlignmentFlag.AlignRight)

    def create_menu_bar(self):
        """Creates the window menu bar with settings options."""
        menu_bar = self.menuBar()

        # Settings Menu
        settings_menu = menu_bar.addMenu("&Settings")

        # Set Default Folder Action
        set_dir_action = QAction("Set Default Directory...", self)
        set_dir_action.setStatusTip("Select the default folder for file pickers")
        set_dir_action.triggered.connect(self.select_default_directory)
        settings_menu.addAction(set_dir_action)

    def select_default_directory(self):
        """Allows the user to pick a persistent default folder for browsing."""
        selected_dir = QFileDialog.getExistingDirectory(
            self, "Select Default Directory", self.default_dir
        )
        if selected_dir:
            self.default_dir = selected_dir
            self.settings.setValue("default_path", self.default_dir)
            self.status_label.setText(
                f"Default directory updated to:\n{self.default_dir}"
            )

    def browse_file(self, target_line_edit: QLineEdit):
        """Opens a native file dialog using self.default_dir as the starting path."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Data File",
            self.default_dir,
            "Data Files (*.txt);;All Files (*)",
        )
        if file_path:
            target_line_edit.setText(file_path)

    def run_parsing(self):
        """Placeholder function to trigger your data parsing loop."""
        sample_path = self.sample_input.text()
        blank_path = self.blank_input.text()

        if not sample_path:
            self.status_label.setText("Please select sample file path first.")
            return

        self.status_label.setText("Processing file(s)...")

        # conv to path objects
        sample_path = Path(sample_path)
        blank_path = Path(blank_path) if blank_path else None

        op_path, blank_provided = parse_and_write(
            sample_path=sample_path, blank_path=blank_path
        )

        self.status_label.setText(
            f"Parsing complete! :) \n Output saved to: {op_path} \n Baseline correction applied: {blank_provided}"
        )


def main_gui():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()


if __name__ == "__main__":
    main_gui()
