"""
Script khởi tạo database cho Windows Forensic System
"""
import os
import sys
import shutil

# Import db_manager từ cùng thư mục
from db_manager import db

def initialize_database():
    print("=== Khởi tạo database Windows Forensic System ===\n")
    
    # Đường dẫn database trong cùng thư mục
    db_path = os.path.join(os.path.dirname(__file__), "forensic_system.db")
    
    # Kiểm tra nếu database đã tồn tại
    if os.path.exists(db_path):
        print(f"Database đã tồn tại tại: {os.path.abspath(db_path)}")
        confirm = input("Bạn có muốn xóa và tạo lại không? (y/n): ")
        if confirm.lower() == 'y':
            try:
                os.remove(db_path)
                print("✓ Đã xóa database cũ")
            except Exception as e:
                print(f"Lỗi khi xóa database: {e}")
                return
        else:
            print("Đã hủy khởi tạo database.")
            return
    
    # Kết nối và khởi tạo database
    print("Đang kết nối database...")
    if db.connect():
        print("Kết nối thành công")
        print("Đang khởi tạo schema...")
        
        if db.initialize_database():
            print("Database đã được khởi tạo thành công!")
        else:
            print("Có lỗi khi khởi tạo database!")
        
        db.disconnect()
    else:
        print("Không thể kết nối database!")

if __name__ == "__main__":
    initialize_database() 