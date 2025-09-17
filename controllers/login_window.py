from tkinter import N, SEL_FIRST
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QIcon, QFont
import hashlib
import sys

from views.login_ui import Ui_LoginWindow
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.db_manager import DatabaseManager


class LoginWindow(QMainWindow):
    # Signal to notify successful login
    login_successful = pyqtSignal()

    def __init__(self):
        super(LoginWindow, self).__init__()
        self.ui = Ui_LoginWindow()
        self.ui.setupUi(self)

        # Flag to track successful login
        self.login_success = False

        self.logged_in_user = None

        # Set window properties
        self.setWindowTitle("Windows Forensic System - Login")
        self.setWindowFlags(Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint)
        
        # Center window on screen
        self.center_window()
        
        # Connect signals
        self.ui.login_button.clicked.connect(self.handle_login)
        self.ui.password_input.returnPressed.connect(self.handle_login)
        self.ui.username_input.returnPressed.connect(lambda: self.ui.password_input.setFocus())
        self.ui.forgot_password_label.mousePressEvent = self.show_forgot_password_dialog
        self.ui.show_password_btn.clicked.connect(self.toggle_password_visibility)
        
        # Track password visibility state
        self.password_visible = False
        
        # Set focus to username input
        self.ui.username_input.setFocus()
        
        # Predefined users (in practice should be stored in database)
        '''self.users = {
            "admin": self.hash_password("admin123"),
            "forensic": self.hash_password("forensic123"),
            "investigator": self.hash_password("investigate123"),
            "user": self.hash_password("user123")
        }'''

        self.db = DatabaseManager()
        if not self.db.connect():
            self.show_error("Cannot connect to database!")
            return

    def center_window(self):
        """Center window on screen"""
        screen = QApplication.desktop().screenGeometry()
        window = self.geometry()
        x = (screen.width() - window.width()) // 2
        y = (screen.height() - window.height()) // 2
        self.move(x, y)
    
    '''def hash_password(self, password):
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()'''

    def handle_login(self):
        """Handle login"""
        username = self.ui.username_input.text().strip()
        password = self.ui.password_input.text()

        # Reset error message
        self.ui.error_label.hide()

        # Validate input
        if not username or not password:
            self.show_error("Please enter both username and password!")
            return

        # Check credentials
        user = self.authenticate(username, password)
        if user:
            self.login_success = True  # Mark successful login
            self.logged_in_user = user # Store logged in user information
            self.login_successful.emit()
            self.close()
        else:
            self.show_error("Incorrect username or password!")
            self.ui.password_input.clear()
            self.ui.password_input.setFocus()

    def authenticate(self, username, password):
        try:
            user = self.db.authenticate_user(username, password)
            return user
        except Exception as e:
            print(f"Authentication error: {e}")
            return None
    def get_logged_in_user(self):
        return self.logged_in_user
    
    def show_error(self, message):
        self.ui.error_label.setText(message)
        self.ui.error_label.show()
    
    def toggle_password_visibility(self):
        """Toggle password visibility"""
        from PyQt5.QtWidgets import QLineEdit

        if self.password_visible:
            # Hide password
            self.ui.password_input.setEchoMode(QLineEdit.Password)
            self.ui.show_password_btn.setText("🔒")
            self.password_visible = False
        else:
            # Show password
            self.ui.password_input.setEchoMode(QLineEdit.Normal)
            self.ui.show_password_btn.setText("🔓")
            self.password_visible = True

    def show_forgot_password_dialog(self, event):
        """Show forgot password dialog"""
        from PyQt5.QtWidgets import QMessageBox

        QMessageBox.information(
            self,
            "🔒 Password Recovery",
            "To recover your password, please contact the system administrator:\n\n"
            "📞 Phone: 0357857581\n\n"
            "The administrator will help you recover your account safely and quickly.\n\n"
            "🕐 Support hours: 8:00 - 17:00 (Monday - Friday)"
        )
    
    def closeEvent(self, event):
        """Override close event to exit application when login window is closed"""
        # Only exit when user actually closes window (not successful login)
        if not self.login_success:
            if hasattr(self, 'db') and self.db:
                self.db.disconnect()
            sys.exit(0)
        else:
            event.accept()  # Allow closing window on successful login 