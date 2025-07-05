# -*- coding: utf-8 -*-

from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_LoginWindow(object):
    def setupUi(self, LoginWindow):
        LoginWindow.setObjectName("LoginWindow")
        LoginWindow.resize(550, 750)
        LoginWindow.setMinimumSize(QtCore.QSize(550, 750))
        LoginWindow.setMaximumSize(QtCore.QSize(550, 750))
        LoginWindow.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #2E86AB, stop:1 #A23B72);
            }
            QWidget#centralwidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #2E86AB, stop:1 #A23B72);
            }
        """)
        
        self.centralwidget = QtWidgets.QWidget(LoginWindow)
        self.centralwidget.setObjectName("centralwidget")
        
        # Main layout
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setContentsMargins(50, 40, 50, 40)
        self.verticalLayout.setSpacing(30)
        self.verticalLayout.setObjectName("verticalLayout")
        
        # Logo/Title area
        self.logo_frame = QtWidgets.QFrame(self.centralwidget)
        self.logo_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 15px;
                border: 2px solid rgba(255, 255, 255, 0.2);
            }
        """)
        self.logo_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.logo_frame.setObjectName("logo_frame")
        
        self.logo_layout = QtWidgets.QVBoxLayout(self.logo_frame)
        self.logo_layout.setContentsMargins(20, 20, 20, 20)
        
        # App title
        self.title_label = QtWidgets.QLabel(self.logo_frame)
        self.title_label.setAlignment(QtCore.Qt.AlignCenter)
        self.title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 22px;
                font-weight: bold;
                background: transparent;
                border: none;
                padding: 10px;
            }
        """)
        self.title_label.setObjectName("title_label")
        self.logo_layout.addWidget(self.title_label)
        
        # Subtitle
        self.subtitle_label = QtWidgets.QLabel(self.logo_frame)
        self.subtitle_label.setAlignment(QtCore.Qt.AlignCenter)
        self.subtitle_label.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.8);
                font-size: 16px;
                background: transparent;
                border: none;
                padding: 5px;
            }
        """)
        self.subtitle_label.setObjectName("subtitle_label")
        self.logo_layout.addWidget(self.subtitle_label)
        
        self.verticalLayout.addWidget(self.logo_frame)
        
        # Login form
        self.login_frame = QtWidgets.QFrame(self.centralwidget)
        self.login_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.95);
                border-radius: 15px;
                border: 2px solid rgba(255, 255, 255, 0.3);
            }
        """)
        self.login_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.login_frame.setObjectName("login_frame")
        
        self.form_layout = QtWidgets.QVBoxLayout(self.login_frame)
        self.form_layout.setContentsMargins(40, 35, 40, 35)
        self.form_layout.setSpacing(18)
        
        # Username field
        self.username_label = QtWidgets.QLabel(self.login_frame)
        self.username_label.setStyleSheet("""
            QLabel {
                color: #333;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        self.username_label.setObjectName("username_label")
        self.form_layout.addWidget(self.username_label)
        
        self.username_input = QtWidgets.QLineEdit(self.login_frame)
        self.username_input.setPlaceholderText("Nhập tên đăng nhập")
        self.username_input.setStyleSheet("""
            QLineEdit {
                padding: 15px;
                border: 2px solid #ddd;
                border-radius: 8px;
                font-size: 16px;
                background-color: white;
                min-height: 20px;
            }
            QLineEdit:focus {
                border-color: #2E86AB;
            }
            QLineEdit::placeholder {
                color: #999;
                font-style: italic;
            }
        """)
        self.username_input.setObjectName("username_input")
        self.form_layout.addWidget(self.username_input)
        
        # Password field
        self.password_label = QtWidgets.QLabel(self.login_frame)
        self.password_label.setStyleSheet("""
            QLabel {
                color: #333;
                font-size: 14px;
                font-weight: bold;
            }
        """)
        self.password_label.setObjectName("password_label")
        self.form_layout.addWidget(self.password_label)
        
        # Password input with horizontal layout
        self.password_container = QtWidgets.QFrame(self.login_frame)
        self.password_container.setStyleSheet("QFrame { border: none; background: transparent; }")
        self.password_layout = QtWidgets.QHBoxLayout(self.password_container)
        self.password_layout.setContentsMargins(0, 0, 0, 0)
        self.password_layout.setSpacing(0)
        
        self.password_input = QtWidgets.QLineEdit(self.password_container)
        self.password_input.setPlaceholderText("Nhập mật khẩu")
        self.password_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.password_input.setStyleSheet("""
            QLineEdit {
                padding: 15px;
                border: 2px solid #ddd;
                border-radius: 8px;
                font-size: 16px;
                background-color: white;
                min-height: 20px;
            }
            QLineEdit:focus {
                border-color: #2E86AB;
            }
            QLineEdit::placeholder {
                color: #999;
                font-style: italic;
            }
        """)
        self.password_input.setObjectName("password_input")
        self.password_layout.addWidget(self.password_input)
        
        # Show/Hide password button
        self.show_password_btn = QtWidgets.QPushButton(self.password_container)
        self.show_password_btn.setText("🔒")
        self.show_password_btn.setFixedSize(45, 54)
        self.show_password_btn.setStyleSheet("""
            QPushButton {
                border: 2px solid #ddd;
                border-left: none;
                border-radius: 0px 8px 8px 0px;
                background-color: #f8f9fa;
                font-size: 14px;
                color: #666;
                margin-left: -2px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                color: #2E86AB;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
            }
        """)
        self.show_password_btn.setObjectName("show_password_btn")
        self.password_layout.addWidget(self.show_password_btn)
        
        self.form_layout.addWidget(self.password_container)
        
        # Forgot password link centered
        self.forgot_password_container = QtWidgets.QFrame(self.login_frame)
        self.forgot_password_container.setStyleSheet("QFrame { background: transparent; border: none; }")
        self.forgot_layout = QtWidgets.QHBoxLayout(self.forgot_password_container)
        self.forgot_layout.setContentsMargins(0, 15, 0, 15)
        
        # Left spacer
        left_spacer = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.forgot_layout.addItem(left_spacer)
        
        # Forgot password link
        self.forgot_password_label = QtWidgets.QLabel(self.forgot_password_container)
        self.forgot_password_label.setStyleSheet("""
            QLabel {
                color: #2E86AB;
                font-size: 15px;
                font-weight: 600;
                text-decoration: underline;
                background: transparent;
                border: none;
                padding: 10px;
                min-height: 25px;
            }
            QLabel:hover {
                color: #1E5F7A;
                font-weight: bold;
            }
        """)
        self.forgot_password_label.setObjectName("forgot_password_label")
        self.forgot_layout.addWidget(self.forgot_password_label)
        
        # Right spacer
        right_spacer = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.forgot_layout.addItem(right_spacer)
        
        self.form_layout.addWidget(self.forgot_password_container)
        
        # Login button
        self.login_button = QtWidgets.QPushButton(self.login_frame)
        self.login_button.setStyleSheet("""
            QPushButton {
                padding: 18px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #2E86AB, stop:1 #A23B72);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 18px;
                font-weight: bold;
                min-height: 25px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #1E5F7A, stop:1 #7A2B52);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #1A4D63, stop:1 #5A1E3A);
            }
        """)
        self.login_button.setObjectName("login_button")
        self.form_layout.addWidget(self.login_button)
        
        # Error message label
        self.error_label = QtWidgets.QLabel(self.login_frame)
        self.error_label.setAlignment(QtCore.Qt.AlignCenter)
        self.error_label.setStyleSheet("""
            QLabel {
                color: #e74c3c;
                font-size: 14px;
                background: transparent;
                border: none;
                padding: 10px;
                font-weight: bold;
            }
        """)
        self.error_label.setWordWrap(True)  # Enable word wrap
        self.error_label.setObjectName("error_label")
        self.error_label.hide()  # Initially hidden
        self.form_layout.addWidget(self.error_label)
        
        self.verticalLayout.addWidget(self.login_frame)
        
        # Spacer
        spacerItem = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem)
        
        LoginWindow.setCentralWidget(self.centralwidget)
        
        self.retranslateUi(LoginWindow)
        QtCore.QMetaObject.connectSlotsByName(LoginWindow)

    def retranslateUi(self, LoginWindow):
        _translate = QtCore.QCoreApplication.translate
        LoginWindow.setWindowTitle(_translate("LoginWindow", "Hệ thống điều tra Windows - Đăng nhập"))
        self.title_label.setText(_translate("LoginWindow", "🔒 HỆ THỐNG ĐIỀU TRA MÁY TÍNH"))
        self.subtitle_label.setText(_translate("LoginWindow", "Nền tảng điều tra số"))
        self.username_label.setText(_translate("LoginWindow", "TÊN ĐĂNG NHẬP:"))
        self.password_label.setText(_translate("LoginWindow", "MẬT KHẨU:"))
        self.forgot_password_label.setText(_translate("LoginWindow", "Quên mật khẩu?"))
        self.login_button.setText(_translate("LoginWindow", "ĐĂNG NHẬP"))
        self.error_label.setText(_translate("LoginWindow", "")) 