"""
Mô-đun tiện ích để quản lý đường dẫn của dự án một cách động.
Điều này giúp ứng dụng hoạt động dù được đặt ở bất kỳ vị trí nào.
"""

import os


def get_project_root():
    """
    Lấy thư mục gốc của dự án (nơi chứa main.py).
    
    Trả về:
        str: Đường dẫn tuyệt đối tới thư mục gốc của dự án
    """
    # Lấy thư mục đang chứa file này
    current_file_dir = os.path.dirname(os.path.abspath(__file__))
    # Đi lên một cấp để tới thư mục gốc của dự án (chứa main.py)
    project_root = os.path.dirname(current_file_dir)
    return project_root


def get_tools_dir():
    """
    Lấy đường dẫn tới thư mục tools.
    
    Trả về:
        str: Đường dẫn tuyệt đối tới thư mục tools
    """
    return os.path.join(get_project_root(), "tools")


def get_database_path():
    """
    Lấy đường dẫn tới file cơ sở dữ liệu.
    
    Trả về:
        str: Đường dẫn tuyệt đối tới file cơ sở dữ liệu
    """
    return os.path.join(get_project_root(), "database", "forensic_system.db")


def get_forensic_collection_dir():
    """
    Lấy đường dẫn tới thư mục thu thập chứng cứ (ForensicCollection).
    
    Trả về:
        str: Đường dẫn tuyệt đối tới thư mục ForensicCollection
    """
    return os.path.join(get_project_root(), "ForensicCollection")


def get_evidence_dir():
    """
    Lấy đường dẫn tới thư mục chứa chứng cứ.
    
    Trả về:
        str: Đường dẫn tuyệt đối tới thư mục evidence
    """
    return os.path.join(get_project_root(), "evidence")


def get_temp_dir():
    """
    Lấy đường dẫn tới thư mục tạm.
    
    Trả về:
        str: Đường dẫn tuyệt đối tới thư mục temp
    """
    return os.path.join(get_project_root(), "temp")


def get_static_dir():
    """
    Lấy đường dẫn tới thư mục tài nguyên tĩnh (static).
    
    Trả về:
        str: Đường dẫn tuyệt đối tới thư mục static
    """
    return os.path.join(get_project_root(), "static")


def get_ui_dir():
    """
    Lấy đường dẫn tới thư mục giao diện (ui).
    
    Trả về:
        str: Đường dẫn tuyệt đối tới thư mục ui
    """
    return os.path.join(get_project_root(), "ui")


def ensure_directories():
    """
    Đảm bảo các thư mục cần thiết tồn tại.
    Tự động tạo thư mục nếu chưa có.
    """
    directories = [
        get_forensic_collection_dir(),
        get_evidence_dir(),
        get_temp_dir(),
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
