from PyQt5.QtWidgets import (QWidget, QMessageBox, QDialog, QVBoxLayout, 
                              QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                              QComboBox, QTableWidgetItem, QHeaderView, QInputDialog)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QIcon, QFont
import sys
import os

# Import UI và database
from ui.pages.user_management_ui import Ui_Form
from database.db_manager import db

class AddUserDialog(QDialog):
    """Dialog thêm/sửa người dùng"""
    def __init__(self, parent=None, user_data=None):
        super(AddUserDialog, self).__init__(parent)
        self.user_data = user_data  # None = thêm mới, có data = sửa
        self.setupUI()
        
        if user_data:
            self.setWindowTitle("✏️ Sửa người dùng")
            self.populate_fields()
        else:
            self.setWindowTitle("➕ Thêm người dùng mới")
    
    def setupUI(self):
        self.setFixedSize(450, 400)
        layout = QVBoxLayout(self)
        
        # Username
        layout.addWidget(QLabel("👤 Tên đăng nhập:"))
        self.username_edit = QLineEdit()
        layout.addWidget(self.username_edit)
        
        # Password (chỉ hiện khi thêm mới)
        if not self.user_data:
            layout.addWidget(QLabel("🔒 Mật khẩu:"))
            self.password_edit = QLineEdit()
            self.password_edit.setEchoMode(QLineEdit.Password)
            layout.addWidget(self.password_edit)
        
        # Full Name
        layout.addWidget(QLabel("👨‍💼 Họ tên đầy đủ:"))
        self.full_name_edit = QLineEdit()
        layout.addWidget(self.full_name_edit)
        
        # Phone Number
        layout.addWidget(QLabel("📱 Số điện thoại:"))
        self.phone_edit = QLineEdit()
        layout.addWidget(self.phone_edit)
        
        # Email
        layout.addWidget(QLabel("📧 Email:"))
        self.email_edit = QLineEdit()
        layout.addWidget(self.email_edit)
        
        # Role
        layout.addWidget(QLabel("🎭 Vai trò:"))
        self.role_combo = QComboBox()
        self.role_combo.addItems(["ANALYST", "ADMIN"])
        layout.addWidget(self.role_combo)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("💾 Lưu")
        self.save_btn.clicked.connect(self.save_user)
        
        self.cancel_btn = QPushButton("❌ Hủy")
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)
    
    def populate_fields(self):
        """Fill fields khi sửa user"""
        if self.user_data:
            self.username_edit.setText(self.user_data.get('username', ''))
            self.full_name_edit.setText(self.user_data.get('full_name', ''))
            self.phone_edit.setText(self.user_data.get('phone_number', ''))
            self.email_edit.setText(self.user_data.get('email', ''))
            role = self.user_data.get('role', 'ANALYST')
            index = self.role_combo.findText(role)
            if index >= 0:
                self.role_combo.setCurrentIndex(index)
    
    def save_user(self):
        username = self.username_edit.text().strip()
        full_name = self.full_name_edit.text().strip()
        phone_number = self.phone_edit.text().strip()
        email = self.email_edit.text().strip()
        role = self.role_combo.currentText()
        
        # Validation
        if not username:
            QMessageBox.warning(self, "Lỗi", "Tên đăng nhập không được rỗng!")
            return
        
        # Nếu không có full_name, dùng username
        if not full_name:
            full_name = username
        
        try:
            if not db.connection:
                if not db.connect():
                    QMessageBox.critical(self, "Lỗi", "Không thể kết nối database!")
                    return
            
            if self.user_data:  # Sửa user
                # Cập nhật thông tin user (không có update full_name và phone trong hàm update_user cũ)
                # Cần sửa hàm update_user hoặc dùng query trực tiếp
                query = """
                    UPDATE Users 
                    SET username=?, full_name=?, phone_number=?, email=?, role=? 
                    WHERE user_id=?
                """
                cursor = db.execute_query(query, (username, full_name, phone_number, email, role, self.user_data['user_id']))
                success = cursor is not None
                message = "Cập nhật user thành công!" if success else "Có lỗi khi cập nhật user!"
            else:  # Thêm user mới
                password = self.password_edit.text().strip()
                if not password:
                    QMessageBox.warning(self, "Lỗi", "Mật khẩu không được rỗng!")
                    return
                
                success = db.create_user(username, password, email, role, full_name, phone_number)
                message = "Tạo user thành công!" if success else "Có lỗi khi tạo user!"
            
            if success:
                QMessageBox.information(self, "Thành công", message)
                self.accept()
            else:
                QMessageBox.warning(self, "Lỗi", message)
                
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Có lỗi xảy ra: {str(e)}")

