from tkinter import N, SEL_FIRST
from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtGui import QIcon, QFont
import hashlib
import sys

from ui.login_ui import Ui_LoginWindow
from database.db_manager import db


class LoginWindow(QMainWindow):
    # Signal để thông báo đăng nhập thành công
    login_successful = pyqtSignal()
    
    def __init__(self):
        super(LoginWindow, self).__init__()
        self.ui = Ui_LoginWindow()
        self.ui.setupUi(self)
        
        # Flag để track đăng nhập thành công
        self.login_success = False
        
        self.logged_in_user = None
        
        # Set window properties
        self.setWindowTitle("Windows Forensic System - Đăng nhập")
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
        
        # Predefined users (trong thực tế nên lưu trong database)
        '''self.users = {
            "admin": self.hash_password("admin123"),
            "forensic": self.hash_password("forensic123"),
            "investigator": self.hash_password("investigate123"),
            "user": self.hash_password("user123")
        }'''
        
        if not db.connect():
            self.show_error("Không thể kết nối đến cơ sở dữ liệu!")
            return
    
    def center_window(self):
        """Căn giữa cửa sổ trên màn hình"""
        screen = QApplication.desktop().screenGeometry()
        window = self.geometry()
        x = (screen.width() - window.width()) // 2
        y = (screen.height() - window.height()) // 2
        self.move(x, y)
    
    '''def hash_password(self, password):
        """Mã hóa mật khẩu bằng SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()'''
    
    def handle_login(self):
        """Xử lý đăng nhập"""
        username = self.ui.username_input.text().strip()
        password = self.ui.password_input.text()
        
        # Reset error message
        self.ui.error_label.hide()
        
        # Validate input
        if not username or not password:
            self.show_error("Vui lòng nhập đầy đủ tên đăng nhập và mật khẩu!")
            return
        
        # Check credentials
        user = self.authenticate(username, password)
        if user:
            self.login_success = True  # Đánh dấu đăng nhập thành công
            self.logged_in_user = user # Lưu thông tin người dùng đã đăng nhập
            self.login_successful.emit()
            self.close()
        else:
            self.show_error("Tên đăng nhập hoặc mật khẩu không chính xác!")
            self.ui.password_input.clear()
            self.ui.password_input.setFocus()
    
    def authenticate(self, username, password):
        try:
            user = db.authenticate_user(username, password)
            return user
        except Exception as e:
            print(f"Lỗi xác thực: {e}")
            return None
    def get_logged_in_user(self):
        return self.logged_in_user
    
    def show_error(self, message):
        self.ui.error_label.setText(message)
        self.ui.error_label.show()
    
    def toggle_password_visibility(self):
        """Toggle hiển thị/ẩn mật khẩu"""
        from PyQt5.QtWidgets import QLineEdit
        
        if self.password_visible:
            # Ẩn mật khẩu
            self.ui.password_input.setEchoMode(QLineEdit.Password)
            self.ui.show_password_btn.setText("🔒")
            self.password_visible = False
        else:
            # Hiển thị mật khẩu
            self.ui.password_input.setEchoMode(QLineEdit.Normal)
            self.ui.show_password_btn.setText("🔓")
            self.password_visible = True
    
    def show_forgot_password_dialog(self, event):
        """Hiển thị dialog quên mật khẩu"""
        from PyQt5.QtWidgets import QMessageBox
        
        QMessageBox.information(
            self,
            "🔒 Khôi phục mật khẩu",
            "Để khôi phục mật khẩu, vui lòng liên hệ với quản trị viên hệ thống:\n\n"
            "📞 Số điện thoại: 0357857581\n\n"
            "Quản trị viên sẽ hỗ trợ bạn khôi phục tài khoản một cách an toàn và nhanh chóng.\n\n"
            "🕐 Thời gian hỗ trợ: 8:00 - 17:00 (Thứ 2 - Thứ 6)"
        )
    
    def closeEvent(self, event):
        """Override close event để thoát ứng dụng nếu đóng login window"""
        # Chỉ exit khi người dùng thực sự đóng window (không phải đăng nhập thành công)
        if not self.login_success:
            db.disconnect()
            sys.exit(0)
        else:
            event.accept()  # Cho phép đóng window khi đăng nhập thành công 