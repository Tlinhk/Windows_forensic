# -*- coding: utf-8 -*-
# Dòng này khai báo bảng mã ký tự cho file là UTF-8,
# cho phép sử dụng các ký tự đặc biệt và tiếng Việt có dấu trong mã nguồn.
import sys
import os
import json
import subprocess
import time
import glob
import re
import math
import psutil
from datetime import datetime

# =========================================================
# I. IMPORT, BIẾN TOÀN CỤC VÀ HÀM TIỆN ÍCH NGOÀI CLASS
# =========================================================

# Thêm thư mục gốc của dự án vào đường dẫn Python (Python path)
# Điều này đảm bảo rằng các module của dự án có thể được import từ bất kỳ đâu.
current_dir = os.path.dirname(os.path.abspath(__file__)) # Lấy thư mục chứa file hiện tại
project_root = os.path.abspath(os.path.join(current_dir, "..", "..", "..")) # Đi ngược lên 3 cấp để đến thư mục gốc
if project_root not in sys.path:
    sys.path.append(project_root) # Thêm thư mục gốc vào sys.path nếu chưa có

# Import các thành phần cần thiết từ thư viện PyQt5 để xây dựng giao diện người dùng
from PyQt5 import QtCore, QtGui, QtWidgets
# Import lớp UI được tạo từ Qt Designer
from ui.pages.collect_ui.collect_nonvolatile_ui import Ui_CollectNonvolatileForm

# Kiểm tra xem thư viện WMI có khả dụng hay không.
# WMI (Windows Management Instrumentation) dùng để lấy thông tin hệ thống chi tiết trên Windows.
try:
    import wmi
    WMI_AVAILABLE = True # Nếu import thành công, đặt biến này là True
except ImportError:
    WMI_AVAILABLE = False # Nếu có lỗi (thư viện chưa cài đặt), đặt là False

# Kiểm tra xem thư viện win32file có khả dụng hay không.
# Thư viện này cung cấp quyền truy cập cấp thấp vào các file và thiết bị trên Windows.
try:
    import win32file
    WIN32_AVAILABLE = True # Nếu import thành công, đặt biến này là True
except ImportError:
    WIN32_AVAILABLE = False # Nếu có lỗi, đặt là False

def is_admin():
    """Hàm này kiểm tra xem người dùng hiện tại có quyền Administrator hay không."""
    try:
        # Import thư viện ctypes để tương tác với các hàm của hệ điều hành
        import ctypes
        # Gọi hàm IsUserAnAdmin() từ thư viện shell32.dll của Windows.
        # Hàm này trả về True nếu người dùng là Admin, ngược lại trả về False.
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        # Nếu có bất kỳ lỗi nào xảy ra (ví dụ: trên hệ điều hành không phải Windows),
        # hàm sẽ trả về False một cách an toàn.
        return False

# =========================================================
# II. CÁC CLASS PHỤ TRỢ (Worker/Loader)
# =========================================================