class UserManagement(QWidget):
    def __init__(self):
        super(UserManagement, self).__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        
        # Get current user info
        self.current_user = self.get_current_user()
        
        # Connect database
        self.connect_database()
        
        # Setup UI
        self.setup_table()
        self.connect_signals()
        
        # Check permissions
        self.check_permissions()
        
        # Load data
        self.load_users()
        
        # Setup search timer (để tránh search liên tục khi typing)
        self.search_timer = QTimer()
        self.search_timer.timeout.connect(self.filter_users)
        self.search_timer.setSingleShot(True)
    
    def get_current_user(self):
        """Lấy thông tin user hiện tại từ main window"""
        try:
            # Tìm main window
            from PyQt5.QtWidgets import QApplication
            app = QApplication.instance()
            
            # Tìm login window để lấy logged_in_user
            for widget in app.allWidgets():
                if hasattr(widget, 'logged_in_user') and widget.logged_in_user:
                    return widget.logged_in_user
                    
            # Fallback: assume admin for now
            return {'role': 'ADMIN', 'username': 'admin'}
        except:
            # Default to admin for safety
            return {'role': 'ADMIN', 'username': 'admin'}
    
    def check_permissions(self):
        """Kiểm tra quyền truy cập User Management"""
        if not self.current_user or self.current_user.get('role') != 'ADMIN':
            # Disable tất cả chức năng nếu không phải admin
            if hasattr(self.ui, 'addUserBtn'):
                self.ui.addUserBtn.setEnabled(False)
                self.ui.addUserBtn.setToolTip("Chỉ Admin mới có quyền thêm người dùng")
            
            if hasattr(self.ui, 'editUserBtn'):
                self.ui.editUserBtn.setEnabled(False)
                self.ui.editUserBtn.setToolTip("Chỉ Admin mới có quyền sửa thông tin người dùng")
            
            if hasattr(self.ui, 'deleteUserBtn'):
                self.ui.deleteUserBtn.setEnabled(False)
                self.ui.deleteUserBtn.setToolTip("Chỉ Admin mới có quyền xóa người dùng")
            
            if hasattr(self.ui, 'toggleStatusBtn'):
                self.ui.toggleStatusBtn.setEnabled(False)
                self.ui.toggleStatusBtn.setToolTip("Chỉ Admin mới có quyền thay đổi trạng thái người dùng")
            
        else:
            self.update_status("✅ Admin có đầy đủ quyền quản lý người dùng")
            return True
    
    def connect_database(self):
        """Kết nối database"""
        try:
            if not db.connection:
                if not db.connect():
                    QMessageBox.critical(self, "Lỗi Database", "Không thể kết nối database!")
                    return False
            return True
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Lỗi kết nối database: {str(e)}")
            return False
    
    def setup_table(self):
        """Thiết lập bảng users"""
        # Chỉ hiển thị khi có UI elements (tránh lỗi khi UI chưa có table)
        if hasattr(self.ui, 'usersTable'):
            # Ẩn cột ID 
            self.ui.usersTable.setColumnHidden(0, True)
            
            # Set column widths
            header = self.ui.usersTable.horizontalHeader()
            header.setStretchLastSection(True)
            
            # Set selection behavior
            self.ui.usersTable.setSelectionBehavior(self.ui.usersTable.SelectRows)
    
    def connect_signals(self):
        """Kết nối signals với slots"""
        # Nếu UI chưa có các elements, tạm thời skip
        if hasattr(self.ui, 'addUserBtn'):
            self.ui.addUserBtn.clicked.connect(self.add_user)
        
        if hasattr(self.ui, 'editUserBtn'):
            self.ui.editUserBtn.clicked.connect(self.edit_user)
        
        if hasattr(self.ui, 'deleteUserBtn'):
            self.ui.deleteUserBtn.clicked.connect(self.delete_user)
        
        if hasattr(self.ui, 'toggleStatusBtn'):
            self.ui.toggleStatusBtn.clicked.connect(self.toggle_user_status)
        
        if hasattr(self.ui, 'refreshBtn'):
            self.ui.refreshBtn.clicked.connect(self.load_users)
        
        if hasattr(self.ui, 'searchEdit'):
            self.ui.searchEdit.textChanged.connect(self.on_search_changed)
        
        if hasattr(self.ui, 'usersTable'):
            self.ui.usersTable.itemSelectionChanged.connect(self.on_selection_changed)
    
    def load_users(self):
        """Load danh sách users từ database"""
        try:
            if not self.connect_database():
                return
            
            users = db.get_users()
            self.populate_table(users)
            self.update_statistics(users)
            self.update_status("Đã tải danh sách người dùng")
            
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể tải danh sách users: {str(e)}")
    
    def populate_table(self, users):
        """Fill data vào table"""
        if not hasattr(self.ui, 'usersTable'):
            return
            
        self.ui.usersTable.setRowCount(len(users))
        
        for row, user in enumerate(users):
            # ID (ẩn)
            self.ui.usersTable.setItem(row, 0, QTableWidgetItem(str(user['user_id'])))
            
            # Username (hiển thị full_name nếu có)
            display_name = user.get('full_name', '') or user['username']
            self.ui.usersTable.setItem(row, 1, QTableWidgetItem(f"{display_name} ({user['username']})"))
            
            # Email
            email = user.get('email', '') or 'N/A'
            self.ui.usersTable.setItem(row, 2, QTableWidgetItem(email))
            
            # Role
            role = user['role']
            role_icon = "👑" if role == "ADMIN" else "🔍"
            self.ui.usersTable.setItem(row, 3, QTableWidgetItem(f"{role_icon} {role}"))
            
            # Created date
            created_at = user.get('created_at', '')
            if created_at:
                # Format ngày đẹp hơn
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    formatted_date = dt.strftime("%d/%m/%Y")
                except:
                    formatted_date = created_at[:10] if len(created_at) >= 10 else "N/A"
            else:
                formatted_date = "N/A"
            self.ui.usersTable.setItem(row, 4, QTableWidgetItem(formatted_date))
            
            # Status
            status = "🟢 Hoạt động" if user['is_active'] else "🔴 Không hoạt động"
            self.ui.usersTable.setItem(row, 5, QTableWidgetItem(status))
    
    def update_statistics(self, users):
        """Cập nhật thống kê"""
        total = len(users)
        active = len([u for u in users if u['is_active']])
        inactive = total - active
        admin = len([u for u in users if u['role'] == 'ADMIN'])
        analyst = len([u for u in users if u['role'] == 'ANALYST'])
        
        if hasattr(self.ui, 'statsLabel'):
            self.ui.statsLabel.setText(f"📊 Tổng: {total} users")
        
        if hasattr(self.ui, 'activeUsersLabel'):
            self.ui.activeUsersLabel.setText(f"🟢 Hoạt động: {active}")
        
        if hasattr(self.ui, 'inactiveUsersLabel'):
            self.ui.inactiveUsersLabel.setText(f"🔴 Không hoạt động: {inactive}")
        
        if hasattr(self.ui, 'adminUsersLabel'):
            self.ui.adminUsersLabel.setText(f"👑 Admin: {admin}")
        
        if hasattr(self.ui, 'analystUsersLabel'):
            self.ui.analystUsersLabel.setText(f"🔍 Analyst: {analyst}")
    
    def update_status(self, message):
        """Cập nhật status bar"""
        if hasattr(self.ui, 'statusLabel'):
            self.ui.statusLabel.setText(message)
    
    def on_selection_changed(self):
        """Xử lý khi selection thay đổi"""
        if not hasattr(self.ui, 'usersTable'):
            return
            
        has_selection = len(self.ui.usersTable.selectedItems()) > 0
        is_admin = self.current_user and self.current_user.get('role') == 'ADMIN'
        
        # Chỉ enable buttons nếu có selection và là admin
        if hasattr(self.ui, 'editUserBtn'):
            self.ui.editUserBtn.setEnabled(has_selection and is_admin)
        
        if hasattr(self.ui, 'deleteUserBtn'):
            self.ui.deleteUserBtn.setEnabled(has_selection and is_admin)
        
        if hasattr(self.ui, 'toggleStatusBtn'):
            self.ui.toggleStatusBtn.setEnabled(has_selection and is_admin)
    
    def get_selected_user(self):
        """Lấy user được chọn"""
        if not hasattr(self.ui, 'usersTable'):
            return None
            
        selected_rows = set()
        for item in self.ui.usersTable.selectedItems():
            selected_rows.add(item.row())
        
        if not selected_rows:
            return None
        
        row = list(selected_rows)[0]
        user_id = int(self.ui.usersTable.item(row, 0).text())
        
        # Lấy thông tin đầy đủ từ database thay vì từ table
        try:
            if not self.connect_database():
                return None
            
            user = db.fetch_one("SELECT user_id, username, full_name, phone_number, email, role FROM Users WHERE user_id = ?", (user_id,))
            return user
        except Exception as e:
            print(f"Error getting user info: {e}")
            return None
    
    def add_user(self):
        """Thêm user mới"""
        dialog = AddUserDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.load_users()
    
    def edit_user(self):
        """Sửa user"""
        user = self.get_selected_user()
        if not user:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn user để sửa!")
            return
        
        dialog = AddUserDialog(self, user)
        if dialog.exec_() == QDialog.Accepted:
            self.load_users()
    
    def delete_user(self):
        """Xóa vĩnh viễn user khỏi hệ thống"""
        user = self.get_selected_user()
        if not user:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn user để xóa!")
            return
        
        # Kiểm tra quyền admin
        if not self.current_user or self.current_user.get('role') != 'ADMIN':
            QMessageBox.warning(self, "🔒 Quyền truy cập", "Chỉ Admin mới có quyền xóa người dùng!")
            return
        
        # Không cho phép xóa chính mình
        if user['username'] == self.current_user.get('username'):
            QMessageBox.warning(
                self, 
                "❌ Không thể xóa", 
                "Bạn không thể xóa chính tài khoản của mình!\n\n"
                "Vui lòng sử dụng tài khoản admin khác để thực hiện thao tác này."
            )
            return
        
        # Kiểm tra nếu user đang hoạt động - gợi ý dùng toggle status
        if user.get('is_active', True):
            QMessageBox.information(
                self,
                "💡 Gợi ý",
                f"User '{user['username']}' đang ở trạng thái hoạt động.\n\n"
                f"💡 GỢI Ý: Nếu bạn chỉ muốn ngăn user đăng nhập,\n"
                f"hãy sử dụng nút '🔄 Đổi trạng thái' thay vì xóa vĩnh viễn.\n\n"
                f"🗑️ Nút 'Xóa' sẽ XÓA VĨNH VIỄN user khỏi hệ thống."
            )
        
        # Hiển thị dialog xác nhận xóa vĩnh viễn
        delete_dialog = DeleteTypeDialog(self, user)
        
        if delete_dialog.exec_() == QDialog.Accepted:
            if delete_dialog.is_confirmed():
                self.perform_hard_delete(user)
            else:
                QMessageBox.information(self, "Thông báo", "Bạn đã hủy xóa vĩnh viễn user.")
    
    def perform_hard_delete(self, user):
        """Thực hiện hard delete với kiểm tra bổ sung"""
        try:
            if not self.connect_database():
                return
            
            # Kiểm tra dữ liệu sẽ bị mất
            activity_count = db.fetch_one("SELECT COUNT(*) as count FROM Activity_Logs WHERE user_id = ?", (user['user_id'],))
            case_count = db.fetch_one("SELECT COUNT(*) as count FROM Case_Assignees WHERE user_id = ?", (user['user_id'],))
            
            # Ngăn chặn xóa nếu đang có case assignments
            if case_count and case_count['count'] > 0:
                QMessageBox.critical(
                    self,
                    "❌ Không thể xóa vĩnh viễn",
                    f"User '{user['username']}' đang được gán vào {case_count['count']} case(s)!\n\n"
                    f"🔧 Vui lòng:\n"
                    f"1. Remove user khỏi tất cả cases trước\n"
                    f"2. Hoặc chọn '🔄 Đổi trạng thái' để vô hiệu hóa thay vì xóa vĩnh viễn"
                )
                return
            
            # Thực hiện hard delete
            success = db.hard_delete_user(user['user_id'])
            
            if success:
                # Thông báo thành công với thống kê
                success_msg = f"💀 Đã XÓA VĨNH VIỄN user '{user['username']}'!\n\n"
                success_msg += f"🗑️ User đã bị xóa hoàn toàn khỏi hệ thống.\n"
                
                if activity_count and activity_count['count'] > 0:
                    success_msg += f"📝 {activity_count['count']} activity logs đã bị xóa vĩnh viễn.\n"
                else:
                    success_msg += f"📝 Không có activity logs nào bị mất.\n"
                    
                success_msg += f"\n⚠️ Thao tác đã hoàn tất và không thể hoàn tác."
                
                QMessageBox.information(self, "💀 Xóa vĩnh viễn thành công", success_msg)
                self.load_users()  # Refresh table
            else:
                QMessageBox.critical(
                    self, 
                    "❌ Hard delete thất bại", 
                    f"Có lỗi nghiêm trọng khi xóa vĩnh viễn user '{user['username']}'!\n\n"
                    f"🔍 Nguyên nhân có thể:\n"
                    f"• User là admin cuối cùng trong hệ thống\n"
                    f"• Có ràng buộc dữ liệu chưa được xử lý\n"
                    f"• Lỗi kết nối database"
                )
                
        except Exception as e:
            QMessageBox.critical(
                self, 
                "❌ Lỗi nghiêm trọng", 
                f"Có lỗi nghiêm trọng khi xóa vĩnh viễn user:\n{str(e)}\n\n"
                f"🛡️ Hệ thống đã dừng thao tác để bảo vệ dữ liệu."
            )
    
    def toggle_user_status(self):
        """Đổi trạng thái user"""
        user = self.get_selected_user()
        if not user:
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn user để thay đổi trạng thái!")
            return
        
        try:
            if not self.connect_database():
                return
            
            # Get current status từ database
            db_user = db.fetch_one("SELECT is_active FROM Users WHERE user_id = ?", (user['user_id'],))
            if not db_user:
                QMessageBox.warning(self, "Lỗi", "Không tìm thấy user trong database!")
                return
            
            new_status = not db_user['is_active']
            success = db.update_user(user['user_id'], is_active=new_status)
            
            if success:
                status_text = "kích hoạt" if new_status else "vô hiệu hóa"
                QMessageBox.information(self, "Thành công", f"Đã {status_text} user '{user['username']}'")
                self.load_users()
            else:
                QMessageBox.warning(self, "Lỗi", "Có lỗi khi cập nhật trạng thái user!")
                
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Có lỗi xảy ra: {str(e)}")
    
    def on_search_changed(self):
        """Xử lý khi search text thay đổi"""
        self.search_timer.stop()
        self.search_timer.start(500)  # Delay 500ms
    
    def filter_users(self):
        """Lọc users theo search term"""
        if not hasattr(self.ui, 'searchEdit') or not hasattr(self.ui, 'usersTable'):
            return
        
        search_text = self.ui.searchEdit.text().lower()
        
        for row in range(self.ui.usersTable.rowCount()):
            show_row = False
            
            # Tìm trong username (cột 1) và email (cột 2)
            for col in [1, 2]:  # Username/Full_name và Email columns
                item = self.ui.usersTable.item(row, col)
                if item and search_text in item.text().lower():
                    show_row = True
                    break
            
            self.ui.usersTable.setRowHidden(row, not show_row)