class KapeDataLoader(QtCore.QObject):
    """
    Lớp này được thiết kế để tải dữ liệu Targets và Modules của KAPE trong một luồng nền (background thread).
    Việc này giúp giao diện người dùng không bị "đóng băng" trong khi chương trình đọc và xử lý các file.
    Nó kế thừa từ QtCore.QObject để có thể sử dụng cơ chế signals/slots của Qt.
    """
    # Định nghĩa một tín hiệu (signal) tên là 'finished'.
    # Tín hiệu này sẽ được phát ra (emit) khi việc tải dữ liệu hoàn tất.
    # Nó sẽ mang theo hai danh sách: một cho targets và một cho modules.
    finished = QtCore.pyqtSignal(list, list)
    
    def __init__(self, tools_dir):
        """Hàm khởi tạo của lớp."""
        super().__init__()
        # Lưu đường dẫn đến thư mục chứa các công cụ (ví dụ: KAPE)
        self.tools_dir = tools_dir
        
    def run(self):
        """
        Đây là phương thức chính sẽ được thực thi khi worker này được chạy trong một luồng.
        """
        # Gọi hàm để nạp danh sách các targets
        targets = self.load_targets()
        # Gọi hàm để nạp danh sách các modules
        modules = self.load_modules()
        # Sau khi tải xong, phát tín hiệu 'finished' và gửi kèm hai danh sách vừa tải được
        self.finished.emit(targets, modules)
        
    def load_targets(self):
        """Nạp danh sách các 'Targets' từ thư mục của KAPE."""
        targets = []
        # Xây dựng đường dẫn đến thư mục chứa các file Target của KAPE
        kape_targets_path = os.path.join(self.tools_dir, "KAPE", "Targets")
        
        # Kiểm tra xem thư mục có tồn tại không
        if os.path.isdir(kape_targets_path):
            try:
                # Tìm tất cả các file có đuôi .tkape trong thư mục và các thư mục con
                target_files = glob.glob(os.path.join(kape_targets_path, "**", "*.tkape"), recursive=True)
                # Giới hạn số lượng file xử lý để cải thiện hiệu năng khi khởi động
                for target_file in target_files:
                    try:
                        # Mở và đọc nội dung file với mã hóa utf-8
                        with open(target_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        # Tên target là tên file không có phần mở rộng
                        name = os.path.splitext(os.path.basename(target_file))[0]
                        # Tên danh mục là tên của thư mục chứa file
                        category = os.path.basename(os.path.dirname(target_file))
                        # Trích xuất mô tả từ nội dung file
                        description = self.extract_description(content)
                        # Thêm thông tin target vào danh sách
                        targets.append((name, category, description))
                    except:
                        # Bỏ qua nếu có lỗi khi đọc một file cụ thể
                        continue
            except:
                # Bỏ qua nếu có lỗi chung khi tìm kiếm file
                pass            
        return targets
        
    def load_modules(self):
        """Nạp danh sách các 'Modules' từ thư mục của KAPE."""
        modules = []
        # Xây dựng đường dẫn đến thư mục chứa các file Module của KAPE
        kape_modules_path = os.path.join(self.tools_dir, "KAPE", "Modules")
        
        # Quy trình tương tự như load_targets
        if os.path.isdir(kape_modules_path):
            try:
                # Tìm tất cả các file có đuôi .mkape
                module_files = glob.glob(os.path.join(kape_modules_path, "**", "*.mkape"), recursive=True)
                # Giới hạn số lượng file xử lý để cải thiện hiệu năng
                for module_file in module_files:
                    try:
                        with open(module_file, 'r', encoding='utf-8') as f:
                            content = f.read()
                        name = os.path.splitext(os.path.basename(module_file))[0]
                        category = os.path.basename(os.path.dirname(module_file))
                        description = self.extract_description(content)
                        modules.append((name, category, description))
                    except:
                        continue
            except:
                pass            
        return modules
        
    def extract_description(self, content):
        """Trích xuất mô tả từ nội dung của file .tkape hoặc .mkape."""
        # Duyệt qua từng dòng trong nội dung
        for line in content.split('\n'):
            # Nếu dòng bắt đầu bằng 'Description:' (sau khi đã loại bỏ khoảng trắng thừa)
            if line.strip().startswith('Description:'):
                # Tách dòng tại dấu ':' và lấy phần thứ hai (phần mô tả)
                return line.split(':', 1)[1].strip()
        # Nếu không tìm thấy dòng mô tả, trả về chuỗi mặc định
        return "No description"
    

class DeviceScanner(QtCore.QObject):
    """
    Lớp này hoạt động như một "worker" để quét tìm các thiết bị lưu trữ (ổ cứng, SSD, USB)
    trong một luồng nền. Điều này giúp giao diện không bị treo trong quá trình quét,
    đặc biệt là khi hệ thống có nhiều thiết bị.
    """
    # Định nghĩa một tín hiệu (signal) tên là 'devicesFound'.
    # Tín hiệu này sẽ được phát ra khi quá trình quét hoàn tất,
    # mang theo một danh sách (list) các thiết bị đã tìm thấy.
    devicesFound = QtCore.pyqtSignal(list)

    def __init__(self, tools_dir: str = None, parent: QtCore.QObject = None):
        super().__init__(parent)
        self.tools_dir = tools_dir
    
    def scan(self):
        """
        Phương thức chính để bắt đầu quét thiết bị.
        Nó sẽ cố gắng sử dụng WMI trước tiên để có thông tin chi tiết.
        Nếu WMI không khả dụng hoặc có lỗi, nó sẽ chuyển sang phương pháp dự phòng.
        """
        devices = [] # Khởi tạo danh sách rỗng để chứa các thiết bị
        
        # Kiểm tra xem thư viện WMI có được import thành công không
        if WMI_AVAILABLE:
            try:
                # Kết nối đến dịch vụ WMI của Windows
                c = wmi.WMI()
                # Từ điển để lưu thông tin các ổ đĩa vật lý
                physical_disks = {}
                
                # ---- Bước 1: Lấy thông tin về các ổ đĩa vật lý (Win32_DiskDrive) ----
                for disk in c.Win32_DiskDrive():
                    disk_id = disk.DeviceID # Ví dụ: \\.\PHYSICALDRIVE0
                    physical_disks[disk_id] = {
                        'model': disk.Model or "Unknown", # Tên model ổ đĩa
                        'serial': disk.SerialNumber or "Unknown", # Số serial
                        'size': disk.Size, # Kích thước (bytes)
                        'status': disk.Status or "Unknown", # Trạng thái
                        'interface': disk.InterfaceType or "Unknown", # Giao tiếp (USB, IDE,...)
                        'partitions': [], # Danh sách các phân vùng
                        'logical_drives': [] # Danh sách các ổ đĩa logic (C:, D:,...)
                    }
                
                # ---- Bước 2: Liên kết ổ đĩa vật lý với các phân vùng và ổ đĩa logic ----
                # Duyệt qua tất cả các phân vùng
                for partition in c.Win32_DiskPartition():
                    # Tìm xem phân vùng này thuộc về ổ đĩa vật lý nào
                    for disk in partition.associators("Win32_DiskDriveToDiskPartition"):
                        disk_id = disk.DeviceID
                        if disk_id in physical_disks:
                            # Tìm các ổ đĩa logic (C:, D:) tương ứng với phân vùng này
                            for logical_disk in partition.associators("Win32_LogicalDiskToPartition"):
                                drive_info = {
                                    'letter': logical_disk.DeviceID,
                                    'filesystem': logical_disk.FileSystem or "Unknown",
                                }
                                # Thêm thông tin ổ logic vào danh sách của ổ vật lý tương ứng
                                physical_disks[disk_id]['logical_drives'].append(drive_info)
                
                # ---- Bước 3: Tổng hợp thông tin và định dạng để hiển thị ----
                for disk_id, disk_info in physical_disks.items():
                    is_windows = False
                    drive_letters = []
                    filesystems = set() # Dùng set để tránh trùng lặp hệ thống file
                    
                    for drive in disk_info['logical_drives']:
                        drive_letters.append(drive['letter'])
                        filesystems.add(drive['filesystem'])
                        # Kiểm tra xem đây có phải là ổ chứa hệ điều hành Windows không
                        if drive['letter'] == "C:":
                            is_windows = True
                    
                    # Định dạng lại thông tin để thêm vào danh sách kết quả cuối cùng
                    device = {
                        'id': disk_id,
                        'model': disk_info['model'],
                        'serial': disk_info['serial'].strip(), # Loại bỏ khoảng trắng thừa
                        'size': self.format_size_gb(disk_info['size']),
                        'filesystem': ", ".join(sorted(list(filesystems))),
                        'partitions': ", ".join(sorted(drive_letters)),
                        'is_windows': is_windows,
                        'encryption': "Unknown"  # Kiểm tra bất đồng bộ sau
                    }
                    devices.append(device)
            except Exception as e:
                # Nếu có lỗi với WMI, in ra lỗi và chuyển sang phương pháp dự phòng
                print(f"Error scanning devices with WMI: {e}")
                devices = self.scan_fallback()
        else:
            # Nếu WMI không khả dụng, sử dụng ngay phương pháp dự phòng
            devices = self.scan_fallback()

        # Không còn kiểm tra mã hóa bất đồng bộ
            
        # Phát tín hiệu 'devicesFound' cùng với danh sách thiết bị đã thu thập được
        self.devicesFound.emit(devices)
        
    def format_size_gb(self, size_bytes):
        """Định dạng kích thước từ bytes sang GB cho dễ đọc."""
        try:
            # Chuyển đổi từ bytes sang gigabytes
            size_gb = int(size_bytes) / (1024**3)
            # Trả về chuỗi đã định dạng, làm tròn đến 1 chữ số thập phân
            return f"{size_gb:.1f} GB"
        except:
            # Nếu có lỗi, trả về "Unknown"
            return "Unknown"
            
    def get_startup_info(self):
        """Tạo startup info để ẩn console trên Windows."""
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            return startupinfo
        return None

    def get_physical_drive_from_letter(self, drive_letter: str) -> str:
        """Chuyển C: → \\.\PHYSICALDRIVE0 nếu có thể (WMI)."""
        try:
            if WMI_AVAILABLE:
                c = wmi.WMI()
                for logical_disk in c.Win32_LogicalDisk(DeviceID=drive_letter):
                    for partition in logical_disk.associators("Win32_LogicalDiskToPartition"):
                        for disk in partition.associators("Win32_DiskDriveToDiskPartition"):
                            return disk.DeviceID
        except Exception:
            pass
        return None

    def check_encryption(self, drive_id: str) -> str:
        """ĐÃ LOẠI BỎ kiểm tra mã hóa. Trả về 'Unknown'."""
        return "Unknown"

    def _check_encryption_async(self, devices: list):
        """ĐÃ LOẠI BỎ: không còn kiểm tra mã hóa, giữ nguyên 'Unknown'."""
        try:
                self.devicesFound.emit(devices)
        except Exception:
            pass
        
    def scan_fallback(self):
        """
        Phương pháp quét thiết bị dự phòng, sử dụng lệnh 'wmic' của Windows.
        Phương pháp này cung cấp ít thông tin chi tiết hơn WMI nhưng đáng tin cậy.
        """
        devices = []
        try:
            # Chạy lệnh wmic để lấy thông tin về các ổ đĩa logic
            result = subprocess.run(
                ["wmic", "logicaldisk", "get", "deviceid,size,filesystem,volumename"],
                capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # Nếu lệnh chạy thành công
            if result.returncode == 0:
                # Tách kết quả thành các dòng, bỏ qua dòng tiêu đề đầu tiên
                lines = result.stdout.strip().split('\n')[1:]
                for line in lines:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        device_id = parts[0]
                        filesystem = parts[1] if len(parts) > 1 else "Unknown"
                        size_bytes = parts[2] if len(parts) > 2 and parts[2].isdigit() else 0
                        volume_name = " ".join(parts[3:]) if len(parts) > 3 else ""

                        # Tạo một đối tượng device với thông tin đã phân tích
                        device = {
                            'id': device_id,
                            'model': f"{volume_name} ({device_id})" if volume_name else device_id,
                            'serial': "Unknown", # wmic không cung cấp serial cho ổ logic
                            'size': self.format_size_gb(size_bytes),
                            'filesystem': filesystem,
                            'partitions': device_id,
                            'is_windows': device_id == "C:",
                            'encryption': "Unknown"
                        }
                        devices.append(device)
        except Exception as e:
            # In ra lỗi nếu phương pháp dự phòng cũng thất bại
            print(f"Error in scan_fallback: {e}")
            
        return devices

# =========================================================
# III. CLASS GIAO DIỆN CHÍNH: NonVolatilePage
# =========================================================

class NonVolatilePage(QtWidgets.QWidget, Ui_CollectNonvolatileForm):
    """
    Lớp chính điều khiển toàn bộ trang giao diện "Thu thập Dữ liệu Non-volatile".
    Nó kế thừa từ QtWidgets.QWidget (một widget cơ bản của Qt) và 
    Ui_CollectNonvolatileForm (lớp giao diện được tạo từ file .ui).
    """

    # -----------------------------------------------------
    # 1. KHỞI TẠO, SETUP BAN ĐẦU, KẾT NỐI TÍN HIỆU UI
    # -----------------------------------------------------
    
    def __init__(self, main_window=None):
        """Hàm khởi tạo (constructor) của lớp."""
        # Gọi hàm khởi tạo của các lớp cha
        super().__init__()
        # Thiết lập giao diện người dùng đã được định nghĩa trong Ui_CollectNonvolatileForm
        self.setupUi(self)
        # Chỉ cho phép chọn, không cho sửa ở các bảng chính
        try:
            for table in [
                getattr(self, 'tableWidget_devices', None),
                getattr(self, 'tableWidget_targets', None),
                getattr(self, 'tableWidget_modules', None),
            ]:
                if table:
                    table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
                    table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        except Exception:
            pass
        # Context case hiện tại (được truyền từ main/wizard)
        self.case_data = None
        # Tham chiếu main window (nếu có) để tự lấy case_id như FileAnalysis
        self.main_window = main_window
        
        # Thiết lập kích thước và chính sách size cho widget
        self.setMinimumSize(1200, 850)
        self.resize(1200, 850)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        
        # Bỏ status label cảnh báo để giao diện gọn hơn
        
        # --- Nhóm 2 radio vào cùng 1 ButtonGroup ---
        self.strategy_group = QtWidgets.QButtonGroup(self)
        self.strategy_group.addButton(self.radioButton_triage)
        self.strategy_group.addButton(self.radioButton_full_image)

        # --- Đường dẫn đến thư mục chứa các công cụ pháp lý ---
        self.tools_dir = r"E:\DoAn\Windows_forensic\tools"
        # EDD không còn được sử dụng
        self.kape_exe = os.path.join(self.tools_dir, "KAPE", "kape.exe") # Công cụ triage
        self.dc3dd_exe = os.path.join(self.tools_dir, "dc3dd", "dc3dd.exe") # Công cụ tạo ảnh RAW

        # Khởi tạo các biến trạng thái
        self.current_step = 0 # Bước hiện tại trong quy trình wizard, bắt đầu từ 0
        self.kape_process = None # Biến để giữ tiến trình KAPE đang chạy
        self.paused = False # Cờ báo hiệu tiến trình có đang tạm dừng hay không
        self.start_time = None # Thời điểm bắt đầu thu thập
        
        # Biến cho việc tạo ảnh đĩa
        self.imaging_active = False # Cờ báo hiệu việc tạo ảnh có đang diễn ra không
        self.imaging_paused = False # Cờ báo hiệu việc tạo ảnh có đang tạm dừng không
        
        # Khởi tạo WMI nếu thư viện có sẵn
        if WMI_AVAILABLE:
            try:
                # Tạo một đối tượng WMI để truy vấn thông tin hệ thống
                self.c = wmi.WMI()
            except Exception as e:
                # Nếu khởi tạo thất bại, đặt là None và in lỗi
                self.c = None
                print(f"WMI initialization failed: {e}")
        else:
            # Nếu thư viện không có, đặt là None
            self.c = None
        
        # Định nghĩa các trang của wizard
        # Mỗi mục trong danh sách là một đối tượng widget trang (page)
        self.pages = [
            self.page_step1_setup,       # Trang 1: Cài đặt và chọn nguồn
            self.page_step2_strategy,    # Trang 2: Chọn phương pháp (Triage/Imaging)
            self.page_step3_config,      # Trang 3: Cấu hình chi tiết
            self.page_step4_overview,    # Trang 4: Tổng quan cấu hình
            self.page_step5_progress     # Trang 5: Tiến trình thực hiện
        ]
        
        # Thiết lập trạng thái ban đầu cho toàn bộ giao diện
        self.setup_initial_state()
        # Kết nối các sự kiện (như click chuột) với các hàm xử lý
        self.connect_signals()
        
        # Tải dữ liệu (danh sách thiết bị, KAPE targets/modules) một cách bất đồng bộ
        # QtCore.QTimer.singleShot(100, ...) sẽ gọi hàm load_data_async sau 100ms
        # để không làm chậm việc hiển thị giao diện ban đầu.
        QtCore.QTimer.singleShot(100, self.load_data_async)

        # Nếu được truyền main_window và đã có case hiện tại, tự nạp case
        try:
            if self.main_window and getattr(self.main_window, "current_case_id", None):
                self.set_case_id(self.main_window.current_case_id)
        except Exception:
            pass

    def set_case_data(self, case_data: dict):
        """Nhận thông tin case và tự động điền thư mục đích Triage/Imaging theo archive_path."""
        try:
            self.case_data = case_data or {}
            # Điền thông tin cơ bản nếu có
            try:
                if hasattr(self, "lineEdit_case_id") and self.case_data.get("case_id"):
                    self.lineEdit_case_id.setText(str(self.case_data["case_id"]))
                if hasattr(self, "lineEdit_investigator") and self.case_data.get("investigator"):
                    self.lineEdit_investigator.setText(self.case_data["investigator"])
            except Exception:
                pass
            # Tự đảm bảo đường dẫn đích
            self.ensure_default_paths()
        except Exception:
            pass

    def set_case_id(self, case_id: int):
        """Fallback: nhận case_id và truy vấn DB lấy archive_path rồi gọi set_case_data."""
        try:
            from database.db_manager import DatabaseManager
            db = DatabaseManager()
            case = None
            if db.connect():
                case = db.get_case_with_investigator(case_id)
            if case:
                self.set_case_data({
                    "case_id": case_id,
                    "case_name": case.get("title", f"CASE-{case_id}"),
                    "investigator": case.get("full_name", "Unknown"),
                    "created_date": case.get("created_at", ""),
                    "archive_path": case.get("archive_path", ""),
                    "database_case_id": case_id,
                })
        except Exception:
            pass

    def ensure_default_paths(self):
        """Auto điền và tạo thư mục đích dựa trên archive_path của case."""
        try:
            archive_path = (self.case_data or {}).get("archive_path") or ""
            if not archive_path:
                return
            triage_dir = os.path.join(archive_path, "nonvolatile", "triage")
            imaging_dir = os.path.join(archive_path, "nonvolatile", "imaging")
            os.makedirs(triage_dir, exist_ok=True)
            os.makedirs(imaging_dir, exist_ok=True)

            if hasattr(self, "lineEdit_target_destination") and not self.lineEdit_target_destination.text().strip():
                self.lineEdit_target_destination.setText(triage_dir)
            if hasattr(self, "lineEdit_module_destination") and (
                not getattr(self, "lineEdit_module_destination", None)
                or not self.lineEdit_module_destination.text().strip()
            ):
                if hasattr(self, "lineEdit_module_destination"):
                    self.lineEdit_module_destination.setText(os.path.join(triage_dir, "ModuleOutput"))
            if hasattr(self, "lineEdit_destination_folder") and not self.lineEdit_destination_folder.text().strip():
                self.lineEdit_destination_folder.setText(imaging_dir)

            if hasattr(self, "update_image_path"):
                self.update_image_path()
        except Exception:
            pass
        
    def setup_initial_state(self):
        """Hàm này thiết lập các giá trị và trạng thái mặc định cho giao diện khi khởi động."""
        # Đặt wizard về trang đầu tiên (trang 0)
        self.stackedWidget.setCurrentIndex(0)
        # Trong trang cấu hình, mặc định hiển thị cấu hình cho Triage
        self.stackedWidget_config.setCurrentIndex(0)
        
        # Cập nhật giao diện của các chỉ báo bước (ví dụ: tô màu bước hiện tại)
        self.update_step_indicators()
        # Cập nhật trạng thái của các nút điều hướng (Next, Previous)
        self.update_navigation_buttons()
        
        # Ẩn nút "Start" ban đầu, nó chỉ hiện ở bước cuối
        self.pushButton_start.setVisible(False)
        
        # Khởi tạo giá trị cho các thành phần hiển thị tiến trình
        self.progressBar.setValue(0)
        self.label_errors_val.setText("0")
        self.label_source_progress_val.setText("0 GB / 0 GB")
        self.label_speed_val.setText("0 MB/s")
        self.label_time_elapsed_val.setText("00:00:00")
        self.label_eta_val.setText("00:00:00")
        
        # Tạo label hiển thị dung lượng thiết bị nguồn nếu layout tồn tại
        if hasattr(self, 'gridLayout_device_info'):
            if not hasattr(self, 'label_source_size'):
                self.label_source_size = QtWidgets.QLabel()
                self.gridLayout_device_info.addWidget(self.label_source_size, 2, 1)
            self.label_source_size.setText("Unknown")

        # Tạo label hiển thị đường dẫn xem trước nếu chưa có
        if not hasattr(self, 'label_preview_path'):
            self.label_preview_path = QtWidgets.QLabel(self)
            self.label_preview_path.setText("")
            # Thêm label này vào layout phù hợp
            if hasattr(self, 'verticalLayout_image_config'):
                self.verticalLayout_image_config.addWidget(self.label_preview_path)
        
        # Đặt các giá trị mặc định cho các ô nhập liệu
        # Tạo mã vụ việc mặc định dựa trên ngày giờ hiện tại
        self.lineEdit_case_id.setText(f"Case-{datetime.now().strftime('%Y%m%d-%H%M')}")
        self.spinBox_fragment_size.setValue(2048) # Mặc định phân mảnh file ảnh là 2GB

        # Mặc định bật các tùy chọn thu thập Targets và Modules
        self.checkBox_use_targets.setChecked(True)
        self.checkBox_use_modules.setChecked(True)
        
        # Khởi tạo các tùy chọn về định dạng ảnh
        self.radioButton_e01.setChecked(True) # Mặc định chọn định dạng E01
        self.comboBox_compression.setCurrentIndex(1) # Mặc định chọn nén "Fast"
        
        # Khởi tạo các tùy chọn xác minh
        self.checkBox_verify_after_creation.setChecked(True)
        self.checkBox_precalculate_progress.setChecked(True)
        self.checkBox_create_directory_listing.setChecked(True)
        self.checkBox_ad_encryption.setChecked(False)
        
        # Khởi tạo các tùy chọn băm (hash)
        self.checkBox_md5.setChecked(True)
        self.checkBox_sha1.setChecked(True)
        self.checkBox_sha256.setChecked(True)
        
        # Bỏ hệ thống triangle warnings
        
        # Khởi tạo dictionary cho target và module variables
        self.target_variables = {}  # Dict để lưu key:value pairs cho --tvars
        self.module_variables = {}  # Dict để lưu key:value pairs cho --mvars

    # Gỡ toàn bộ cơ chế triangle warnings và status label

    def connect_signals(self):
        """Kết nối tất cả các tín hiệu (signals) từ các widget trên UI tới các khe cắm (slots) xử lý tương ứng."""
        # Nút điều hướng
        self.pushButton_next.clicked.connect(self.next_page) # Nút Next -> hàm next_page
        self.pushButton_previous.clicked.connect(self.previous_page) # Nút Previous -> hàm previous_page
        self.pushButton_start.clicked.connect(self.start_collection) # Nút Start -> hàm start_collection
        
        # Quản lý thiết bị
        self.pushButton_refresh_devices.clicked.connect(self.refresh_devices) # Nút Refresh -> hàm refresh_devices
        self.tableWidget_devices.itemSelectionChanged.connect(self.on_device_selection_changed) # Thay đổi lựa chọn trong bảng -> hàm on_device_selection_changed
        
        # Điều khiển quá trình thu thập
        self.pushButton_pause.clicked.connect(self.pause_collection) # Nút Pause/Resume -> hàm pause_collection
        self.pushButton_stop.clicked.connect(self.stop_collection) # Nút Stop -> hàm stop_collection
        self.pushButton_save_log.clicked.connect(self.save_log) # Nút Save Log -> hàm save_log
        
        # Lựa chọn phương pháp thu thập
        self.radioButton_triage.toggled.connect(self.on_strategy_changed) # Chọn Triage -> hàm on_strategy_changed
        self.radioButton_full_image.toggled.connect(self.on_strategy_changed) # Chọn Full Image -> hàm on_strategy_changed
        
        # Tùy chọn Target/Module
        self.checkBox_use_targets.toggled.connect(self.toggle_target_options)
        self.checkBox_use_modules.toggled.connect(self.toggle_module_options)
        
        # Các nút chọn thư mục
        self.toolButton_target_source.clicked.connect(lambda: self.browse_folder(self.lineEdit_target_source))
        self.toolButton_target_destination.clicked.connect(self.browse_target_destination)
        self.pushButton_browse_folder.clicked.connect(self.browse_image_destination)
        
        # Tùy chọn module source/destination
        if hasattr(self, 'toolButton_module_source'):
            self.toolButton_module_source.clicked.connect(lambda: self.browse_folder(self.lineEdit_module_source))
        if hasattr(self, 'toolButton_module_destination'):
            self.toolButton_module_destination.clicked.connect(lambda: self.browse_folder(self.lineEdit_module_destination))
        
        # SHA-1 exclusions
        if hasattr(self, 'toolButton_sha1_exclusions'):
            self.toolButton_sha1_exclusions.clicked.connect(self.browse_sha1_exclusions)
        
        # Các nút chọn nhanh bộ Target định sẵn
        self.toolButton_sans.clicked.connect(lambda: self.select_predefined_targets("!SANS_Triage"))
        self.toolButton_quick.clicked.connect(lambda: self.select_predefined_targets("Quick_System_Info"))
        self.toolButton_browser.clicked.connect(lambda: self.select_predefined_targets("Browser_and_Email"))
        if hasattr(self, 'toolButton_registry'):
            self.toolButton_registry.clicked.connect(lambda: self.select_predefined_targets("Registry_All"))
        if hasattr(self, 'toolButton_logs'):
            self.toolButton_logs.clicked.connect(lambda: self.select_predefined_targets("EventLogs"))
        if hasattr(self, 'toolButton_memory'):
            self.toolButton_memory.clicked.connect(lambda: self.select_predefined_targets("Memory_Artefacts"))
        if hasattr(self, 'toolButton_persistence'):
            self.toolButton_persistence.clicked.connect(lambda: self.select_predefined_targets("Persistence"))
        
        # Target table controls
        if hasattr(self, 'pushButton_select_all_targets'):
            self.pushButton_select_all_targets.clicked.connect(self.select_all_targets)
        if hasattr(self, 'pushButton_clear_all_targets'):
            self.pushButton_clear_all_targets.clicked.connect(self.clear_all_targets)
        
        # Variable controls
        if hasattr(self, 'pushButton_add_variable'):
            self.pushButton_add_variable.clicked.connect(self.add_target_variable)
        
        # Chức năng tìm kiếm trong bảng
        self.lineEdit_targets_search.textChanged.connect(self.filter_targets) # Gõ vào ô tìm kiếm Target -> hàm filter_targets
        self.lineEdit_modules_search.textChanged.connect(self.filter_modules) # Gõ vào ô tìm kiếm Module -> hàm filter_modules
        
        # Định dạng ảnh và nén
        self.radioButton_e01.toggled.connect(self.on_format_changed)
        self.radioButton_raw.toggled.connect(self.on_format_changed)
        self.radioButton_aff.toggled.connect(self.on_format_changed)
        self.comboBox_compression.currentIndexChanged.connect(self.on_compression_changed)
        
        # Kích thước phân mảnh và tùy chọn xác minh
        self.spinBox_fragment_size.valueChanged.connect(self.on_fragment_size_changed)
        self.checkBox_verify_after_creation.toggled.connect(self.on_verification_option_changed)
        self.checkBox_precalculate_progress.toggled.connect(self.on_verification_option_changed)
        self.checkBox_create_directory_listing.toggled.connect(self.on_verification_option_changed)
        self.checkBox_ad_encryption.toggled.connect(self.on_verification_option_changed)
        
        # Thay đổi đường dẫn đích cho file ảnh
        self.lineEdit_destination_folder.textChanged.connect(self.update_image_path)
        self.lineEdit_image_filename.textChanged.connect(self.update_image_path)
        
        # Bỏ auto-update triangle indicators
        
        # Debug và export command line
        if hasattr(self, 'lineEdit_command_line'):
            self.lineEdit_command_line.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            self.lineEdit_command_line.customContextMenuRequested.connect(self.show_command_context_menu)
    
    def show_command_context_menu(self, position):
        """Hiển thị context menu cho command line field."""
        menu = QtWidgets.QMenu()
        
        copy_action = menu.addAction("📋 Copy Command")
        save_action = menu.addAction("💾 Save Command to File")
        validate_action = menu.addAction("✅ Validate Command")
        
        action = menu.exec_(self.lineEdit_command_line.mapToGlobal(position))
        
        if action == copy_action:
            self.copy_command_to_clipboard()
        elif action == save_action:
            self.save_command_to_file()
        elif action == validate_action:
            self.validate_command()
    
    def copy_command_to_clipboard(self):
        """Copy command line to clipboard."""
        command = self.lineEdit_command_line.text()
        if command:
            QtWidgets.QApplication.clipboard().setText(command)
            QtWidgets.QMessageBox.information(self, "Thành công", "Đã copy command line vào clipboard!")
    
    def save_command_to_file(self):
        """Save command line to a batch file."""
        command = self.lineEdit_command_line.text()
        if not command:
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Không có command line để lưu!")
            return
        
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Lưu Command Line", 
            f"kape_command_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bat",
            "Batch Files (*.bat);;Text Files (*.txt);;All Files (*)"
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write("@echo off\n")
                    f.write("REM KAPE Command generated by Windows Forensic Tool\n")
                    f.write(f"REM Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"REM Case ID: {self.lineEdit_case_id.text()}\n")
                    f.write("\n")
                    f.write("REM Change to KAPE directory\n")
                    f.write(f'cd /d "{os.path.dirname(self.kape_exe)}"\n')
                    f.write("\n")
                    f.write("REM Execute KAPE command\n")
                    f.write(command + "\n")
                    f.write("\n")
                    f.write("pause\n")
                
                QtWidgets.QMessageBox.information(self, "Thành công", f"Đã lưu command vào: {filename}")
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Lỗi", f"Không thể lưu file: {str(e)}")
    
    def validate_command(self):
        """Validate the current command line."""
        command = self.lineEdit_command_line.text()
        if not command:
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Không có command line để validate!")
            return
        
        issues = []
        
        # Check if KAPE exe exists
        if not os.path.exists(self.kape_exe):
            issues.append(f"KAPE executable không tìm thấy: {self.kape_exe}")
        
        # Check basic required parameters
        if "--tsource" not in command and "--msource" not in command:
            issues.append("Thiếu source (--tsource hoặc --msource)")
        
        if "--tdest" not in command and "--mdest" not in command:
            issues.append("Thiếu destination (--tdest hoặc --mdest)")
        
        # Check if target or module is specified
        if "--target" not in command and "--module" not in command:
            issues.append("Cần chỉ định ít nhất một --target hoặc --module")
        
        if issues:
            QtWidgets.QMessageBox.warning(self, "Validation Issues", 
                "Phát hiện các vấn đề:\n\n" + "\n".join(issues))
        else:
            QtWidgets.QMessageBox.information(self, "Validation Success", 
                "✅ Command line hợp lệ!\n\nSẵn sàng để thực thi.")

    # -----------------------------------------------------
    # 2. LOGIC ĐIỀU HƯỚNG CÁC BƯỚC (WIZARD NAVIGATION)
    # -----------------------------------------------------

    def update_step_indicators(self):
        """Cập nhật giao diện của các chỉ báo bước ở đầu trang."""
        # Danh sách các label tương ứng với các bước
        step_labels = [
            self.label_step1, self.label_step2, self.label_step3,
            self.label_step4, self.label_step5
        ]
        
        # Duyệt qua từng label để đặt stylesheet phù hợp
        for i, label in enumerate(step_labels):
            if i == self.current_step:
                # Bước hiện tại: Nền màu xanh dương, chữ trắng
                label.setStyleSheet("background-color: #2196F3; color: white; border-radius: 5px; padding: 5px; font-weight: bold;")
            elif i < self.current_step:
                # Các bước đã hoàn thành: Nền màu xanh lá, chữ trắng
                label.setStyleSheet("background-color: #4CAF50; color: white; border-radius: 5px; padding: 5px; font-weight: bold;")
            else:
                # Các bước chưa tới: Nền màu xám, chữ đen
                label.setStyleSheet("background-color: #E0E0E0; color: #333; border-radius: 5px; padding: 5px; font-weight: bold;")

    def update_navigation_buttons(self):
        """Cập nhật trạng thái (enable/disable) của các nút điều hướng."""
        # Nút "Previous" chỉ được bật khi không ở bước đầu tiên
        self.pushButton_previous.setEnabled(self.current_step > 0)
        # Nút "Next" chỉ được bật khi không ở bước cuối cùng
        self.pushButton_next.setEnabled(self.current_step < len(self.pages) - 1)
        
        # Chỉ hiển thị nút "Start" ở bước cuối cùng (trang tiến trình)
        self.pushButton_start.setVisible(self.current_step == len(self.pages) - 1)
        # Ẩn nút "Next" khi ở bước cuối cùng
        self.pushButton_next.setVisible(self.current_step < len(self.pages) - 1)

    def next_page(self):
        """Chuyển đến trang (bước) tiếp theo trong wizard."""
        # Kiểm tra xem có phải đang ở bước cuối cùng không
        if self.current_step < len(self.pages) - 1:
            # Xác thực thông tin của bước hiện tại trước khi đi tiếp
            if not self.validate_current_step():
                return # Nếu xác thực thất bại, không làm gì cả
            
            # Tăng chỉ số bước hiện tại
            self.current_step += 1
            # Hiển thị trang tương ứng trong stackedWidget
            self.stackedWidget.setCurrentIndex(self.current_step)
            
            # Xử lý các trường hợp đặc biệt cho từng bước
            if self.current_step == 2:  # Bước 3: Cấu hình
                self.update_config_page() # Cập nhật trang cấu hình (Triage/Image)
            elif self.current_step == 3:  # Bước 4: Tổng quan
                self.update_overview() # Cập nhật trang tổng quan
            elif self.current_step == 4:  # Bước 5: Tiến trình
                self.prepare_collection() # Chuẩn bị cho việc thu thập
            
            # Cập nhật lại giao diện chỉ báo và các nút điều hướng
            self.update_step_indicators()
            self.update_navigation_buttons()

    def previous_page(self):
        """Chuyển về trang (bước) trước đó trong wizard."""
        # Kiểm tra xem có phải đang ở bước đầu tiên không
        if self.current_step > 0:
            # Giảm chỉ số bước hiện tại
            self.current_step -= 1
            # Hiển thị trang tương ứng
            self.stackedWidget.setCurrentIndex(self.current_step)
            # Cập nhật lại giao diện chỉ báo và các nút điều hướng
            self.update_step_indicators()
            self.update_navigation_buttons()

    def update_config_page(self):
        """
        Hiển thị trang cấu hình phù hợp (Triage hoặc Imaging) dựa trên lựa chọn
        của người dùng ở bước 2.
        """
        if self.radioButton_triage.isChecked():
            # Nếu chọn Triage, hiển thị trang cấu hình Triage
            self.stackedWidget_config.setCurrentWidget(self.page_triage_config)
        else:
            # Nếu chọn Imaging, hiển thị trang cấu hình Imaging
            self.stackedWidget_config.setCurrentWidget(self.page_image_config)

    def on_strategy_changed(self):
        """
        Slot được gọi khi người dùng thay đổi lựa chọn phương pháp (Triage/Imaging).
        Nó sẽ bật/tắt các tùy chọn không liên quan trên giao diện.
        """
        # Cập nhật trang cấu hình để hiển thị đúng phần
        self.update_config_page()
        
        # Lấy trạng thái hiện tại
        is_triage = self.radioButton_triage.isChecked()

        # Bật/Tắt các frame và group box liên quan đến Triage
        if hasattr(self, 'frame_targets'):
            self.frame_targets.setEnabled(is_triage)
        if hasattr(self, 'frame_modules'):
            self.frame_modules.setEnabled(is_triage)
        if hasattr(self, 'groupBox_modules'):
            self.groupBox_modules.setEnabled(is_triage)
        if hasattr(self, 'groupBox_module_options'):
            self.groupBox_module_options.setEnabled(is_triage)
        if hasattr(self, 'groupBox_export_options'):
            self.groupBox_export_options.setEnabled(is_triage)

        # Bật/Tắt các group box và widget liên quan đến Imaging
        if hasattr(self, 'groupBox_image_format'):
            self.groupBox_image_format.setEnabled(not is_triage)
        if hasattr(self, 'groupBox_image_settings'):
            self.groupBox_image_settings.setEnabled(not is_triage)
        if hasattr(self, 'groupBox_verification'):
            self.groupBox_verification.setEnabled(not is_triage)
        if hasattr(self, 'groupBox_hashing'):
            self.groupBox_hashing.setEnabled(not is_triage)
        if hasattr(self, 'groupBox_image_source'):
            self.groupBox_image_source.setEnabled(not is_triage)
        if hasattr(self, 'groupBox_image_destination'):
            self.groupBox_image_destination.setEnabled(not is_triage)
        
        # Kiểm tra các thành phần UI khác trước khi truy cập
        for attr_name in ['lineEdit_destination_folder', 'lineEdit_image_filename', 'pushButton_browse_folder']:
            if hasattr(self, attr_name):
                getattr(self, attr_name).setEnabled(not is_triage)
        # Cố gắng tự điền lại đường dẫn theo case nếu có
        try:
            if self.case_data:
                self.set_case_data(self.case_data)
        except Exception:
            pass

    # -----------------------------------------------------
    # 3. KIỂM TRA, VALIDATE DỮ LIỆU Ở MỖI BƯỚC
    # -----------------------------------------------------
    def validate_current_step(self):
        """
        Kiểm tra xem người dùng đã nhập đủ thông tin bắt buộc cho bước hiện tại chưa.
        Trả về True nếu hợp lệ, False nếu không.
        """
        # Bổ sung: nếu chưa có case_data mà main_window đang có case, tự nạp
        try:
            if (not self.case_data) and getattr(self, 'main_window', None) and getattr(self.main_window, 'current_case_id', None):
                self.set_case_id(self.main_window.current_case_id)
        except Exception:
            pass

        # Bỏ cập nhật triangle indicators
        
        if self.current_step == 0:  # Bước 1: Cài đặt & Chọn Nguồn
            if not self.lineEdit_case_id.text().strip():
                QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập Mã vụ việc!")
                return False
            if self.tableWidget_devices.currentRow() < 0:
                QtWidgets.QMessageBox.warning(self, "Thiếu thiết bị", "Vui lòng chọn một thiết bị nguồn!")
                return False
            
            # Kiểm tra quyền admin với triangle warning
            if not is_admin():
                QtWidgets.QMessageBox.warning(self, "Cảnh báo quyền", 
                            "Để thực hiện thu thập forensic một cách an toàn, ứng dụng cần quyền Administrator.\n"
                            "Vui lòng khởi động lại ứng dụng với quyền Administrator.")
                return False
            
            # Nếu chọn ổ C:, phải tick vào ô chấp nhận rủi ro
            current_row = self.tableWidget_devices.currentRow()
            if current_row >= 0:
                partition_text = self.tableWidget_devices.item(current_row, 3).text()
                if "C:" in partition_text and not self.checkBox_accept_risk.isChecked():
                    QtWidgets.QMessageBox.warning(self, "Cảnh báo rủi ro", 
                                "Bạn đang chọn ổ hệ thống Windows. Vui lòng chấp nhận rủi ro trước khi tiếp tục!")
                    return False

        elif self.current_step == 1:  # Bước 2: Chọn Phương pháp
            if not (self.radioButton_triage.isChecked() or self.radioButton_full_image.isChecked()):
                QtWidgets.QMessageBox.warning(self, "Thiếu lựa chọn", "Vui lòng chọn một phương pháp thu thập!")
                return False
        
        elif self.current_step == 2:  # Bước 3: Cấu hình chi tiết
            if self.radioButton_triage.isChecked(): # Nếu là Triage
                # Auto điền nếu có case và còn trống
                try:
                    if self.case_data and hasattr(self, 'lineEdit_target_destination') and not self.lineEdit_target_destination.text().strip():
                        self.set_case_data(self.case_data)
                except Exception:
                    pass
                if not self.lineEdit_target_destination.text():
                    QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng chọn thư mục đích cho Triage!")
                    return False
                if not (self.checkBox_use_targets.isChecked() or self.checkBox_use_modules.isChecked()):
                    QtWidgets.QMessageBox.warning(self, "Thiếu lựa chọn", "Vui lòng chọn ít nhất một loại thu thập (Targets hoặc Modules)!")
                    return False
                
                # Kiểm tra xem có targets/modules nào được chọn không
                if self.checkBox_use_targets.isChecked():
                    selected_targets = [row for row in range(self.tableWidget_targets.rowCount()) 
                                      if self.tableWidget_targets.item(row, 0).checkState() == QtCore.Qt.Checked]
                    if not selected_targets:
                        QtWidgets.QMessageBox.warning(self, "Thiếu lựa chọn", "Vui lòng chọn ít nhất một Target!")
                        return False
                
                if self.checkBox_use_modules.isChecked():
                    selected_modules = [row for row in range(self.tableWidget_modules.rowCount()) 
                                      if self.tableWidget_modules.item(row, 0).checkState() == QtCore.Qt.Checked]
                    if not selected_modules:
                        QtWidgets.QMessageBox.warning(self, "Thiếu lựa chọn", "Vui lòng chọn ít nhất một Module!")
                        return False
                        
            else: # Nếu là Imaging
                # Auto điền nếu có case và còn trống
                try:
                    if self.case_data and hasattr(self, 'lineEdit_destination_folder') and not self.lineEdit_destination_folder.text().strip():
                        self.set_case_data(self.case_data)
                except Exception:
                    pass
                if not self.lineEdit_destination_folder.text():
                    QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng chọn thư mục đích cho file ảnh!")
                    return False
                if not self.lineEdit_image_filename.text():
                    QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập tên file ảnh!")
                    return False
                
                # Kiểm tra dung lượng bằng QMessageBox thay vì triangle
                if not self.check_disk_space(self.lineEdit_destination_folder.text(), self.get_device_size()):
                    return False
        
        return True # Nếu tất cả kiểm tra đều qua, trả về True

    # -----------------------------------------------------
    # 4. QUẢN LÝ DANH SÁCH, THÔNG TIN Ổ CỨNG/THIẾT BỊ
    # -----------------------------------------------------

    def refresh_devices(self):
        """
        Quét và hiển thị lại danh sách các ổ cứng/thiết bị lưu trữ vào bảng.
        Phương thức này sử dụng WMI để có thông tin chi tiết và đầy đủ nhất.
        Đây là phương thức được gọi trực tiếp khi người dùng nhấn nút "Làm mới".
        """
        # Xóa tất cả các hàng hiện có trong bảng để chuẩn bị cho dữ liệu mới
        self.tableWidget_devices.setRowCount(0)
        
        try:
            # Sử dụng thư viện WMI để lấy thông tin hệ thống
            if WMI_AVAILABLE:
                c = wmi.WMI()
                # Duyệt qua từng ổ đĩa vật lý (Win32_DiskDrive) mà WMI tìm thấy
                for disk in c.Win32_DiskDrive():
                    # Lấy số hàng hiện tại và thêm một hàng mới vào bảng
                    row = self.tableWidget_devices.rowCount()
                    self.tableWidget_devices.insertRow(row)
                    
                    # Lấy thông tin cơ bản của ổ đĩa
                    model = disk.Model or "Unknown"
                    serial = disk.SerialNumber.strip() if disk.SerialNumber else "Unknown"
                    device_id = disk.DeviceID # Ví dụ: \\.\PHYSICALDRIVE0
                    
                    # Chuyển đổi kích thước từ bytes sang GB
                    try:
                        size_gb = float(disk.Size) / (1024**3)
                        size_display = f"{size_gb:.1f} GB"
                    except:
                        size_display = "Unknown"
                    
                    # Tìm các phân vùng và ổ đĩa logic (C:, D:) liên kết với ổ đĩa vật lý này
                    is_windows = False
                    filesystems = set() # Dùng set để tránh lặp
                    partitions = []
                    
                    # Dùng associators để tìm các đối tượng liên quan
                    for partition in disk.associators("Win32_DiskDriveToDiskPartition"):
                        for logical_disk in partition.associators("Win32_LogicalDiskToPartition"):
                            # Kiểm tra xem có phải ổ C: (ổ hệ thống) không
                            if logical_disk.DeviceID == "C:":
                                is_windows = True
                            
                            # Thêm hệ thống file (NTFS, FAT32,...) vào set
                            if logical_disk.FileSystem:
                                filesystems.add(logical_disk.FileSystem)
                            
                            # Thêm ký tự ổ đĩa (C:, D:,...) vào danh sách
                            if logical_disk.DeviceID:
                                partitions.append(logical_disk.DeviceID)
                    
                    # Chuẩn bị chuỗi hiển thị
                    model_display = f"{model} ({serial})"
                    if is_windows:
                        model_display += " (Windows OS)" # Đánh dấu nếu là ổ Windows

                    # Đưa dữ liệu vào các ô trong bảng
                    # Cột 0: Model và Serial
                    self.tableWidget_devices.setItem(row, 0, QtWidgets.QTableWidgetItem(model_display))
                    # Cột 1: Hệ thống file
                    filesystem_display = ", ".join(sorted(list(filesystems))) if filesystems else "Unknown"
                    self.tableWidget_devices.setItem(row, 1, QtWidgets.QTableWidgetItem(filesystem_display))
                    # Cột 2: Kích thước đĩa
                    self.tableWidget_devices.setItem(row, 2, QtWidgets.QTableWidgetItem(size_display))
                    # Cột 3: Các phân vùng
                    partition_display = ", ".join(sorted(partitions)) if partitions else "Không có"
                    self.tableWidget_devices.setItem(row, 3, QtWidgets.QTableWidgetItem(partition_display))
                    # Cột 4: Trạng thái mã hóa (đã loại bỏ kiểm tra)
                    self.tableWidget_devices.setItem(row, 4, QtWidgets.QTableWidgetItem("Unknown"))
                    
                    # Tô màu vàng cho hàng chứa ổ đĩa Windows để cảnh báo
                    if is_windows:
                        for col in range(5):
                            item = self.tableWidget_devices.item(row, col)
                            if item:
                                item.setBackground(QtGui.QColor(255, 255, 200))
            
            # Nếu WMI thất bại hoặc không tìm thấy gì, thử phương pháp dự phòng
            if self.tableWidget_devices.rowCount() == 0:
                self.refresh_devices_fallback()
                
        except Exception as e:
            # Nếu có lỗi, hiển thị thông báo và thử phương pháp dự phòng
            QtWidgets.QMessageBox.warning(self, "Lỗi", f"Không thể lấy danh sách thiết bị bằng WMI: {str(e)}")
            self.refresh_devices_fallback()

    def refresh_devices_fallback(self):
        """Phương pháp dự phòng để lấy danh sách thiết bị bằng cách gọi lệnh 'wmic'."""
        try:
            # Chạy lệnh wmic để lấy thông tin các ổ đĩa logic
            result = subprocess.run(
                ["wmic", "logicaldisk", "where", "drivetype=3", "get", "deviceid,size,filesystem,volumename"],
                capture_output=True, text=True, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                # Tách kết quả thành các dòng, bỏ qua dòng tiêu đề
                lines = result.stdout.strip().split('\n')[1:]
                for line in lines:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        # Phân tích chuỗi đầu ra của wmic
                        device_id = parts[0]
                        filesystem = parts[2] if len(parts) >= 3 else "Unknown"
                        volume_name = " ".join(parts[3:]) if len(parts) >= 4 else ""
                        try:
                            size_bytes = int(parts[1]) if parts[1].isdigit() else 0
                            size_gb = size_bytes / (1024**3)
                            size = f"{size_gb:.1f} GB"
                        except:
                            size = "Unknown"
                        
                        # Thêm một hàng mới và điền thông tin
                        row = self.tableWidget_devices.rowCount()
                        self.tableWidget_devices.insertRow(row)
                        
                        display_name = f"{volume_name} ({device_id})" if volume_name else device_id
                        self.tableWidget_devices.setItem(row, 0, QtWidgets.QTableWidgetItem(display_name))
                        self.tableWidget_devices.setItem(row, 1, QtWidgets.QTableWidgetItem(filesystem))
                        self.tableWidget_devices.setItem(row, 2, QtWidgets.QTableWidgetItem(size))
                        self.tableWidget_devices.setItem(row, 3, QtWidgets.QTableWidgetItem(device_id))
                        # Cột 4: Trạng thái mã hóa (đã loại bỏ kiểm tra)
                        self.tableWidget_devices.setItem(row, 4, QtWidgets.QTableWidgetItem("Unknown"))
                        
                        # Tô màu cho ổ C:
                        if device_id == "C:":
                            for col in range(5):
                                item = self.tableWidget_devices.item(row, col)
                                if item:
                                    item.setBackground(QtGui.QColor(255, 255, 200))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Lỗi", f"Không thể tải danh sách thiết bị: {str(e)}")
            
    def update_device_list(self, devices):
        """
        Cập nhật bảng danh sách thiết bị với dữ liệu nhận được từ luồng nền (DeviceScanner).
        Đây là một "slot" nhận tín hiệu từ worker.
        """
        self.tableWidget_devices.setRowCount(0) # Xóa dữ liệu cũ
        
        # Duyệt qua danh sách thiết bị mà worker đã quét
        for device in devices:
            row = self.tableWidget_devices.rowCount()
            self.tableWidget_devices.insertRow(row)
            
            # Tương tự như refresh_devices, điền thông tin vào bảng
            model_display = f"{device['model']} ({device['serial']})"
            if device['is_windows']:
                model_display += " (Windows OS)"
            
            self.tableWidget_devices.setItem(row, 0, QtWidgets.QTableWidgetItem(model_display))
            self.tableWidget_devices.setItem(row, 1, QtWidgets.QTableWidgetItem(device['filesystem']))
            self.tableWidget_devices.setItem(row, 2, QtWidgets.QTableWidgetItem(device['size']))
            self.tableWidget_devices.setItem(row, 3, QtWidgets.QTableWidgetItem(device['partitions']))
            self.tableWidget_devices.setItem(row, 4, QtWidgets.QTableWidgetItem(device['encryption']))
            
            # Tô màu nền cho ổ Windows
            if device['is_windows']:
                for col in range(5):
                    item = self.tableWidget_devices.item(row, col)
                    if item:
                        item.setBackground(QtGui.QColor(255, 255, 200))
                        
        self.device_thread.quit() # Dừng luồng sau khi hoàn thành
    
    def get_startup_info(self):
        """Tạo startup info để ẩn cửa sổ console trên Windows."""
        if os.name == 'nt':  # Windows
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            return startupinfo
        return None

    def check_encryption_status(self, drive_index):
        """ĐÃ LOẠI BỎ: luôn trả về 'Unknown'."""
        return "Unknown"

    # -----------------------------------------------------
    # 5. XỬ LÝ LOAD VÀ HIỂN THỊ TARGETS/MODULES (KAPE)
    # -----------------------------------------------------

    def load_data_async(self):
        """
        Tải các dữ liệu cần thời gian (như danh sách thiết bị, danh sách KAPE)
        một cách bất đồng bộ để không làm treo giao diện chính.
        """
        # --- Tải dữ liệu KAPE trong một luồng nền ---
        # 1. Tạo một luồng (QThread)
        self.kape_thread = QtCore.QThread()
        # 2. Tạo một worker (KapeDataLoader) để thực hiện công việc tải dữ liệu
        self.kape_worker = KapeDataLoader(self.tools_dir)
        # 3. Di chuyển worker vào luồng đã tạo
        self.kape_worker.moveToThread(self.kape_thread)
        # 4. Kết nối tín hiệu 'finished' của worker với slot 'on_kape_data_loaded'
        #    Khi worker tải xong, nó sẽ phát tín hiệu này và gọi hàm on_kape_data_loaded
        self.kape_worker.finished.connect(self.on_kape_data_loaded)
        # 5. Kết nối tín hiệu 'started' của luồng với phương thức 'run' của worker
        self.kape_thread.started.connect(self.kape_worker.run)
        # 6. Bắt đầu luồng
        self.kape_thread.start()
        
        # --- Làm mới danh sách thiết bị trong một luồng nền (tương tự như trên) ---
        self.device_thread = QtCore.QThread()
        # Khởi tạo worker quét thiết bị với tools_dir để kiểm tra mã hóa bằng EDD
        try:
            self.device_worker = DeviceScanner(self.tools_dir)
        except TypeError:
            # Fallback nếu chữ ký hàm không hỗ trợ đối số tên
            self.device_worker = DeviceScanner(self.tools_dir)
        self.device_worker.moveToThread(self.device_thread)
        # Khi worker quét xong, tín hiệu 'devicesFound' sẽ gọi hàm 'update_device_list'
        self.device_worker.devicesFound.connect(self.update_device_list)
        self.device_thread.started.connect(lambda: self.initialize_wmi_and_scan())
        self.device_thread.start()
    
    def initialize_wmi_and_scan(self):
        """Initialize WMI in the worker thread and start scanning."""
        try:
            import pythoncom
            pythoncom.CoInitialize()  # Initialize COM for this thread
            self.device_worker.scan()
        except Exception as e:
            print(f"Error initializing WMI in thread: {e}")
        finally:
            try:
                pythoncom.CoUninitialize()  # Clean up COM
            except:
                pass
        
    def on_kape_data_loaded(self, targets, modules):
        """
        Slot này được gọi khi KapeDataLoader hoàn thành việc tải dữ liệu.
        Nó nhận về danh sách targets và modules.
        """
        # Cập nhật bảng Targets trên giao diện với dữ liệu vừa nhận được
        self.update_targets_table(targets)
        # Cập nhật bảng Modules trên giao diện
        self.update_modules_table(modules)
        # Dọn dẹp và dừng luồng tải KAPE
        self.kape_thread.quit()
        
    def update_targets_table(self, targets):
        """Cập nhật nội dung của bảng hiển thị Targets (tableWidget_targets)."""
        # Xóa tất cả các hàng hiện có
        self.tableWidget_targets.setRowCount(0)
        
        # Duyệt qua danh sách targets đã được tải
        for name, category, description in targets:
            row = self.tableWidget_targets.rowCount()
            # Thêm một hàng mới vào cuối bảng
            self.tableWidget_targets.insertRow(row)
            
            # Cột 0: Checkbox
            checkbox = QtWidgets.QTableWidgetItem()
            # Đặt cờ để item này có thể được check và luôn được bật
            checkbox.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            checkbox.setCheckState(QtCore.Qt.Unchecked) # Mặc định là chưa check
            self.tableWidget_targets.setItem(row, 0, checkbox)
            
            # Cột 1, 2, 3: Điền thông tin Name, Category, và Description
            self.tableWidget_targets.setItem(row, 1, QtWidgets.QTableWidgetItem(name))
            self.tableWidget_targets.setItem(row, 2, QtWidgets.QTableWidgetItem(category))
            self.tableWidget_targets.setItem(row, 3, QtWidgets.QTableWidgetItem(description))

    def update_modules_table(self, modules):
        """Cập nhật nội dung của bảng hiển thị Modules (tableWidget_modules)."""
        # Logic hoàn toàn tương tự như update_targets_table
        self.tableWidget_modules.setRowCount(0)
        
        for name, category, description in modules:
            row = self.tableWidget_modules.rowCount()
            self.tableWidget_modules.insertRow(row)
            
            # Thêm checkbox
            checkbox = QtWidgets.QTableWidgetItem()
            checkbox.setFlags(QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsEnabled)
            checkbox.setCheckState(QtCore.Qt.Unchecked)
            self.tableWidget_modules.setItem(row, 0, checkbox)
            
            # Điền thông tin
            self.tableWidget_modules.setItem(row, 1, QtWidgets.QTableWidgetItem(name))
            self.tableWidget_modules.setItem(row, 2, QtWidgets.QTableWidgetItem(category))
            self.tableWidget_modules.setItem(row, 3, QtWidgets.QTableWidgetItem(description))

    def toggle_target_options(self, enabled):
        """Bật hoặc tắt các vùng giao diện liên quan đến Targets."""
        # Enable/disable the targets frame and related components
        if hasattr(self, 'frame_targets'):
            # Enable/disable specific sections within the frame
            if hasattr(self, 'gridLayout_target_options'):
                # Enable/disable individual widgets in the target options layout
                for i in range(self.gridLayout_target_options.count()):
                    widget = self.gridLayout_target_options.itemAt(i).widget()
                    if widget:
                        widget.setEnabled(enabled)
            
            if hasattr(self, 'tableWidget_targets'):
                self.tableWidget_targets.setEnabled(enabled)
            if hasattr(self, 'lineEdit_targets_search'):
                self.lineEdit_targets_search.setEnabled(enabled)
    
    def toggle_module_options(self, enabled):
        """Bật hoặc tắt các vùng giao diện liên quan đến Modules."""
        # Các groupbox này có thể không tồn tại trên UI, cần kiểm tra trước
        if hasattr(self, 'groupBox_module_options'):
            self.groupBox_module_options.setEnabled(enabled)
        if hasattr(self, 'groupBox_modules'):
            self.groupBox_modules.setEnabled(enabled)
        if hasattr(self, 'groupBox_export_options'):
            self.groupBox_export_options.setEnabled(enabled)
        if hasattr(self, 'frame_modules'):
            # Also enable/disable the entire modules frame if needed
            pass  # The frame is handled separately
    
    def browse_folder(self, line_edit):
        """Mở hộp thoại cho phép người dùng chọn một thư mục."""
        # Hiển thị hộp thoại chọn thư mục
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Chọn thư mục")
        # Nếu người dùng chọn một thư mục (không nhấn Cancel)
        if folder:
            # Đặt đường dẫn thư mục đã chọn vào ô line_edit được truyền vào
            line_edit.setText(folder)
    
    def select_predefined_targets(self, target_name):
        """Chọn nhanh một nhóm các Targets đã được định nghĩa trước."""
        # Đầu tiên, bỏ chọn tất cả các checkbox hiện có
        for row in range(self.tableWidget_targets.rowCount()):
            checkbox = self.tableWidget_targets.item(row, 0)
            if checkbox:
                checkbox.setCheckState(QtCore.Qt.Unchecked)
        
        # Xác định danh sách các target cần chọn dựa trên tên nhóm
        if target_name == "!SANS_Triage":
            target_names = ["!SANS_Triage", "WindowsEventLogs", "RegistryHives", "Prefetch"]
        elif target_name == "Quick_System_Info":
            target_names = ["RegistryHives", "WindowsEventLogs", "Prefetch"]
        elif target_name == "Browser_and_Email":
            target_names = ["BrowserHistory", "Chrome", "Firefox", "Edge"]
        elif target_name == "Registry_All":
            target_names = ["RegistryHives", "RegistryBackups", "AmCache", "Syscache"]
        elif target_name == "EventLogs":
            target_names = ["WindowsEventLogs", "Application Event Logs", "Security Logs"]
        elif target_name == "Memory_Artefacts":
            target_names = ["Memory", "Hibernation", "PageFile"]
        elif target_name == "Persistence":
            target_names = ["AutoStart", "Services", "Scheduled Tasks", "Registry Persistence"]
        else:
            target_names = []
        
        # Duyệt qua bảng và tick vào các checkbox tương ứng
        for row in range(self.tableWidget_targets.rowCount()):
            name_item = self.tableWidget_targets.item(row, 1)
            # Nếu tên của target ở hàng hiện tại nằm trong danh sách cần chọn
            if name_item and name_item.text() in target_names:
                checkbox = self.tableWidget_targets.item(row, 0)
                if checkbox:
                    checkbox.setCheckState(QtCore.Qt.Checked) # Tick vào ô
    
    def select_all_targets(self):
        """Chọn tất cả các targets trong bảng."""
        for row in range(self.tableWidget_targets.rowCount()):
            checkbox = self.tableWidget_targets.item(row, 0)
            if checkbox:
                checkbox.setCheckState(QtCore.Qt.Checked)
    
    def clear_all_targets(self):
        """Bỏ chọn tất cả các targets trong bảng."""
        for row in range(self.tableWidget_targets.rowCount()):
            checkbox = self.tableWidget_targets.item(row, 0)
            if checkbox:
                checkbox.setCheckState(QtCore.Qt.Unchecked)
    
    def browse_sha1_exclusions(self):
        """Mở hộp thoại để chọn file chứa SHA-1 hash exclusions."""
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Chọn file SHA-1 exclusions",
            "", "Text Files (*.txt);;All Files (*)"
        )
        if filename:
            self.lineEdit_sha1_exclusions.setText(filename)
    
    def add_target_variable(self):
        """Thêm biến target vào danh sách để sử dụng với --tvars."""
        key = self.lineEdit_variable_key.text().strip()
        value = self.lineEdit_variable_value.text().strip()
        
        if not key or not value:
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng nhập cả key và value!")
            return
        
        # Validate key format (should not contain special characters used by KAPE)
        if ':' in key or '^' in key:
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Key không được chứa ký tự ':' hoặc '^'!")
            return
        
        # Lưu vào dictionary
        self.target_variables[key] = value
        
        # Hiển thị thông báo thành công với danh sách hiện tại
        var_list = [f"{k}:{v}" for k, v in self.target_variables.items()]
        QtWidgets.QMessageBox.information(self, "Thành công", 
            f"Đã thêm biến: {key} = {value}\n\n"
            f"Danh sách biến hiện tại:\n" + "\n".join(var_list))
        
        # Xóa nội dung sau khi thêm
        self.lineEdit_variable_key.clear()
        self.lineEdit_variable_value.clear()
    
    def get_variables_string(self, variables_dict):
        """Chuyển đổi dictionary thành string format cho KAPE --tvars/--mvars."""
        if not variables_dict:
            return ""
        # Format: key1:value1^key2:value2^key3:value3
        return "^".join([f"{k}:{v}" for k, v in variables_dict.items()])
    
    def filter_targets(self, text):
        """Lọc bảng Targets dựa trên nội dung người dùng nhập vào ô tìm kiếm."""
        # Duyệt qua từng hàng trong bảng
        for row in range(self.tableWidget_targets.rowCount()):
            visible = False # Mặc định là ẩn hàng này đi
            # Duyệt qua các cột có chứa text (bỏ qua cột checkbox)
            for col in range(1, 4):
                item = self.tableWidget_targets.item(row, col)
                # Nếu text tìm kiếm (chuyển về chữ thường) có trong nội dung của ô
                if item and text.lower() in item.text().lower():
                    visible = True # Đặt cờ là sẽ hiển thị hàng này
                    break # Thoát khỏi vòng lặp cột vì đã tìm thấy
            # Ẩn hoặc hiện hàng dựa trên cờ 'visible'
            self.tableWidget_targets.setRowHidden(row, not visible)
    
    def filter_modules(self, text):
        """Lọc bảng Modules dựa trên nội dung người dùng nhập vào ô tìm kiếm."""
        # Logic hoàn toàn tương tự như filter_targets
        for row in range(self.tableWidget_modules.rowCount()):
            visible = False
            for col in range(1, 4):
                item = self.tableWidget_modules.item(row, col)
                if item and text.lower() in item.text().lower():
                    visible = True
                    break
            self.tableWidget_modules.setRowHidden(row, not visible)

    # -----------------------------------------------------
    # 6. XÂY DỰNG LỆNH THU THẬP/IMAGE (BUILD COMMAND LINE)
    # -----------------------------------------------------
    
    def update_overview(self):
        """
        Cập nhật trang tổng quan (bước 4) với các thông tin cấu hình mà người dùng đã chọn.
        """
        # Tạo một bản tóm tắt HTML về cấu hình
        summary = self.generate_configuration_summary()
        # Hiển thị bản tóm tắt này trong textBrowser
        self.textBrowser_summary.setHtml(summary)
        
        # Xây dựng dòng lệnh tương ứng với cấu hình
        command = self.build_command_line()
        # Hiển thị dòng lệnh trong ô lineEdit
        self.lineEdit_command_line.setText(' '.join(command))
    
    def generate_configuration_summary(self):
        """Tạo một chuỗi HTML để tóm tắt tất cả các lựa chọn của người dùng."""
        html = "<h3>📋 Tóm tắt Cấu hình</h3>"
        
        # Triangle warnings removed
        
        # --- Thông tin Vụ việc ---
        html += "<h4>🏷️ Thông tin Vụ việc</h4>"
        html += f"<b>Mã vụ việc:</b> {self.lineEdit_case_id.text()}<br>"
        html += f"<b>Điều tra viên:</b> {self.lineEdit_investigator.text()}<br>"
        html += f"<b>Mô tả:</b> {self.lineEdit_case_description.text()}<br><br>"
        
        # --- Thiết bị Nguồn ---
        html += "<h4>💾 Thiết bị Nguồn</h4>"
        current_row = self.tableWidget_devices.currentRow()
        if current_row >= 0:
            model = self.tableWidget_devices.item(current_row, 0).text()
            partition = self.tableWidget_devices.item(current_row, 3).text()
            size = self.tableWidget_devices.item(current_row, 2).text()
            html += f"<b>Thiết bị:</b> {model}<br>"
            html += f"<b>Phân vùng:</b> {partition}<br>"
            html += f"<b>Dung lượng:</b> {size}<br><br>"
        
        # --- Phương pháp Thu thập ---
        html += "<h4>🎯 Phương pháp Thu thập</h4>"
        if self.radioButton_triage.isChecked():
            html += "<b>Loại:</b> Thu thập Triage (Nhanh & có Mục tiêu)<br>"
            
            # Liệt kê các Targets và Modules đã chọn
            if self.checkBox_use_targets.isChecked():
                selected_targets = [self.tableWidget_targets.item(row, 1).text() 
                                    for row in range(self.tableWidget_targets.rowCount()) 
                                    if self.tableWidget_targets.item(row, 0).checkState() == QtCore.Qt.Checked]
                html += f"<b>Targets đã chọn:</b> {len(selected_targets)}<br>"
                # Hiển thị 5 target đầu tiên để tóm tắt
                if selected_targets:
                    html += "<ul>" + "".join([f"<li>{t}</li>" for t in selected_targets[:5]])
                    if len(selected_targets) > 5:
                        html += f"<li>... và {len(selected_targets) - 5} targets khác</li>"
                    html += "</ul>"

            if self.checkBox_use_modules.isChecked():
                selected_modules = [self.tableWidget_modules.item(row, 1).text() 
                                    for row in range(self.tableWidget_modules.rowCount()) 
                                    if self.tableWidget_modules.item(row, 0).checkState() == QtCore.Qt.Checked]
                html += f"<b>Modules đã chọn:</b> {len(selected_modules)}<br>"
        else: # Nếu là Imaging
            html += "<b>Loại:</b> Tạo ảnh Toàn bộ (Toàn diện & An toàn)<br>"
            
            # Định dạng ảnh
            format_text = "E01" if self.radioButton_e01.isChecked() else "Raw" if self.radioButton_raw.isChecked() else "AFF"
            html += f"<b>Định dạng:</b> {format_text}<br>"
            
            # Mức độ nén (chỉ áp dụng cho E01/AFF)
            if format_text != "Raw":
                html += f"<b>Mức nén:</b> {self.comboBox_compression.currentText()}<br>"
            
            # Phân mảnh
            frag_size = self.spinBox_fragment_size.value()
            html += f"<b>Phân mảnh:</b> {'Không' if frag_size == 0 else str(frag_size) + ' MB'}<br>"

            # Các thuật toán băm đã chọn
            hashes = [cb.text() for cb in [self.checkBox_md5, self.checkBox_sha1, self.checkBox_sha256] if cb.isChecked()]
            html += f"<b>Hash:</b> {', '.join(hashes) if hashes else 'Không'}<br>"
        
        # --- Target Variables (nếu có) ---
        if hasattr(self, 'target_variables') and self.target_variables:
            html += "<h4>🔧 Target Variables</h4>"
            for key, value in self.target_variables.items():
                html += f"<b>%{key}%:</b> {value}<br>"
            html += "<br>"
        
        # --- Module Variables (nếu có) ---
        if hasattr(self, 'module_variables') and self.module_variables:
            html += "<h4>⚙️ Module Variables</h4>"
            for key, value in self.module_variables.items():
                html += f"<b>%{key}%:</b> {value}<br>"
            html += "<br>"
        
        return html
    
    def build_command_line(self):
        """
        Hàm chính để xây dựng dòng lệnh dựa trên lựa chọn của người dùng.
        Nó sẽ gọi các hàm con tương ứng với phương pháp Triage hoặc Imaging.
        """
        if self.radioButton_triage.isChecked():
            return self.build_kape_command()
        else:
            return self.build_imaging_command()
    
    def build_kape_command(self):
        """Xây dựng lệnh KAPE chi tiết với tất cả các tùy chọn từ UI theo đúng syntax KAPE."""
        cmd = [self.kape_exe]
        
        # === TARGET OPTIONS ===
        current_row = self.tableWidget_devices.currentRow()
        if current_row >= 0:
            # --tsource: Target source drive (C:, D:, F:\ etc)
            source = self.lineEdit_target_source.text() or self.tableWidget_devices.item(current_row, 3).text().split(',')[0]
            if not source.endswith(':') and not source.endswith('\\'):
                source = source + ':'  # Ensure proper drive format
            cmd.extend(["--tsource", source])
        
        # --tdest: Destination directory với biến %d (date) và %m (machine) nếu cần
        tdest = self.lineEdit_target_destination.text().strip() if hasattr(self, "lineEdit_target_destination") else ""
        if tdest:
            os.makedirs(tdest, exist_ok=True)
        target_dest = self.lineEdit_target_destination.text()
        if hasattr(self, 'checkBox_add_date') and self.checkBox_add_date.isChecked():
            target_dest = target_dest + "_%d"  # %d = timestamp (yyyyMMddTHHmmss)
        if hasattr(self, 'checkBox_add_machine') and self.checkBox_add_machine.isChecked():
            target_dest = target_dest + "_%m"  # %m = machine name
        cmd.extend(["--tdest", target_dest])
        
        # --target: Target configurations
        if self.checkBox_use_targets.isChecked():
            selected = [self.tableWidget_targets.item(row, 1).text() 
                        for row in range(self.tableWidget_targets.rowCount()) 
                        if self.tableWidget_targets.item(row, 0).checkState() == QtCore.Qt.Checked]
            if selected:
                cmd.extend(["--target", ",".join(selected)])
        
        # --tflush: Delete all files in tdest prior to collection
        if hasattr(self, 'checkBox_flush') and self.checkBox_flush.isChecked():
            cmd.append("--tflush")
        
        # --tdd: Deduplicate files based on SHA-1 (default is TRUE, so only add if unchecked)
        if hasattr(self, 'checkBox_deduplicate') and not self.checkBox_deduplicate.isChecked():
            # KAPE default is TRUE for deduplication, so we don't need to add --tdd unless we want to disable it
            # But KAPE doesn't have a disable option, so we skip this
            pass
        
        # --vss: Process Volume Shadow Copies
        if hasattr(self, 'checkBox_process_vscs') and self.checkBox_process_vscs.isChecked():
            cmd.append("--vss")
        
        # === MODULE OPTIONS ===
        if self.checkBox_use_modules.isChecked():
            selected_modules = [self.tableWidget_modules.item(row, 1).text() 
                              for row in range(self.tableWidget_modules.rowCount()) 
                              if self.tableWidget_modules.item(row, 0).checkState() == QtCore.Qt.Checked]
            if selected_modules:
                # --msource: Auto-set to --tdest if not specified
                module_source = self.lineEdit_module_source.text() if hasattr(self, 'lineEdit_module_source') else ""
                if module_source:
                    cmd.extend(["--msource", module_source])
                # If not specified, KAPE will auto-set to --tdest
                
                # --module: Module configurations
                cmd.extend(["--module", ",".join(selected_modules)])
                
                # --mdest: Module output destination
                module_dest = self.lineEdit_module_destination.text() if hasattr(self, 'lineEdit_module_destination') else ""
                if not module_dest:
                    module_dest = os.path.join(target_dest, "ModuleOutput")
                cmd.extend(["--mdest", module_dest])
                
                # --mef: Export format for modules
                if hasattr(self, 'radioButton_export_csv') and self.radioButton_export_csv.isChecked():
                    cmd.extend(["--mef", "csv"])
                elif hasattr(self, 'radioButton_export_json') and self.radioButton_export_json.isChecked():
                    cmd.extend(["--mef", "json"])
                elif hasattr(self, 'radioButton_export_html') and self.radioButton_export_html.isChecked():
                    cmd.extend(["--mef", "html"])
        
        # === CONTAINER OPTIONS ===
        base_name = ""
        if hasattr(self, 'lineEdit_base_name'):
            base_name = self.lineEdit_base_name.text() or f"KAPE_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if hasattr(self, 'radioButton_vhdx') and self.radioButton_vhdx.isChecked():
            cmd.extend(["--vhdx", base_name])
        elif hasattr(self, 'radioButton_vhd') and self.radioButton_vhd.isChecked():
            cmd.extend(["--vhd", base_name])
        elif hasattr(self, 'radioButton_zip') and self.radioButton_zip.isChecked():
            cmd.extend(["--zip", base_name])
        
        # --zv: Zip the VHD(X) container after creation (default TRUE)
        if hasattr(self, 'checkBox_zip_container') and not self.checkBox_zip_container.isChecked():
            # KAPE default is TRUE, but we can't disable it with a flag
            # This checkbox probably should control whether we use containers at all
            pass
        
        # === ADVANCED OPTIONS ===
        # --hex: SHA-1 exclusion file
        if hasattr(self, 'lineEdit_sha1_exclusions') and self.lineEdit_sha1_exclusions.text():
            cmd.extend(["--hex", self.lineEdit_sha1_exclusions.text()])
        
        # --tvars: Target variables (key:value pairs separated by ^)
        tvars_string = self.get_variables_string(self.target_variables)
        if tvars_string:
            cmd.extend(["--tvars", tvars_string])
        
        # --mvars: Module variables (key:value pairs separated by ^) 
        mvars_string = self.get_variables_string(self.module_variables)
        if mvars_string:
            cmd.extend(["--mvars", mvars_string])
        
        # === DEBUG OPTIONS ===
        cmd.append("--debug")  # Show debug information during processing
        
        return cmd
    
    def build_imaging_command(self):
        """Xây dựng lệnh imaging với kiểm tra thiết bị cải thiện."""
        current_row = self.tableWidget_devices.currentRow()
        if current_row < 0: 
            return ["echo", "Chưa chọn thiết bị"]
        
        # Lấy device ID một cách thông minh hơn
        device_id = None
        model_text = self.tableWidget_devices.item(current_row, 0).text()
        
        # Tìm physical drive pattern
        match = re.search(r'(\\\\\.\\PHYSICALDRIVE\d+)', model_text, re.IGNORECASE)
        if match:
            device_id = match.group(1)
        else:
            # Fallback: sử dụng partition từ cột 3
            partitions = self.tableWidget_devices.item(current_row, 3).text()
            if partitions and ':' in partitions:
                # Convert drive letter to physical drive
                device_id = self.get_physical_drive_from_letter(partitions.split(',')[0])
        
        if not device_id:
            return ["echo", "Không thể xác định device ID"]

        # Gọi hàm xây dựng lệnh phù hợp với định dạng ảnh đã chọn
        if self.radioButton_raw.isChecked():
            return self.build_dd_command(device_id)
        else:
            format_type = "encase6" if self.radioButton_e01.isChecked() else "aff"
            return self.build_ewf_command(device_id, format_type)
    
    def get_physical_drive_from_letter(self, drive_letter):
        """Chuyển đổi drive letter (C:) thành physical drive (\\.\PHYSICALDRIVE0)."""
        try:
            if WMI_AVAILABLE:
                c = wmi.WMI()
                for logical_disk in c.Win32_LogicalDisk(DeviceID=drive_letter):
                    for partition in logical_disk.associators("Win32_LogicalDiskToPartition"):
                        for disk in partition.associators("Win32_DiskDriveToDiskPartition"):
                            return disk.DeviceID
            return f"\\\\.\\PHYSICALDRIVE0"  # Default fallback
        except:
            return f"\\\\.\\PHYSICALDRIVE0"

    def build_ewf_command(self, device_id, format_type):
        """Xây dựng dòng lệnh cho công cụ ewfacquire.exe để tạo ảnh E01 hoặc AFF."""
        ewf_path = os.path.join(self.tools_dir, "ewftools-x64", "ewfacquire.exe")
        
        # Lấy đường dẫn và tên file từ giao diện
        output_dir = self.lineEdit_destination_folder.text()
        filename = self.lineEdit_image_filename.text()
        output_path = os.path.join(output_dir, filename)
        
        # Khởi tạo lệnh cơ bản
        cmd = [
            ewf_path,
            "-t", output_path,          # Target path: đường dẫn file ảnh đích
            "-f", format_type,          # Format: định dạng (encase6 cho E01, aff)
            "-u",                       # Unattended mode: chế độ tự động không hỏi
            "-v",                       # Verbose: hiển thị log chi tiết
            "-b", "64",                 # Sectors per chunk: số sector mỗi lần đọc
        ]

        # Thêm thông tin vụ việc
        if self.lineEdit_case_id.text(): cmd.extend(["-C", self.lineEdit_case_id.text()])
        if self.lineEdit_case_description.text(): cmd.extend(["-D", self.lineEdit_case_description.text()])
        if self.lineEdit_investigator.text(): cmd.extend(["-e", self.lineEdit_investigator.text()])

        # Thêm mức độ nén
        compression_map = {0: "none", 1: "fast", 2: "best"}
        compression_level = compression_map.get(self.comboBox_compression.currentIndex(), "fast")
        if compression_level != "none":
             cmd.extend(["-c", compression_level])

        # Thêm kích thước phân mảnh (segment size)
        frag_size = self.spinBox_fragment_size.value()
        if frag_size > 0:
            segment_bytes = frag_size * 1024 * 1024 # Chuyển từ MB sang bytes
            cmd.extend(["-S", str(segment_bytes)])

        # Thêm các tùy chọn băm
        hashes = []
        if self.checkBox_md5.isChecked(): hashes.append("md5")
        if self.checkBox_sha1.isChecked(): hashes.append("sha1")
        if self.checkBox_sha256.isChecked(): hashes.append("sha256")
        if hashes:
            cmd.extend(["-d", ",".join(hashes)])

        # Thêm thiết bị nguồn vào cuối lệnh
        cmd.append(device_id)
        
        return cmd
        
    def build_dd_command(self, device_id):
        """Xây dựng dòng lệnh để tạo ảnh RAW bằng công cụ dc3dd."""
        # Đường dẫn file ảnh đầu ra
        output_path = os.path.join(
            self.lineEdit_destination_folder.text(),
            self.lineEdit_image_filename.text() + ".dd" # Thêm đuôi .dd cho ảnh RAW
        )
        
        # Đường dẫn file log
        log_path = os.path.join(
            self.lineEdit_destination_folder.text(),
            self.lineEdit_image_filename.text() + "_dc3dd.log"
        )
        
        # Xây dựng lệnh dc3dd cơ bản
        cmd = [
            self.dc3dd_exe,
            f"if={device_id}",      # Input device
            f"of={output_path}",    # Output file
            "bufsz=8M",             # Buffer size 8MB để tối ưu tốc độ
            "verb=on",              # Verbose reporting
        ]
        
        # Thêm các tùy chọn hash nếu được chọn
        if self.checkBox_md5.isChecked():
            cmd.append("hash=md5")
        if self.checkBox_sha1.isChecked():
            cmd.append("hash=sha1")
        if self.checkBox_sha256.isChecked():
            cmd.append("hash=sha256")
            
        # Thêm log file để lưu thông tin
        cmd.append(f"log={log_path}")
        
        # Thêm tùy chọn phân mảnh nếu cần
        frag_size = self.spinBox_fragment_size.value()
        if frag_size > 0:
            # dc3dd sử dụng ofsz= cho output file size khi dùng với ofs=
            # Nhưng với of= đơn lẻ, ta cần split thủ công sau
            pass
            
        return cmd

    # -----------------------------------------------------
    # 7. XỬ LÝ QUẢN LÝ DUNG LƯỢNG, TIẾN ĐỘ VÀ KIỂM TRA ĐỦ DISK
    # -----------------------------------------------------

    def get_free_space(self, path):
        """
        Lấy dung lượng trống (free space) của một ổ đĩa dựa trên đường dẫn.
        Hàm này hoạt động trên cả Windows và các hệ điều hành khác.
        """
        try:
            # Kiểm tra nếu hệ điều hành là Windows ('nt' là tên cho Windows)
            if os.name == 'nt':
                import ctypes
                free_bytes = ctypes.c_ulonglong(0)
                # Gọi hàm GetDiskFreeSpaceExW từ kernel32.dll của Windows
                # để lấy dung lượng trống một cách chính xác.
                ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                    ctypes.c_wchar_p(path), None, None, ctypes.pointer(free_bytes)
                )
                return free_bytes.value # Trả về dung lượng trống tính bằng bytes
            else:
                # Đối với các hệ điều hành khác (Linux, macOS)
                st = os.statvfs(path)
                # Tính dung lượng trống bằng cách nhân kích thước block với số block trống
                return st.f_frsize * st.f_bavail
        except Exception as e:
            print(f"Lỗi khi lấy dung lượng trống: {e}")
            return 0 # Trả về 0 nếu có lỗi
            
    def on_format_changed(self):
        """Handle image format selection change"""
        # Enable/disable compression options based on format
        use_compression = self.radioButton_e01.isChecked() or self.radioButton_aff.isChecked()
        self.comboBox_compression.setEnabled(use_compression)
        
        # Update UI based on format
        if self.radioButton_raw.isChecked():
            # Raw format doesn't support compression or encryption
            self.checkBox_ad_encryption.setEnabled(False)
            self.checkBox_ad_encryption.setChecked(False)
        else:
            self.checkBox_ad_encryption.setEnabled(True)
        
        # Update overview if we're on that page
        if self.current_step == 3:
            self.update_overview()

    def on_compression_changed(self, index):
        """Handle compression level change"""
        # Update overview if we're on that page
        if self.current_step == 3:
            self.update_overview()

    def on_fragment_size_changed(self, value):
        """Handle fragment size change"""
        # Update overview if we're on that page
        if self.current_step == 3:
            self.update_overview()

    def on_verification_option_changed(self):
        """Handle verification option changes"""
        # Update overview if we're on that page
        if self.current_step == 3:
            self.update_overview()

    def check_disk_space(self, output_path, source_size):
        """
        Kiểm tra xem ổ đĩa đích có đủ dung lượng trống để lưu file ảnh hay không.
        Đây là một bước quan trọng để tránh thất bại giữa chừng.
        """
        try:
            # Lấy ký tự ổ đĩa từ đường dẫn đích (ví dụ: 'C:\\' từ 'C:\\Output\\image.e01')
            drive = os.path.splitdrive(output_path)[0]
            if not drive:
                # Nếu đường dẫn không có ký tự ổ đĩa, lấy thư mục cha
                drive = os.path.dirname(os.path.abspath(output_path))

            # Lấy dung lượng trống của ổ đĩa đích
            free_space = self.get_free_space(drive)
            
            # Ước tính dung lượng cần thiết dựa trên định dạng ảnh và mức nén
            if self.radioButton_raw.isChecked():
                # Ảnh RAW có kích thước bằng nguồn + 1% dự phòng
                required_space = source_size * 1.01
            else: # Ảnh E01/AFF có nén
                # Sử dụng một bản đồ để ước tính tỉ lệ nén
                compression_map = {
                    0: 1.01,  # Không nén: Cần ~101% dung lượng nguồn
                    1: 0.7,   # Nén nhanh: Ước tính còn ~70%
                    2: 0.5    # Nén tốt nhất: Ước tính còn ~50%
                }
                compression_factor = compression_map.get(self.comboBox_compression.currentIndex(), 1.01)
                required_space = source_size * compression_factor

            # Chuyển đổi sang đơn vị GB để hiển thị cho người dùng
            free_gb = free_space / (1024**3)
            required_gb = required_space / (1024**3)
            
            # So sánh và đưa ra cảnh báo
            if free_space < required_space:
                # Nếu không đủ dung lượng, hiển thị lỗi nghiêm trọng và không cho phép tiếp tục
                QtWidgets.QMessageBox.critical(
                    self, "Không đủ dung lượng",
                    f"Không đủ dung lượng trống trên ổ đích!\n\n"
                    f"Dung lượng trống: {free_gb:.1f} GB\n"
                    f"Dung lượng cần thiết (ước tính): {required_gb:.1f} GB"
                )
                return False # Trả về False để ngăn quá trình bắt đầu
            
            # Nếu dung lượng còn lại rất ít (dưới 10% dự phòng), hiển thị cảnh báo
            elif free_space < required_space * 1.1:
                reply = QtWidgets.QMessageBox.warning(
                    self, "Cảnh báo dung lượng",
                    f"Dung lượng trống trên ổ đích gần với dung lượng cần thiết!\n\n"
                    f"Dung lượng trống: {free_gb:.1f} GB\n"
                    f"Dung lượng cần thiết (ước tính): {required_gb:.1f} GB\n\n"
                    f"Bạn có muốn tiếp tục không?",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                )
                return reply == QtWidgets.QMessageBox.Yes # Chỉ tiếp tục nếu người dùng chọn "Yes"
            
            return True # Trả về True nếu đủ dung lượng
            
        except Exception as e:
            # Nếu có lỗi khi kiểm tra, hiển thị cảnh báo nhưng vẫn cho phép người dùng quyết định
            QtWidgets.QMessageBox.warning(
                self, "Lỗi",
                f"Không thể kiểm tra dung lượng ổ đĩa: {str(e)}\n"
                "Vui lòng đảm bảo có đủ dung lượng trống trước khi tiếp tục."
            )
            return True # Mặc định là cho phép tiếp tục sau cảnh báo lỗi

    def get_device_size(self):
        """
        Lấy tổng dung lượng (tính bằng bytes) của thiết bị nguồn đã được chọn.
        Hàm thử nhiều cách để có được thông tin này.
        """
        try:
            current_row = self.tableWidget_devices.currentRow()
            if current_row >= 0:
                # Cách 1: Thử lấy từ cột "Kích thước" trong bảng (nhanh nhất)
                size_text = self.tableWidget_devices.item(current_row, 2).text()
                if size_text and "GB" in size_text:
                    size_gb = float(size_text.replace("GB", "").strip())
                    return int(size_gb * 1024 * 1024 * 1024)
                
                # Cách 2: Nếu cách 1 thất bại, thử truy vấn lại bằng WMI (chính xác)
                device_id_wmi = self.tableWidget_devices.item(current_row, 0).text() # Lấy DeviceID từ cột Model
                match = re.search(r'(\\\\\.\\[A-Za-z0-9]+)', device_id_wmi)
                if WMI_AVAILABLE and match:
                    c = wmi.WMI()
                    for disk in c.Win32_DiskDrive(DeviceID=match.group(1)):
                        return int(disk.Size) # Trả về kích thước chính xác từ WMI
                
                # Cách 3: Dùng win32file để mở thiết bị và lấy kích thước (cấp thấp)
                device_id_raw = self.tableWidget_devices.item(current_row, 3).text().split(',')[0]
                if WIN32_AVAILABLE and device_id_raw.startswith("\\\\.\\"):
                    try:
                        hDevice = win32file.CreateFile(device_id_raw, win32file.GENERIC_READ,
                                                       win32file.FILE_SHARE_READ | win32file.FILE_SHARE_WRITE,
                                                       None, win32file.OPEN_EXISTING, 0, None)
                        size = win32file.GetFileSize(hDevice)
                        win32file.CloseHandle(hDevice)
                        return size
                    except:
                        pass
            
            return 0 # Trả về 0 nếu không thể xác định
        except Exception as e:
            print(f"Lỗi khi lấy kích thước thiết bị: {e}")
            return 0
               
    # -----------------------------------------------------
    # 8. XỬ LÝ TIẾN TRÌNH (PROCESS), LOG, TIẾN ĐỘ, PAUSE/STOP
    # -----------------------------------------------------

    def prepare_collection(self):
        """
        Chuẩn bị giao diện cho bước cuối cùng (trang tiến trình).
        Hàm này được gọi khi người dùng chuyển đến trang 5.
        """
        # Bật các nút điều khiển quá trình thu thập
        self.pushButton_pause.setEnabled(False) # Tạm thời vô hiệu hóa cho đến khi bắt đầu
        self.pushButton_stop.setEnabled(False)
        self.pushButton_save_log.setEnabled(True)
        
        # Reset lại các hiển thị tiến trình và log
        self.progressBar.setValue(0)
        self.label_errors_val.setText("0")
        self.textBrowser_log.clear()
        
        # Hiển thị tóm tắt cấu hình trong cửa sổ log để người dùng biết sắp làm gì
        if self.radioButton_triage.isChecked():
            self.textBrowser_log.append("<b>✅ Sẵn sàng thu thập Triage</b>")
        else: # Imaging mode
            self.textBrowser_log.append("<b>✅ Sẵn sàng tạo Image</b>")
            
        # Hiển thị dòng lệnh sẽ được thực thi
        command = self.build_command_line()
        self.textBrowser_log.append(f"<br><b>Lệnh sẽ chạy:</b><pre>{' '.join(command)}</pre>")
        self.textBrowser_log.append("\nNhấn 'Bắt đầu Thu thập' để thực thi.")


    def start_collection(self):
        """
        Hàm chính được gọi khi người dùng nhấn nút "Bắt đầu thu thập".
        Nó thực hiện các kiểm tra cuối cùng và bắt đầu tiến trình tương ứng.
        """
        # 1. Kiểm tra quyền Administrator
        if not is_admin():
            QtWidgets.QMessageBox.warning(self, "Yêu cầu quyền Administrator",
                                          "Thu thập dữ liệu cần quyền Administrator.\nVui lòng chạy lại ứng dụng với quyền Administrator.")
            return

        # 2. Kiểm tra các lựa chọn cơ bản
        current_row = self.tableWidget_devices.currentRow()
        if current_row < 0:
            QtWidgets.QMessageBox.warning(self, "Lỗi", "Vui lòng chọn thiết bị nguồn!")
            return
        
        # Reset UI cho quá trình mới
        self.progressBar.setValue(0)
        self.start_time = time.time()
        # Khởi tạo và bắt đầu timer cập nhật tiến độ mỗi giây
        self.update_timer = QtCore.QTimer(self)
        self.update_timer.timeout.connect(self.update_progress_stats)
        self.update_timer.start(1000)

        # 3. Phân nhánh logic dựa trên Triage hay Imaging
        if self.radioButton_triage.isChecked():
            # Nếu là Triage, gọi hàm riêng để bắt đầu
            self.start_triage_collection()
        else:
            # Nếu là Imaging, thực hiện kiểm tra dung lượng và bắt đầu
            source_size = self.get_device_size()
            if source_size == 0:
                QtWidgets.QMessageBox.warning(self, "Lỗi", "Không thể xác định dung lượng thiết bị nguồn!")
                self.update_timer.stop()
                return
            
            # Kiểm tra xem ổ đích có đủ dung lượng không
            if not self.check_disk_space(self.lineEdit_destination_folder.text(), source_size):
                self.update_timer.stop()
                return # Dừng lại nếu không đủ dung lượng

            self.start_imaging_process()

    def start_triage_collection(self):
        """Bắt đầu quá trình thu thập Triage bằng KAPE."""
        try:
            cmd = self.build_command_line() # Lấy dòng lệnh đã được xây dựng
            
            self.textBrowser_log.clear()
            self.textBrowser_log.append("<b>🚀 Bắt đầu thu thập KAPE...</b>")
            self.textBrowser_log.append(f"<b>Lệnh:</b> {' '.join(cmd)}")
            # Đảm bảo thư mục tdest tồn tại trước khi chạy
            try:
                if hasattr(self, 'lineEdit_target_destination'):
                    tdest = self.lineEdit_target_destination.text().strip()
                    if tdest:
                        os.makedirs(tdest, exist_ok=True)
            except Exception:
                pass
            
            # Thiết lập và chạy QProcess cho KAPE
            self.kape_process = QtCore.QProcess(self)
            self.kape_process.setProcessChannelMode(QtCore.QProcess.MergedChannels) # Gộp stdout và stderr
            self.kape_process.readyReadStandardOutput.connect(self.handle_kape_output)
            self.kape_process.finished.connect(self.kape_process_finished)
            
            # KAPE cần chạy từ thư mục chứa nó để tìm đúng các file cấu hình
            kape_dir = os.path.dirname(self.kape_exe)
            self.kape_process.setWorkingDirectory(kape_dir)
            
            self.kape_process.start(cmd[0], cmd[1:]) # Bắt đầu tiến trình
            
            # Cập nhật trạng thái các nút
            self.pushButton_start.setEnabled(False)
            self.pushButton_previous.setEnabled(False)
            self.pushButton_pause.setEnabled(True)
            self.pushButton_stop.setEnabled(True)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể bắt đầu KAPE: {str(e)}")
            self.update_timer.stop()

    def start_imaging_process(self):
        """Bắt đầu quá trình tạo ảnh đĩa (EWF hoặc RAW)."""
        try:
            cmd = self.build_command_line()
            output_dir = self.lineEdit_destination_folder.text()
            os.makedirs(output_dir, exist_ok=True) # Tạo thư mục đích nếu chưa có

            self.textBrowser_log.clear()
            self.textBrowser_log.append("<b>🚀 Bắt đầu tạo ảnh...</b>")
            self.textBrowser_log.append(f"<b>Lệnh:</b> {' '.join(cmd)}")
            
            # Thiết lập và chạy QProcess cho công cụ tạo ảnh
            self.imaging_process = QtCore.QProcess(self)
            self.imaging_process.readyReadStandardOutput.connect(self.handle_imaging_stdout)
            self.imaging_process.readyReadStandardError.connect(self.handle_imaging_stderr)
            self.imaging_process.finished.connect(self.imaging_process_finished)

            self.imaging_process.start(cmd[0], cmd[1:])
            self.imaging_active = True

            # Cập nhật trạng thái các nút
            self.pushButton_start.setEnabled(False)
            self.pushButton_previous.setEnabled(False)
            self.pushButton_pause.setEnabled(True)
            self.pushButton_stop.setEnabled(True)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Lỗi", f"Không thể bắt đầu tạo ảnh: {str(e)}")
            self.update_timer.stop()

    def handle_kape_output(self):
        """Xử lý output từ tiến trình KAPE đang chạy."""
        if hasattr(self, 'kape_process') and self.kape_process:
            output = self.kape_process.readAllStandardOutput().data().decode('utf-8', errors='ignore')
            self.textBrowser_log.append(output)
            
            # Dùng regex để tìm phần trăm tiến độ trong output của KAPE
            match = re.search(r'Progress:\s*(\d+)%', output)
            if match:
                progress = int(match.group(1))
                self.progressBar.setValue(progress)

    def kape_process_finished(self, exit_code, exit_status):
        """Slot được gọi khi tiến trình KAPE kết thúc."""
        if hasattr(self, 'update_timer'): self.update_timer.stop() # Dừng timer cập nhật
        if exit_code == 0:
            self.textBrowser_log.append("<b>✅ Thu thập KAPE hoàn tất thành công!</b>")
            self.progressBar.setValue(100)
        else:
            self.textBrowser_log.append(f"<b>❌ Thu thập KAPE thất bại với mã lỗi: {exit_code}</b>")
        
        # Reset trạng thái các nút
        self.pushButton_start.setEnabled(True)
        self.pushButton_previous.setEnabled(True)
        self.pushButton_pause.setEnabled(False)
        self.pushButton_stop.setEnabled(False)
        # Thông báo wizard (nếu đang chạy workflow) để auto ghi artifact vào DB
        try:
            if hasattr(self, 'wizard_reference'):
                tdest = ''
                try:
                    tdest = self.lineEdit_target_destination.text().strip()
                except Exception:
                    pass
                self.wizard_reference.wizard_collection_finished(
                    "nonvolatile",
                    exit_code == 0,
                    "KAPE triage completed" if exit_code == 0 else f"KAPE triage failed: {exit_code}",
                    tdest or None,
                )
        except Exception:
            pass

        # Thông báo wizard (nếu có) với đường dẫn triage
        if hasattr(self, "wizard_reference"):
            tdest = ""
            try:
                tdest = self.lineEdit_target_destination.text().strip()
            except Exception:
                pass
            self.wizard_reference.wizard_collection_finished(
                "nonvolatile",
                exit_code == 0,
                "KAPE triage completed" if exit_code == 0 else f"KAPE triage failed: {exit_code}",
                tdest or None
            )

    def update_progress_stats(self):
        """Cập nhật các thông số về thời gian và ETA mỗi giây."""
        if self.start_time is None: return

        elapsed = time.time() - self.start_time
        self.label_time_elapsed_val.setText(time.strftime("%H:%M:%S", time.gmtime(elapsed)))
        
        progress = self.progressBar.value()
        # Tính toán thời gian dự kiến hoàn thành (ETA)
        if progress > 0 and elapsed > 1: # Cần có tiến độ và thời gian trôi qua để tính
            total_time_estimated = (elapsed / progress) * 100
            remaining_time = total_time_estimated - elapsed
            if remaining_time > 0:
                self.label_eta_val.setText(time.strftime("%H:%M:%S", time.gmtime(remaining_time)))

    def imaging_process_finished(self, exit_code, exit_status):
        """Slot được gọi khi tiến trình tạo ảnh kết thúc."""
        if hasattr(self, 'update_timer'): self.update_timer.stop()
        self.imaging_active = False
        if exit_code == 0:
            self.textBrowser_log.append("<b>✅ Tạo ảnh hoàn tất thành công!</b>")
            self.progressBar.setValue(100)
        else:
            self.textBrowser_log.append(f"<b>❌ Tạo ảnh thất bại với mã lỗi: {exit_code}</b>")
        
        # Reset trạng thái các nút
        self.pushButton_start.setEnabled(True)
        self.pushButton_previous.setEnabled(True)
        self.pushButton_pause.setEnabled(False)
        self.pushButton_stop.setEnabled(False)

        # Thông báo wizard (nếu có) với thư mục lưu ảnh
        if hasattr(self, "wizard_reference"):
            out_dir = ""
            try:
                out_dir = self.lineEdit_destination_folder.text().strip()
            except Exception:
                pass
            self.wizard_reference.wizard_collection_finished(
                "nonvolatile",
                exit_code == 0,
                "Imaging completed" if exit_code == 0 else f"Imaging failed: {exit_code}",
                out_dir or None
            )

    def handle_imaging_stdout(self):
        """Xử lý output chuẩn (stdout) từ ewfacquire hoặc dc3dd."""
        if hasattr(self, 'imaging_process') and self.imaging_process:
            output = self.imaging_process.readAllStandardOutput().data().decode('utf-8', errors='ignore')
            
            # Kiểm tra xem đang dùng công cụ nào
            if self.radioButton_raw.isChecked():
                # dc3dd xuất thông tin tiến độ dạng:
                # dc3dd: Started at 2024-01-20 10:30:00 +0700
                # dc3dd: Current: 1073741824 bytes (1.0 GB) copied  REM: 00:05:30
                # Tìm bytes đã copy
                match = re.search(r'Current:\s*(\d+)\s*bytes.*copied', output)
                if match:
                    bytes_copied = int(match.group(1))
                    total_bytes = self.get_device_size()
                    if total_bytes > 0:
                        progress = (bytes_copied / total_bytes) * 100
                        self.progressBar.setValue(int(progress))
                        copied_gb = bytes_copied / (1024**3)
                        total_gb = total_bytes / (1024**3)
                        self.label_source_progress_val.setText(f"{copied_gb:.1f} GB / {total_gb:.1f} GB")
                
                # Ghi log output
                if output.strip():
                    self.textBrowser_log.append(output.strip())
            else:
                # ewfacquire xuất log dạng JSON, tìm các key quan trọng
                if "acquiry_percentage" in output:
                    match = re.search(r'acquiry_percentage:\s*(\d+)', output)
                    if match: self.progressBar.setValue(int(match.group(1)))
            # Có thể parse thêm các thông tin khác như tốc độ, dung lượng đã đọc...

    def handle_imaging_stderr(self):
        """Xử lý output lỗi (stderr) từ các công cụ."""
        if hasattr(self, 'imaging_process') and self.imaging_process:
            error_output = self.imaging_process.readAllStandardError().data().decode('utf-8', errors='ignore')
            
            # dc3dd có thể xuất thông tin tiến độ hoặc lỗi ra stderr
            if self.radioButton_raw.isChecked():
                # Tìm sectors đã copy
                match_in = re.search(r'(\d+)\s+sectors in', error_output)
                match_mb = re.search(r'(\d+)\s+MB in', error_output)
                
                if match_in:
                    sectors_copied = int(match_in.group(1))
                    # Giả sử sector size = 512 bytes
                    bytes_copied = sectors_copied * 512
                    total_bytes = self.get_device_size()
                    if total_bytes > 0:
                        progress = (bytes_copied / total_bytes) * 100
                        self.progressBar.setValue(int(progress))
                elif match_mb:
                    mb_copied = int(match_mb.group(1))
                    self.label_source_progress_val.setText(f"{mb_copied/1024:.1f} GB copied")
                
                # Tìm tốc độ nếu có
                speed_match = re.search(r'([\d\.]+)\s+MB/s', error_output)
                if speed_match:
                    speed_mbs = float(speed_match.group(1))
                    self.label_speed_val.setText(f"{speed_mbs:.1f} MB/s")
                    
                # Ghi log
                if error_output.strip():
                    self.textBrowser_log.append(error_output.strip())
            else:
                # Xử lý cho dd thông thường (nếu có)
                # Dùng regex để phân tích dòng tiến độ của 'dd'
                # Ví dụ: "1073741824 bytes (1.1 GB, 1.0 GiB) copied, 10.53 s, 102.0 MB/s"
                match = re.search(r'(\d+)\s+bytes.*copied,.*,\s+([\d\.]+)\s+MB/s', error_output)
                if match:
                    bytes_copied = int(match.group(1))
                    speed_mbs = float(match.group(2))
                    total_bytes = self.get_device_size()
                    if total_bytes > 0:
                        progress = (bytes_copied / total_bytes) * 100
                        self.progressBar.setValue(int(progress))
                        copied_gb = bytes_copied / (1024**3)
                        total_gb = total_bytes / (1024**3)
                        self.label_source_progress_val.setText(f"{copied_gb:.1f} GB / {total_gb:.1f} GB")
                        self.label_speed_val.setText(f"{speed_mbs:.1f} MB/s")
                elif error_output.strip():
                    # Nếu không phải dòng tiến độ, in ra như một lỗi
                    self.textBrowser_log.append(f"<span style='color: red;'>{error_output}</span>")

    def pause_collection(self):
        """
        Tạm dừng hoặc tiếp tục quá trình thu thập thực sự bằng psutil.
        """
        # Chọn process đúng: imaging hoặc kape
        process = None
        if hasattr(self, 'kape_process') and self.kape_process and self.kape_process.state() != QtCore.QProcess.NotRunning:
            process = self.kape_process
        elif hasattr(self, 'imaging_process') and self.imaging_process and self.imaging_process.state() != QtCore.QProcess.NotRunning:
            process = self.imaging_process

        if not process:
            self.textBrowser_log.append("<b>⚠️ Không tìm thấy tiến trình đang chạy để tạm dừng.</b>")
            return

        try:
            pid = process.processId()  # lấy PID của QProcess
            ps_proc = psutil.Process(pid)
            if not self.paused:
                ps_proc.suspend()
                self.paused = True
                self.pushButton_pause.setText("▶️ Tiếp tục")
                self.textBrowser_log.append("<b>⏸️ Đã tạm dừng tiến trình thành công.</b>")
            else:
                ps_proc.resume()
                self.paused = False
                self.pushButton_pause.setText("⏸️ Tạm dừng")
                self.textBrowser_log.append("<b>▶️ Đã tiếp tục tiến trình.</b>")
        except Exception as e:
            self.textBrowser_log.append(f"<b>❌ Lỗi khi tạm dừng/tiếp tục tiến trình: {e}</b>")


    def stop_collection(self):
        """
        Dừng hoàn toàn quá trình thu thập đang chạy, đảm bảo dừng an toàn với psutil.
        """
        process = None
        if hasattr(self, 'kape_process') and self.kape_process and self.kape_process.state() != QtCore.QProcess.NotRunning:
            process = self.kape_process
        elif hasattr(self, 'imaging_process') and self.imaging_process and self.imaging_process.state() != QtCore.QProcess.NotRunning:
            process = self.imaging_process

        if not process:
            self.textBrowser_log.append("<b>⚠️ Không có tiến trình nào để dừng.</b>")
            return

        try:
            pid = process.processId()
            ps_proc = psutil.Process(pid)

            # Trước hết gửi terminate (SIGTERM)
            ps_proc.terminate()
            gone, alive = psutil.wait_procs([ps_proc], timeout=10)
            if alive:
                for p in alive:
                    p.kill()
                self.textBrowser_log.append("<b>⚠️ Buộc dừng tiến trình sau 10 giây.</b>")
            else:
                self.textBrowser_log.append("<b>✅ Đã dừng tiến trình thành công.</b>")
        except Exception as e:
            self.textBrowser_log.append(f"<b>❌ Lỗi khi dừng tiến trình: {e}</b>")

        # Cập nhật lại nút
        self.pushButton_start.setEnabled(True)
        self.pushButton_previous.setEnabled(True)
        self.pushButton_pause.setEnabled(False)
        self.pushButton_stop.setEnabled(False)


    # -----------------------------------------------------
    # 9. CẬP NHẬT UI, TIỆN ÍCH NHỎ, HÀNH ĐỘNG PHỤ TRỢ
    # -----------------------------------------------------

    def save_log(self):
        """Lưu nội dung của cửa sổ log ra một file văn bản."""
        # Mở hộp thoại "Lưu file" của hệ thống
        # Đề xuất một tên file mặc định có dạng: collection_log_YYYYMMDD_HHMMSS.txt
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Lưu nhật ký", 
            f"collection_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt)"
        )
        
        # Nếu người dùng đã chọn một tên file (không nhấn Cancel)
        if filename:
            try:
                # Mở file ở chế độ ghi với mã hóa UTF-8
                with open(filename, 'w', encoding='utf-8') as f:
                    # Ghi toàn bộ nội dung text từ textBrowser vào file
                    f.write(self.textBrowser_log.toPlainText())
                # Thông báo cho người dùng đã lưu thành công
                QtWidgets.QMessageBox.information(self, "Thành công", f"Đã lưu nhật ký vào: {filename}")
            except Exception as e:
                # Nếu có lỗi, thông báo lỗi
                QtWidgets.QMessageBox.warning(self, "Lỗi", f"Không thể lưu nhật ký: {str(e)}")

    def on_device_selection_changed(self):
        """
        Slot được gọi mỗi khi người dùng chọn một thiết bị khác trong bảng.
        Hàm này tự động điền một số thông tin vào các ô khác để tiết kiệm thời gian.
        """
        current_row = self.tableWidget_devices.currentRow()
        if current_row >= 0:
            # Lấy thông tin từ hàng đã chọn
            model_text = self.tableWidget_devices.item(current_row, 0).text()
            partitions_text = self.tableWidget_devices.item(current_row, 3).text()
            
            # Tự động điền nguồn cho Triage (lấy ký tự ổ đĩa đầu tiên)
            source_drive = partitions_text.split(',')[0]
            self.lineEdit_target_source.setText(source_drive)
            
            # Tự động điền nguồn cho Imaging
            self.lineEdit_image_source.setText(model_text)
            
            # Tự động tạo tên file ảnh nếu ô này đang trống
            if not self.lineEdit_image_filename.text():
                # Thay thế các ký tự không hợp lệ trong tên model bằng dấu gạch dưới
                safe_model_name = re.sub(r'[<>:"/\\|?*]', '_', model_text.split('(')[0].strip())
                timestamp = datetime.now().strftime('%Y%m%d-%H%M')
                self.lineEdit_image_filename.setText(f"{safe_model_name}_{timestamp}")

    def browse_target_destination(self):
        """Mở hộp thoại để chọn thư mục đích cho việc thu thập Triage."""
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Chọn thư mục đích cho Triage",
            # Mở hộp thoại tại vị trí hiện tại hoặc thư mục người dùng
            self.lineEdit_target_destination.text() or os.path.expanduser("~")
        )
        if folder:
            self.lineEdit_target_destination.setText(folder)

    def browse_image_destination(self):
        """Mở hộp thoại để chọn thư mục đích cho việc tạo file ảnh."""
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Chọn thư mục đích cho Image",
            self.lineEdit_destination_folder.text() or os.path.expanduser("~")
        )
        if folder:
            self.lineEdit_destination_folder.setText(folder)

    def update_image_path(self):
        """
        Cập nhật đường dẫn xem trước của file ảnh mỗi khi người dùng thay đổi
        thư mục đích hoặc tên file.
        """
        folder = self.lineEdit_destination_folder.text()
        filename = self.lineEdit_image_filename.text()
        
        if folder and filename:
            # Xác định phần mở rộng file dựa trên định dạng đã chọn
            if self.radioButton_e01.isChecked():
                ext = ".E01"
            elif self.radioButton_aff.isChecked():
                ext = ".aff"
            else: # RAW
                ext = ".dd"
                
            # Tạo đường dẫn đầy đủ
            full_path = os.path.join(folder, filename + ext)
            
            # Hiển thị đường dẫn xem trước
            self.label_preview_path.setText(f"File sẽ được lưu tại: {full_path}")
            
            # Kiểm tra xem file đã tồn tại hay chưa và cảnh báo nếu có
            if os.path.exists(full_path):
                self.label_preview_path.setStyleSheet("color: red;") # Đổi màu chữ thành đỏ
                self.label_preview_path.setText(
                    f"⚠️ Cảnh báo: File đã tồn tại tại {full_path}"
                )
            else:
                self.label_preview_path.setStyleSheet("") # Trả về màu chữ mặc định

# ----------------------------------------------------------
# ALIAS CHO TƯƠNG THÍCH (không sửa, giữ nguyên)
# ----------------------------------------------------------
CollectNonvolatileController = NonVolatilePage