class DeleteTypeDialog(QDialog):
    """Dialog xác nhận xóa vĩnh viễn người dùng"""
    
    def __init__(self, parent=None, user_info=None):
        super(DeleteTypeDialog, self).__init__(parent)
        self.user_info = user_info or {}
        self.confirmed = False
        
        self.setWindowTitle("💀 Xác nhận xóa vĩnh viễn")
        self.setFixedSize(500, 450)
        self.setModal(True)
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Header
        header_label = QLabel("💀 XÁC NHẬN XÓA VĨNH VIỄN")
        header_label.setAlignment(Qt.AlignCenter)
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet("color: #dc3545; margin: 10px;")
        layout.addWidget(header_label)
        
        # User info
        info_label = QLabel(f"""
📋 Thông tin người dùng sẽ bị XÓA VĨNH VIỄN:
👤 Username: {self.user_info.get('username', 'N/A')}
👨‍💼 Họ tên: {self.user_info.get('full_name', 'N/A')}
🎭 Role: {self.user_info.get('role', 'N/A')}
📧 Email: {self.user_info.get('email', 'N/A')}
        """)
        info_label.setStyleSheet("""
            background-color: #f8d7da;
            border: 2px solid #dc3545;
            border-radius: 8px;
            padding: 15px;
            margin: 10px;
            font-weight: bold;
        """)
        layout.addWidget(info_label)
        
        # Warning box
        warning_label = QLabel("""
🚨 CẢNH BÁO NGHIÊM TRỌNG:

💀 NHỮNG GÌ SẼ BỊ MẤT VĨNH VIỄN:
• Toàn bộ thông tin user
• Mọi dữ liệu liên quan

⚠️ THAO TÁC NÀY KHÔNG THỂ HOÀN TÁC!

💡 GỢI Ý: Nếu bạn chỉ muốn ngăn user đăng nhập,
   hãy sử dụng nút "🔄 Đổi trạng thái" thay vì xóa.
        """)
        warning_label.setStyleSheet("""
            background-color: #fff3cd;
            border: 2px solid #ffc107;
            border-radius: 8px;
            padding: 15px;
            margin: 10px;
            font-size: 11px;
            line-height: 1.4;
        """)
        layout.addWidget(warning_label)
        
        # Confirmation checkbox or text input
        confirm_label = QLabel("🔐 XÁC NHẬN XÓA VĨNH VIỄN:")
        confirm_label.setStyleSheet("font-weight: bold; margin: 10px 0 5px 0;")
        layout.addWidget(confirm_label)
        
        instruction_label = QLabel(f"Nhập chính xác '{self.user_info.get('username', '')}' để xác nhận:")
        instruction_label.setStyleSheet("margin: 0 0 5px 10px;")
        layout.addWidget(instruction_label)
        
        self.confirm_input = QLineEdit()
        self.confirm_input.setPlaceholderText(f"Nhập '{self.user_info.get('username', '')}' ở đây...")
        self.confirm_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #dc3545;
                border-radius: 6px;
                padding: 8px;
                font-size: 12px;
                margin: 5px 10px;
            }
            QLineEdit:focus {
                border-color: #a71e2a;
                background-color: #fff5f5;
            }
        """)
        self.confirm_input.textChanged.connect(self.check_confirmation)
        layout.addWidget(self.confirm_input)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # Cancel button
        cancel_btn = QPushButton("❌ Hủy")
        cancel_btn.setMinimumHeight(45)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #545b62;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        # Delete button
        self.delete_btn = QPushButton("💀 XÓA VĨNH VIỄN")
        self.delete_btn.setMinimumHeight(45)
        self.delete_btn.setEnabled(False)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover:enabled {
                background-color: #c82333;
            }
            QPushButton:disabled {
                background-color: #6c757d;
                color: #adb5bd;
            }
        """)
        self.delete_btn.clicked.connect(self.confirm_delete)
        button_layout.addWidget(self.delete_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    
    def check_confirmation(self):
        """Kiểm tra xác nhận username"""
        entered_text = self.confirm_input.text().strip()
        expected_username = self.user_info.get('username', '')
        
        if entered_text == expected_username:
            self.delete_btn.setEnabled(True)
            self.confirm_input.setStyleSheet("""
                QLineEdit {
                    border: 2px solid #28a745;
                    border-radius: 6px;
                    padding: 8px;
                    font-size: 12px;
                    margin: 5px 10px;
                    background-color: #f8fff8;
                }
            """)
        else:
            self.delete_btn.setEnabled(False)
            self.confirm_input.setStyleSheet("""
                QLineEdit {
                    border: 2px solid #dc3545;
                    border-radius: 6px;
                    padding: 8px;
                    font-size: 12px;
                    margin: 5px 10px;
                }
                QLineEdit:focus {
                    border-color: #a71e2a;
                    background-color: #fff5f5;
                }
            """)
    
    def confirm_delete(self):
        """Xác nhận cuối cùng trước khi xóa"""
        final_warning = QMessageBox.critical(
            self,
            "💀 XÁC NHẬN CUỐI CÙNG",
            f"🚨 CẢNH BÁO CUỐI CÙNG!\n\n"
            f"Bạn THỰC SỰ muốn XÓA VĨNH VIỄN user '{self.user_info.get('username', '')}'?\n\n"
            f"💀 User sẽ bị xóa hoàn toàn khỏi database\n"
            f"⚠️ KHÔNG THỂ HOÀN TÁC!\n\n"
            f"Nhấn 'Yes' để XÓA VĨNH VIỄN ngay lập tức.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if final_warning == QMessageBox.Yes:
            self.confirmed = True
            self.accept()
    
    def is_confirmed(self):
        """Trả về True nếu user đã xác nhận xóa"""
        return self.confirmed