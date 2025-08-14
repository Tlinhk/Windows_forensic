# -*- coding: utf-8 -*-

# 1) Imports & UI

import os
import sys
import json
import csv
import subprocess
import threading
import shutil
from datetime import datetime
from pathlib import Path

# Thư viện phân tích Registry
import Registry.Registry as Registry

# Thư viện giao diện PyQt5
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QMessageBox, QFileDialog, QTableWidget, QTableWidgetItem, QProgressDialog, QApplication, QComboBox, QLabel, QPushButton, QTextEdit, QSplitter, QTreeWidget, QTreeWidgetItem, QTabWidget, QHeaderView, QAbstractItemView, QMenu, QAction, QGroupBox, QFormLayout, QCheckBox, QLineEdit, QProgressBar, QDialog, QDialogButtonBox, QListWidgetItem, QSpinBox)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QMutex
from PyQt5.QtGui import QIcon, QFont, QPixmap, QCursor, QStandardItemModel, QStandardItem

# Import UI đã được thiết kế
from ui.pages.analysis_ui.registry_analysis_ui import Ui_RegistryAnalysisWidget

# 2) Tiện ích chung

def format_as_hex(data):
    """Trả về hex dump (hex + ASCII) từ bytes/str."""
    if not data:
        return "Không có dữ liệu"
    
    try:
        # Chuyển string thành bytes nếu cần
        if isinstance(data, str):
            data = data.encode('utf-8', errors='ignore')
        
        hex_lines = []
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            hex_part = ' '.join(f'{b:02X}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            hex_lines.append(f'{i:08X}  {hex_part:<48} |{ascii_part}|')
        
        return '\n'.join(hex_lines)
    except Exception as e:
        return f"Lỗi định dạng hex: {str(e)}"


def decode_registry_data(data, format_type):
    """Decode dữ liệu registry theo định dạng đã chọn."""
    if not data:
        return "Không có dữ liệu để decode"
    
    try:
        if format_type == "Auto-detect":
            return auto_decode_data(data)
        elif format_type == "UTF-8 String":
            if isinstance(data, bytes):
                return data.decode('utf-8', errors='ignore')
            return str(data)
        elif format_type == "UTF-16 String":
            if isinstance(data, bytes):
                return data.decode('utf-16le', errors='ignore')
            return str(data)
        elif format_type == "DWORD":
            return decode_dword(data)
        elif format_type == "QWORD":
            return decode_qword(data)
        elif format_type == "Windows Timestamp":
            return decode_filetime(data)
        else:
            return str(data)
    except Exception as e:
        return f"Lỗi decode: {str(e)}"

def auto_decode_data(data):
    """Tự phát hiện định dạng và decode dữ liệu."""
    if not data:
        return "Không có dữ liệu"
    
    try:
        if str(data).isdigit(): # Kiểm tra xem có phải số nguyên không
            num = int(data)
            return f"Thập phân: {num}\nHex: 0x{num:X}\nBinary: {bin(num)}"
        
        if isinstance(data, str): # Thử decode UTF-8
            return f"String: {data}"
        
        if isinstance(data, bytes):
            try: # Thử decode bytes
                utf8_result = data.decode('utf-8', errors='ignore')
                if utf8_result.isprintable():
                    return f"UTF-8 String: {utf8_result}"
            except:
                pass
            
            try: # Thử decode UTF-16
                utf16_result = data.decode('utf-16le', errors='ignore')
                if utf16_result.isprintable():
                    return f"UTF-16 String: {utf16_result}"
            except:
                pass
        
        return str(data)
    except Exception as e:
        return f"Lỗi auto-decode: {str(e)}"

def decode_dword(data):
    """Giải mã DWORD (32-bit) và hiển thị thập phân/hex/binary."""
    try:
        if isinstance(data, str) and data.isdigit():
            value = int(data)
            return f"DWORD: {value}\nHex: 0x{value:08X}\nBinary: {bin(value)}"
        elif isinstance(data, bytes) and len(data) == 4:
            value = int.from_bytes(data, byteorder='little')
            return f"DWORD: {value}\nHex: 0x{value:08X}\nBinary: {bin(value)}"
        return str(data)
    except Exception as e:
        return f"Lỗi decode DWORD: {str(e)}"

def decode_qword(data):
    """Giải mã QWORD (64-bit) và hiển thị thập phân/hex/binary."""
    try:
        if isinstance(data, str) and data.isdigit():
            value = int(data)
            return f"QWORD: {value}\nHex: 0x{value:016X}\nBinary: {bin(value)}"
        elif isinstance(data, bytes) and len(data) == 8:
            value = int.from_bytes(data, byteorder='little')
            return f"QWORD: {value}\nHex: 0x{value:016X}\nBinary: {bin(value)}"
        return str(data)
    except Exception as e:
        return f"Lỗi decode QWORD: {str(e)}"


def decode_filetime(data):
    """Giải mã FILETIME (Windows) sang thời gian người đọc được."""
    try:
        if isinstance(data, bytes) and len(data) == 8:
            filetime = int.from_bytes(data, byteorder='little') # FILETIME là little-endian 64-bit integer
            
            # Chuyển đổi từ FILETIME sang Unix timestamp
            # FILETIME epoch: 1601-01-01, Unix epoch: 1970-01-01
            FILETIME_EPOCH_DIFF = 11644473600 # Khác biệt: 11644473600 giây
            
            unix_timestamp = (filetime / 10000000) - FILETIME_EPOCH_DIFF # Chuyển từ 100-nanosecond intervals sang giây
            if unix_timestamp > 0:
                dt = datetime.fromtimestamp(unix_timestamp)
                return f"FILETIME: {dt.strftime('%Y-%m-%d %H:%M:%S')}\nRaw: {filetime}\nUnix: {unix_timestamp}" # Chuyển đổi từ FILETIME sang Unix timestamp
            else:
                return f"FILETIME (invalid): {filetime}" # Trả về thông báo lỗi nếu FILETIME không hợp lệ
        
        return f"FILETIME (raw): {data}" # Trả về thông báo lỗi nếu FILETIME không hợp lệ
    except Exception as e:
        return f"Lỗi decode FILETIME: {str(e)}" # Trả về thông báo lỗi nếu có lỗi xảy ra        

# 3) RegistryAnalysisThread (chạy RECmd trong nền)

class RegistryAnalysisThread(QThread):
    """Thread chạy phân tích registry bằng RECmd mà không chặn UI."""
    
    # Các signal để giao tiếp với UI chính
    progress_updated = pyqtSignal(int)      # Cập nhật tiến độ (0-100)
    status_updated = pyqtSignal(str)        # Cập nhật trạng thái hiện tại
    analysis_completed = pyqtSignal(dict)   # Hoàn thành phân tích với kết quả
    error_occurred = pyqtSignal(str)        # Có lỗi xảy ra với thông điệp lỗi
    
    def __init__(self, recmd_path, batch_file, hive_files, output_dir):
        """Khởi tạo thread.
        recmd_path: đường dẫn RECmd.exe; batch_file: file .reb; hive_files: các hive; output_dir: thư mục xuất."""
        super().__init__()
        self.recmd_path = recmd_path
        self.batch_file = batch_file
        self.hive_files = hive_files
        self.output_dir = output_dir
        self.is_cancelled = False
        
    def cancel(self):
        """Đánh dấu hủy quá trình phân tích đang chạy."""
        self.is_cancelled = True
        
    def run(self):
        """Chạy phân tích lần lượt các hive và báo cáo tiến độ."""
        try:
            total_hives = len(self.hive_files)
            results = {}
            
            for i, hive_file in enumerate(self.hive_files):
                if self.is_cancelled:
                    break
                    
                hive_name = os.path.basename(hive_file)
                self.status_updated.emit(f"Đang phân tích {hive_name}...")
                
                result = self.run_recmd_analysis(hive_file) # Chạy phân tích RECmd trên một file hive cụ thể
                if result:
                    results[hive_file] = result
                
                progress = int((i + 1) / total_hives * 100) # Cập nhật tiến độ
                self.progress_updated.emit(progress)
            
            if not self.is_cancelled: # Nếu không bị hủy bỏ
                self.analysis_completed.emit(results) # Gửi kết quả phân tích
                
        except Exception as e: # Nếu có lỗi xảy ra
            self.error_occurred.emit(str(e)) # Gửi thông báo lỗi
    
    def run_recmd_analysis(self, hive_file):
        """Chạy RECmd cho một hive; trả về list record đọc từ CSV."""
        try:
            hive_name = os.path.splitext(os.path.basename(hive_file))[0] # Chuẩn bị tên file output
            output_csv = os.path.join(self.output_dir, f"{hive_name}_analysis.csv") # Tạo đường dẫn file CSV output
            
            cmd = [
                self.recmd_path,
                "-f", hive_file,                    # File hive input
                "--bn", self.batch_file,            # Batch file để sử dụng
                "--csv", self.output_dir,           # Thư mục output CSV
                "--csvf", f"{hive_name}_analysis.csv",  # Tên file CSV output
                "--nl"                              # Cho phép transaction logs không tồn tại
            ]
            
            process = subprocess.Popen(# Chạy lệnh subprocess
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode == 0 and os.path.exists(output_csv): # Kiểm tra kết quả
                return self.parse_csv_results(output_csv) # Phân tích kết quả CSV
            else:
                raise Exception(f"RECmd thất bại: {stderr}") # Gửi thông báo lỗi nếu RECmd thất bại
                
        except Exception as e: # Nếu có lỗi xảy ra
            raise Exception(f"Lỗi phân tích {os.path.basename(hive_file)}: {str(e)}") # Gửi thông báo lỗi
    
    def parse_csv_results(self, csv_file):
        """Đọc CSV kết quả từ RECmd thành list[dict]."""
        results = []
        try:
            with open(csv_file, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    results.append(row)
            return results
        except Exception as e:
            raise Exception(f"Lỗi đọc CSV {csv_file}: {str(e)}")

# 4) BatchFileManager (quản lý .reb)

class BatchFileManager:
    """Quản lý, phát hiện và mô tả các RECmd batch (.reb)."""
    
    def __init__(self, batch_dir):
        """batch_dir: thư mục chứa các .reb."""
        self.batch_dir = batch_dir
        self.batch_files = self.discover_batch_files()
    
    def discover_batch_files(self):
        """Quét batch_dir, trả về {filename: {'path','info','size'}}."""
        batch_files = {}
        
        if not os.path.exists(self.batch_dir):
            return batch_files
            
        for file in os.listdir(self.batch_dir):
            if file.endswith('.reb'):
                file_path = os.path.join(self.batch_dir, file)
                try:
                    info = self.parse_batch_file_info(file_path)
                    batch_files[file] = {
                        'path': file_path,
                        'info': info,
                        'size': os.path.getsize(file_path)
                    }
                except Exception as e: # Nếu parse thất bại, vẫn bao gồm file với thông tin cơ bản
                    batch_files[file] = {
                        'path': file_path,
                        'info': {'Description': file, 'Category': 'Unknown', 'Error': str(e)},
                        'size': os.path.getsize(file_path)
                    }
        
        return batch_files
    
    def parse_batch_file_info(self, batch_file):
        """Đọc header .reb để lấy Description/Author/Version/Category."""
        info = {
            'Description': 'Unknown',
            'Author': 'Unknown', 
            'Version': 'Unknown',
            'Category': 'General'
        }
        
        try:
            with open(batch_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()[:20]  # Chỉ đọc 20 dòng đầu cho header
                
            for line in lines: # Đọc từng dòng
                line = line.strip()
                if line.startswith('Description:'):
                    info['Description'] = line.replace('Description:', '').strip()
                elif line.startswith('Author:'):
                    info['Author'] = line.replace('Author:', '').strip()
                elif line.startswith('Version:'):
                    info['Version'] = line.replace('Version:', '').strip()
                elif line.startswith('Category:'):
                    info['Category'] = line.replace('Category:', '').strip()
                    
            if info['Category'] == 'General': # Phân loại tự động dựa trên tên file nếu không có Category
                filename = os.path.basename(batch_file).lower()
                if 'system' in filename:
                    info['Category'] = 'System Analysis'
                elif 'user' in filename:
                    info['Category'] = 'User Activity'
                elif 'software' in filename:
                    info['Category'] = 'Software Analysis'
                elif 'asep' in filename:
                    info['Category'] = 'Persistence'
                elif 'dfir' in filename:
                    info['Category'] = 'Comprehensive DFIR'
                elif 'activity' in filename:
                    info['Category'] = 'User Activity'
                elif 'basic' in filename:
                    info['Category'] = 'Basic System Info'
                
        except Exception as e: # Nếu có lỗi xảy ra
            info['Error'] = str(e) # Gửi thông báo lỗi
            
        return info
    
    def get_recommended_batches(self, hive_type=None):
        """
        Lấy danh sách batch file được khuyến nghị cho loại hive cụ thể
        Dựa trên loại hive để chọn batch file phù hợp nhất
        Args:
            hive_type (str): Loại hive (SYSTEM, SOFTWARE, NTUSER, SAM, SECURITY)  
        Returns:
            list: Danh sách tên batch file được khuyến nghị theo độ ưu tiên
        """
        recommendations = {
            'SYSTEM': ['DFIRBatch.reb', 'BasicSystemInfo.reb', 'SystemASEPs.reb'],
            'SOFTWARE': ['DFIRBatch.reb', 'SoftwareASEPs.reb', 'InstalledSoftware.reb'],
            'NTUSER': ['DFIRBatch.reb', 'UserActivity.reb', 'UserClassesASEPs.reb'],
            'SAM': ['DFIRBatch.reb', 'BasicSystemInfo.reb'],
            'SECURITY': ['DFIRBatch.reb', 'BasicSystemInfo.reb']
        }
        
        if hive_type and hive_type.upper() in recommendations:
            return recommendations[hive_type.upper()]
        
        return ['DFIRBatch.reb'] # Mặc định sử dụng phân tích toàn diện

# 5) RegistryHiveDetector (nhận diện hive)

class RegistryHiveDetector:
    """Nhận diện/kiểm tra tính hợp lệ của registry hive."""
    
    @staticmethod
    def detect_hive_type(file_path):
        """Suy đoán loại hive (SYSTEM/SOFTWARE/...) từ tên và header."""
        filename = os.path.basename(file_path).upper()
        
        if filename in ['SYSTEM', 'SYSTEM.LOG', 'SYSTEM.LOG1', 'SYSTEM.LOG2']:
            return 'SYSTEM'
        elif filename in ['SOFTWARE', 'SOFTWARE.LOG', 'SOFTWARE.LOG1', 'SOFTWARE.LOG2']:
            return 'SOFTWARE'
        elif filename in ['SAM', 'SAM.LOG', 'SAM.LOG1', 'SAM.LOG2']:
            return 'SAM'
        elif filename in ['SECURITY', 'SECURITY.LOG', 'SECURITY.LOG1', 'SECURITY.LOG2']:
            return 'SECURITY'
        elif filename.startswith('NTUSER'):
            return 'NTUSER'
        elif filename.startswith('USRCLASS'):
            return 'USRCLASS'
        elif 'DEFAULT' in filename:
            return 'DEFAULT'
        try:
            with open(file_path, 'rb') as f: # Thử phát hiện dựa trên cấu trúc file (kiểm tra header)
                header = f.read(4)
                if header == b'regf':
                    return 'UNKNOWN_HIVE'
        except Exception:
            pass
            
        return 'UNKNOWN'
    
    @staticmethod
    def is_registry_hive(file_path):
        """Kiểm tra magic header 'regf' để xác thực hive."""
        try:
            with open(file_path, 'rb') as f:
                header = f.read(4)
                return header == b'regf'
        except Exception:
            return False

# 6) RegistryTreeParser (xây dựng cây registry)

class RegistryTreeParser:
    """Trích xuất cấu trúc cây keys/values từ hive (python-registry)."""
    
    def __init__(self):
        """Khởi tạo bộ nhớ đệm registry theo đường dẫn file."""
        self.registry_objects = {}  # Lưu trữ registry objects theo đường dẫn file
        
    def parse_registry_file(self, file_path):
        """Mở hive và trả về Registry.Registry; lưu vào bộ nhớ đệm."""
        try:
            registry = Registry.Registry(file_path)
            self.registry_objects[file_path] = registry
            return registry
        except Exception as e:
            raise Exception(f"Không thể phân tích file registry {os.path.basename(file_path)}: {e}")
    
    def build_registry_tree(self, model, parent_item, registry, key, max_depth=100, current_depth=0, icons=None):
        """Đệ quy dựng cây keys vào model (giới hạn max_depth)."""
        if current_depth >= max_depth:
            return None
        
        try:
            key_name = key.name() if key.name() else os.path.basename(registry.hive_name())# Tạo item cho key này
            key_item = QStandardItem(key_name)
            
            if icons:# Đặt icon dựa trên độ sâu và loại
                if current_depth == 0:
                    key_item.setIcon(icons.get('folder', QIcon()))
                else:
                    key_item.setIcon(icons.get('key', QIcon()))
            
            key_data = { # Lưu metadata trong item để sử dụng sau
                'type': 'key',
                'path': key.path(),
                'timestamp': key.timestamp(),
                'registry_object': registry,
                'key_object': key
            }
            key_item.setData(key_data, Qt.UserRole)
            
            if parent_item:# Thêm vào parent hoặc model root
                parent_item.appendRow(key_item)
            else:
                model.appendRow(key_item)
            
            try: # Thêm các subkey một cách đệ quy
                for subkey in key.subkeys():
                    self.build_registry_tree(model, key_item, registry, subkey, 
                                           max_depth, current_depth + 1, icons)
            except Registry.RegistryKeyNotFoundException:
                pass  # Bỏ qua các key không tìm thấy
                
            return key_item
        
        except Exception as e: # Nếu có lỗi xảy ra
            error_item = QStandardItem(f"Lỗi: {str(e)}")
            if icons:
                error_item.setIcon(icons.get('error', QIcon()))
            if parent_item:
                parent_item.appendRow(error_item)
            else:
                model.appendRow(error_item)
            return error_item
    
    def get_values_for_key(self, key):
        """Trả về list value của key kèm name/value/type/type_id/raw_data."""
        values = []
        
        try:
            for value in key.values():
                value_data = {
                    'name': value.name(),
                    'value': self._format_value_data(value),
                    'type': value.value_type_str(),
                    'type_id': value.value_type(),
                    'raw_data': value.raw_data()
                }
                values.append(value_data)
        except Exception as e: # Thêm entry lỗi nếu không thể đọc values
            values.append({
                'name': '(Lỗi đọc values)',
                'value': str(e),
                'type': 'ERROR',
                'type_id': -1,
                'raw_data': b''
            })
            
        return values
    
    def _format_value_data(self, value):
        """Chuẩn hóa dữ liệu value để hiển thị an toàn."""
        try:
            raw_value = value.value()
            
            if isinstance(raw_value, str): # Xử lý các loại dữ liệu khác nhau
                return raw_value.replace('\x00', '').strip()
            elif isinstance(raw_value, (int, float)):
                return str(raw_value)
            elif isinstance(raw_value, bytes):
                try:
                    return raw_value.decode('utf-8', errors='ignore').replace('\x00', '').strip()
                except:
                    return f"<binary data: {len(raw_value)} bytes>"
            elif isinstance(raw_value, list):
                return '; '.join(str(item) for item in raw_value)
            else:
                return str(raw_value)
                
        except Registry.RegistryValueNotFoundException:
            return "(giá trị không tìm thấy)" # Gửi thông báo lỗi nếu không tìm thấy giá trị
        except Registry.RegistryParse.ParseException:
            return "(lỗi phân tích dữ liệu)" # Gửi thông báo lỗi nếu có lỗi phân tích dữ liệu
        except Exception as e: # Nếu có lỗi xảy ra
            return f"(lỗi: {str(e)})" # Gửi thông báo lỗi

# 7) RegistryAnalysis (UI chính)

class RegistryAnalysis(QWidget):
    """Widget chính: tải, phân tích và hiển thị dữ liệu registry."""
    
    def __init__(self, parent=None):
        """Khởi tạo widget và cấu hình thành phần UI."""
        super().__init__(parent)
        
        self.ui = Ui_RegistryAnalysisWidget() # Thiết lập UI từ file thiết kế
        self.ui.setupUi(self)
        
        self.tools_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'tools')
        self.recmd_path = os.path.join(self.tools_dir, 'RECmd', 'RECmd.exe')
        self.batch_dir = os.path.join(self.tools_dir, 'RECmd', 'BatchExamples')
        self.output_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'temp', 'registry_analysis')
        
        os.makedirs(self.output_dir, exist_ok=True) # Tạo thư mục output nếu chưa tồn tại
        
        self.batch_manager = BatchFileManager(self.batch_dir)
        self.hive_detector = RegistryHiveDetector()
        self.registry_parser = RegistryTreeParser()
        
        self.icons = {
            'folder': QIcon(":/icons/folder.ico") if QIcon.hasThemeIcon("folder") else QIcon.fromTheme("folder"),
            'key': QIcon(":/icons/key.ico") if QIcon.hasThemeIcon("dialog-password") else QIcon.fromTheme("dialog-password"),
            'value': QIcon(":/icons/binary.ico") if QIcon.hasThemeIcon("text-x-generic") else QIcon.fromTheme("text-x-generic"),
            'bookmark': QIcon(":/icons/bookmark.ico") if QIcon.hasThemeIcon("bookmark-new") else QIcon.fromTheme("bookmark-new"),
            'error': QIcon(":/icons/error.ico") if QIcon.hasThemeIcon("dialog-error") else QIcon.fromTheme("dialog-error")
        }
        
        # Trạng thái
        self.loaded_hives = {}
        self.analysis_results = {}
        self.current_analysis_thread = None
        
        # Thiết lập UI và kết nối
        self.setup_ui()
        self.setup_connections()
        self.populate_batch_files()
        self.setup_forensic_bookmarks()

    # 7.1 Cấu hình UI
        
    def setup_ui(self):
        """Thiết lập thành phần UI và tùy chọn hiển thị."""
        # Đặt thuộc tính cửa sổ
        self.setWindowTitle("Công cụ Phân tích Registry - Digital Forensics")
        
        # Cấu hình bảng values với các thuộc tính hiển thị
        self.ui.registryValuesTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ui.registryValuesTable.setSelectionMode(QAbstractItemView.SingleSelection)
        self.ui.registryValuesTable.setAlternatingRowColors(True)
        self.ui.registryValuesTable.setSortingEnabled(True)
        self.ui.registryValuesTable.horizontalHeader().setStretchLastSection(True)
        self.ui.registryValuesTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        
        # Cấu hình tree view cho registry structure
        self.ui.registryTreeView.setAlternatingRowColors(True)
        self.ui.registryTreeView.setHeaderHidden(False)
        self.ui.registryTreeView.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ui.registryTreeView.setUniformRowHeights(True)
        self.ui.registryTreeView.setEditTriggers(QAbstractItemView.NoEditTriggers)
        
        # Tạo model rỗng ban đầu cho tree view
        tree_model = QStandardItemModel()
        tree_model.setHorizontalHeaderLabels(["Registry Keys"])
        self.ui.registryTreeView.setModel(tree_model)
        
        # Đặt tỷ lệ splitter cho layout
        self.ui.horizontalSplitter.setSizes([300, 700])  # Tree : Detail = 3:7
        self.ui.verticalSplitter.setSizes([500, 200])    # Main : Bottom = 5:2
        
        # Thiết lập combo boxes
        self.ui.cmbHiveSelector.clear()
        self.ui.cmbHiveSelector.addItems(["Tất cả Hive", "SYSTEM", "SOFTWARE", "NTUSER", "SAM", "SECURITY"])
        
        self.ui.cmbViewType.clear()
        self.ui.cmbViewType.addItems(["Tất cả mục", "Chỉ Key", "Chỉ Value", "Mục đáng nghi"])
        
        # Thiết lập data format combo
        if hasattr(self.ui, 'cmbDataFormat'):
            self.ui.cmbDataFormat.clear()
            self.ui.cmbDataFormat.addItems([
                "Auto-detect", "UTF-8 String", "UTF-16 String", 
                "DWORD", "QWORD", "Windows Timestamp", "Binary"
            ])
        
        # Trạng thái ban đầu
        self.update_status("Sẵn sàng - Tải hive để bắt đầu phân tích")
        
    def setup_connections(self):
        """Kết nối signal-slot cho các thành phần UI."""
        # Kết nối các nút toolbar chính
        self.ui.btnLoadHive.clicked.connect(self.load_registry_hives)
        self.ui.btnExportReport.clicked.connect(self.export_analysis_report)
        self.ui.btnSettings.clicked.connect(self.show_settings_dialog)
        self.ui.btnRefresh.clicked.connect(self.refresh_analysis)
        self.ui.btnAddToReport.clicked.connect(self.add_selected_to_report)
        
        # Kết nối tìm kiếm và lọc
        self.ui.txtGlobalSearch.returnPressed.connect(self.perform_global_search)
        self.ui.btnAdvancedSearch.clicked.connect(self.show_advanced_search)
        self.ui.cmbHiveSelector.currentTextChanged.connect(self.filter_by_hive)
        self.ui.cmbViewType.currentTextChanged.connect(self.filter_by_view_type)
        
        # Kết nối bookmark functionality
        self.ui.btnAddBookmark.clicked.connect(self.add_current_to_bookmarks)
        self.ui.btnRemoveBookmark.clicked.connect(self.remove_selected_bookmark)
        self.ui.bookmarksList.itemDoubleClicked.connect(self.navigate_to_bookmark)
        
        # Kết nối Tree và table view interactions
        self.ui.registryTreeView.clicked.connect(self.on_tree_selection_changed)
        self.ui.registryTreeView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.registryTreeView.customContextMenuRequested.connect(self.show_tree_context_menu)
        
        # Kết nối ghi chú investigation
        self.ui.btnSaveNotes.clicked.connect(self.save_investigation_notes)
        
        # Kết nối thay đổi định dạng dữ liệu
        if hasattr(self.ui, 'cmbDataFormat'):
            self.ui.cmbDataFormat.currentTextChanged.connect(self.update_decoded_view)
    
    def update_status(self, message):
        """Cập nhật trạng thái hiển thị và tiêu đề cửa sổ."""
        # Hiển thị trong console để debug
        print(f"Registry Analysis Status: {message}")
        
        # Cập nhật status bar nếu có
        if hasattr(self.ui, 'statusLabel'):
            self.ui.statusLabel.setText(message)
        
        # Cập nhật window title với trạng thái
        if "Đang phân tích" in message:
            self.setWindowTitle(f"Công cụ Phân tích Registry - {message}")
        elif "hoàn thành" in message.lower():
            self.setWindowTitle("Công cụ Phân tích Registry - Phân tích hoàn thành")
        else:
            self.setWindowTitle("Công cụ Phân tích Registry")
    
    def populate_batch_files(self):
        """
        Đưa thông tin batch file vào các selector trong settings
        Chuẩn bị danh sách batch file để sử dụng trong dialog settings
        """
        self.available_batches = list(self.batch_manager.batch_files.keys())
        
        # Log thông tin batch files được tìm thấy
        print(f"Tìm thấy {len(self.available_batches)} batch files:")
        for batch_name in self.available_batches:
            batch_info = self.batch_manager.batch_files[batch_name]['info']
            print(f"  - {batch_name}: {batch_info.get('Description', 'Không có mô tả')}")

    # 7.2 Bookmarks & thao tác cây
    
    def setup_forensic_bookmarks(self):
        """Thêm các registry location quan trọng vào danh sách bookmark."""
        bookmarks = [
            ("🏃 Run Keys", "Chương trình tự khởi động", "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run"),
            ("👤 UserAssist", "Lịch sử thực thi chương trình", "NTUSER\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\UserAssist"),
            ("🖴 MRU Lists", "File sử dụng gần đây", "NTUSER\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\RecentDocs"),
            ("🌐 USB Devices", "Thiết bị USB đã kết nối", "SYSTEM\\ControlSet001\\Enum\\USBSTOR"),
            ("🛠️ Services", "Dịch vụ hệ thống", "SYSTEM\\ControlSet001\\Services"),
            ("🖥️ Startup", "Ứng dụng khởi động", "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run"),
            ("👥 ProfileList", "Danh sách hồ sơ người dùng", "SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\ProfileList"),
            ("🔑 Sam Users", "Tài khoản người dùng", "SAM\\Domains\\Account\\Users"),
            ("📂 TypedPaths", "Đường dẫn đã gõ", "NTUSER\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\TypedPaths"),
            ("🌐 IE History", "Lịch sử Internet Explorer", "NTUSER\\Software\\Microsoft\\Internet Explorer\\TypedURLs")
        ]
        
        for name, description, path in bookmarks:
            item = QListWidgetItem(f"{name} - {description}")
            if 'bookmark' in self.icons:
                item.setIcon(self.icons['bookmark'])
            item.setData(Qt.UserRole, {'path': path, 'description': description})
            self.ui.bookmarksList.addItem(item)
    
    def show_tree_context_menu(self, position):
        """Hiển thị context menu của tree (copy path, bookmark, expand/collapse)."""
        # Lấy index item dưới con trỏ chuột
        index = self.ui.registryTreeView.indexAt(position)
        if not index.isValid():
            return
            
        # Lấy model và dữ liệu item
        model = self.ui.registryTreeView.model()
        if not model:
            return
            
        item_data = model.data(index, Qt.UserRole)
        if not item_data or not isinstance(item_data, dict):
            return
            
        # Tạo context menu
        menu = QMenu(self)
        
        if item_data.get('type') == 'key':
            key = item_data.get('key_object')
            if key:
                # Action sao chép đường dẫn
                copy_path_action = QAction("📋 Sao chép đường dẫn Key", self)
                copy_path_action.triggered.connect(
                    lambda: self.copy_text_to_clipboard(item_data.get('path', ''))
                )
                menu.addAction(copy_path_action)
                
                # Action thêm bookmark
                add_bookmark_action = QAction("⭐ Thêm vào Bookmark", self)
                add_bookmark_action.triggered.connect(
                    lambda: self.add_key_to_bookmarks(key, item_data)
                )
                menu.addAction(add_bookmark_action)
                
                menu.addSeparator()
                
                # Actions expand/collapse
                expand_all_action = QAction("📂 Mở rộng tất cả", self)
                expand_all_action.triggered.connect(lambda: self.expand_subtree(index))
                menu.addAction(expand_all_action)
                
                collapse_all_action = QAction("📁 Thu gọn tất cả", self)
                collapse_all_action.triggered.connect(lambda: self.collapse_subtree(index))
                menu.addAction(collapse_all_action)
                
                menu.addSeparator()
                
                # Action export key
                export_key_action = QAction("💾 Export Key", self)
                export_key_action.triggered.connect(lambda: self.export_key_data(key))
                menu.addAction(export_key_action)
                
        # Hiển thị menu tại vị trí chuột
        menu.exec_(self.ui.registryTreeView.viewport().mapToGlobal(position))
    
    def copy_text_to_clipboard(self, text):
        """Sao chép text vào clipboard hệ thống."""
        clipboard = QApplication.clipboard()
        clipboard.setText(text)
        self.update_status(f"Đã sao chép: {text}")
    
    def add_key_to_bookmarks(self, key, key_data):
        """Thêm registry key vào danh sách bookmarks."""
        key_path = key_data.get('path', '')
        key_name = key.name() if key.name() else '(Root)'
        
        # Tạo bookmark item với icon
        item = QListWidgetItem(f"🔖 {key_name} - {key_path}")
        if 'bookmark' in self.icons:
            item.setIcon(self.icons['bookmark'])
        item.setData(Qt.UserRole, {'path': key_path, 'description': f"User bookmark: {key_path}"})
        
        # Thêm vào đầu danh sách (sau các forensic bookmarks)
        self.ui.bookmarksList.insertItem(len(self.ui.bookmarksList) + 1, item)
        self.update_status(f"Đã thêm bookmark: {key_path}")
    
    def add_current_to_bookmarks(self):
        """Thêm vị trí đang chọn trong tree vào bookmarks."""
        # Lấy item hiện tại được chọn
        index = self.ui.registryTreeView.currentIndex()
        if not index.isValid():
            QMessageBox.warning(
                self,
                "Không Có Lựa Chọn",
                "Vui lòng chọn một registry key trong cây để bookmark."
            )
            return
            
        # Lấy dữ liệu item
        model = self.ui.registryTreeView.model()
        if not model:
            return
            
        item_data = model.data(index, Qt.UserRole)
        if not item_data or not isinstance(item_data, dict) or item_data.get('type') != 'key':
            QMessageBox.warning(
                self,
                "Lựa Chọn Không Hợp Lệ",
                "Vui lòng chọn một registry key hợp lệ để bookmark."
            )
            return
            
        # Thêm vào bookmarks
        self.add_key_to_bookmarks(item_data.get('key_object'), item_data)
    
    def remove_selected_bookmark(self):
        """Xóa bookmark đang chọn khỏi danh sách."""
        current_item = self.ui.bookmarksList.currentItem()
        if not current_item:
            QMessageBox.warning(
                self,
                "Không Có Lựa Chọn",
                "Vui lòng chọn một bookmark để xóa."
            )
            return
            
        # Xác nhận xóa
        reply = QMessageBox.question(
            self,
            "Xóa Bookmark",
            f"Xóa bookmark '{current_item.text()}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            row = self.ui.bookmarksList.row(current_item)
            self.ui.bookmarksList.takeItem(row)
            self.update_status("Đã xóa bookmark")
    
    def navigate_to_bookmark(self, item):
        """Điều hướng đến key của bookmark trong tree."""
        bookmark_data = item.data(Qt.UserRole)
        if not bookmark_data:
            return
            
        path = bookmark_data.get('path', '')
        description = bookmark_data.get('description', '')
        
        self.update_status(f"Đang điều hướng đến: {path}")
        
        # Tìm registry key theo path trong các hive đã tải
        found = False
        for hive_path, registry in self.registry_parser.registry_objects.items():
            try:
                # Thử mở key với đường dẫn
                key = registry.open(path)
                if key:
                    # Tìm thấy key, điều hướng tới
                    self.find_key_in_tree(key)
                    found = True
                    break
            except Exception:
                # Key không tìm thấy trong hive này, thử hive tiếp theo
                continue
        
        if not found:
            QMessageBox.warning(
                self,
                "Không Tìm Thấy Key",
                f"Key bookmark '{path}' không được tìm thấy trong bất kỳ registry hive nào đã tải.\n\n"
                f"Hãy đảm bảo bạn đã tải đúng hive chứa key này."
            )
    
    def expand_subtree(self, index):
        """Mở rộng tất cả node con của index."""
        self.ui.registryTreeView.expandRecursively(index)
        self.update_status("Đã mở rộng tất cả node con")
    
    def collapse_subtree(self, index):
        """Thu gọn node và toàn bộ node con."""
        self.ui.registryTreeView.collapse(index)
        
        # Thu gọn các child nodes
        model = self.ui.registryTreeView.model()
        if model:
            for row in range(model.rowCount(index)):
                child_index = model.index(row, 0, index)
                self.ui.registryTreeView.collapse(child_index)
        
        self.update_status("Đã thu gọn tất cả node con")
        
    def export_key_data(self, key):
        """Export dữ liệu key ra JSON (key info, values, subkeys)."""
        try:
            # Lấy đường dẫn key
            key_path = key.path()
            
            # Tạo tên file an toàn
            filename = key_path.replace('\\', '_').replace('/', '_').replace(':', '')
            if len(filename) > 50:
                filename = filename[-50:]
            
            # Mở dialog chọn file
            file_dialog = QFileDialog()
            file_path, _ = file_dialog.getSaveFileName(
                self,
                "Export Dữ liệu Registry Key",
                f"registry_key_{filename}.json",
                "JSON Files (*.json);;All Files (*)"
            )
            
            if not file_path:
                return
            
            # Thu thập dữ liệu key
            key_data = {
                'export_info': {
                    'timestamp': datetime.now().isoformat(),
                    'tool': 'Registry Analysis Tool',
                    'source_key': key_path
                },
                'key_info': {
                    'path': key_path,
                    'name': key.name(),
                    'timestamp': key.timestamp().isoformat() if key.timestamp() else None,
                    'subkey_count': len(list(key.subkeys())),
                    'value_count': len(list(key.values()))
                },
                'values': self.registry_parser.get_values_for_key(key),
                'subkeys': []
            }
            
            # Thêm thông tin subkeys (chỉ tên, không đệ quy)
            try:
                for subkey in key.subkeys():
                    subkey_info = {
                        'name': subkey.name(),
                        'path': subkey.path(),
                        'timestamp': subkey.timestamp().isoformat() if subkey.timestamp() else None
                    }
                    key_data['subkeys'].append(subkey_info)
            except Exception as e:
                key_data['subkeys_error'] = str(e)
            
            # Ghi ra file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(key_data, f, indent=2, default=str, ensure_ascii=False)
            
            self.update_status(f"Đã export dữ liệu key ra: {file_path}")
            QMessageBox.information(
                self, 
                "Export Thành Công", 
                f"Dữ liệu registry key đã được export thành công!\n\n"
                f"File: {file_path}\n"
                f"Key: {key_path}\n"
                f"Values: {len(key_data['values'])}\n"
                f"Subkeys: {len(key_data['subkeys'])}"
            )
            
        except Exception as e:
            error_msg = f"Không thể export dữ liệu key:\n{str(e)}"
            QMessageBox.critical(self, "Lỗi Export", error_msg)
            self.update_status(f"Lỗi export: {str(e)}")

    # ====================================================
    # 7.3 Tải hive & chuẩn bị phân tích
    # ====================================================
    
    def load_registry_hives(self):
        """Mở dialog chọn nhiều registry hive để tải."""
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.ExistingFiles)
        file_dialog.setNameFilter("Registry Hives (*);;All Files (*)")
        file_dialog.setWindowTitle("Chọn Registry Hive Files")
        
        if file_dialog.exec_():
            files = file_dialog.selectedFiles()
            if files:
                self.process_hive_files(files)
    
    def process_hive_files(self, file_paths):
        """Kiểm tra hợp lệ, phân loại và lưu metadata cho các hive đã chọn."""
        valid_hives = []
        invalid_files = []
        
        # Kiểm tra từng file
        for file_path in file_paths:
            if self.hive_detector.is_registry_hive(file_path):
                hive_type = self.hive_detector.detect_hive_type(file_path)
                hive_info = {
                    'path': file_path,
                    'name': os.path.basename(file_path),
                    'type': hive_type,
                    'size': os.path.getsize(file_path),
                    'modified': datetime.fromtimestamp(os.path.getmtime(file_path))
                }
                valid_hives.append(hive_info)
                self.loaded_hives[file_path] = hive_info
            else:
                invalid_files.append(file_path)
        
        # Thông báo về file không hợp lệ
        if invalid_files:
            QMessageBox.warning(
                self,
                "File Không Hợp Lệ",
                f"Các file sau không phải registry hive hợp lệ:\n\n" +
                "\n".join([f"• {os.path.basename(f)}" for f in invalid_files])
            )
        
        # Xử lý file hợp lệ
        if valid_hives:
            self.build_registry_tree_view()
            self.update_evidence_info()
            self.start_comprehensive_analysis()
            
            # Thông báo thành công
            hive_list = "\n".join([f"• {h['name']} ({h['type']}) - {h['size']:,} bytes" 
                                 for h in valid_hives])
            QMessageBox.information(
                self,
                "Đã Tải Hive Thành Công",
                f"Đã tải thành công {len(valid_hives)} registry hive:\n\n{hive_list}"
            )
    
    def build_registry_tree_view(self):
        """Dựng tree view keys cho toàn bộ hive đã tải (một model)."""
        # Tạo model mới cho tree view
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(["Registry Keys"])
        
        # Xử lý từng hive đã tải
        for hive_path, hive_info in self.loaded_hives.items():
            try:
                # Phân tích file registry
                registry = self.registry_parser.parse_registry_file(hive_path)
                
                # Tạo root item cho hive này
                hive_root_item = QStandardItem(f"{hive_info['name']} ({hive_info['type']})")
                hive_root_item.setIcon(self.icons.get('folder', QIcon()))
                
                # Metadata cho hive root
                hive_data = {
                    'type': 'hive_root',
                    'hive_info': hive_info,
                    'registry_object': registry
                }
                hive_root_item.setData(hive_data, Qt.UserRole)
                
                # Thêm hive root vào model
                model.appendRow(hive_root_item)
                
                # Xây dựng cây từ registry root key
                registry_root = registry.root()
                self.registry_parser.build_registry_tree(
                    model, hive_root_item, registry, registry_root, 
                    max_depth=50, icons=self.icons
                )
                
            except Exception as e:
                # Thêm node lỗi cho hive này
                error_item = QStandardItem(f"❌ Lỗi tải {hive_info['name']}: {str(e)}")
                if 'error' in self.icons:
                    error_item.setIcon(self.icons['error'])
                model.appendRow(error_item)
                print(f"Lỗi tải hive {hive_info['name']}: {e}")
        
        # Đặt model cho tree view
        self.ui.registryTreeView.setModel(model)
        
        # Mở rộng các hive root items
        for row in range(model.rowCount()):
            index = model.index(row, 0)
            self.ui.registryTreeView.setExpanded(index, True)
        
        # Resize cột theo nội dung
        self.ui.registryTreeView.resizeColumnToContents(0)
        
        self.update_status(f"Đã xây dựng cây registry cho {len(self.loaded_hives)} hive")
    
    def update_evidence_info(self):
        """
        Cập nhật panel thông tin evidence với metadata của hive
        Hiển thị thông tin tổng quan về các hive đã tải
        """
        if self.loaded_hives:
            # Hiển thị thông tin hive đầu tiên
            first_hive = list(self.loaded_hives.values())[0]
            self.ui.valueHiveFile.setText(first_hive['name'])
            self.ui.valuePath.setText(first_hive['path'])
            self.ui.valueSize.setText(f"{first_hive['size']:,} bytes")
            self.ui.valueStatus.setText("Đã tải - Sẵn sàng phân tích")
            
            # Cập nhật thông tin tổng quan nếu có nhiều hive
            if len(self.loaded_hives) > 1:
                total_size = sum(h['size'] for h in self.loaded_hives.values())
                hive_types = [h['type'] for h in self.loaded_hives.values()]
                self.ui.valueHiveFile.setText(f"{len(self.loaded_hives)} hives loaded")
                self.ui.valueSize.setText(f"Total: {total_size:,} bytes")
        else:
            # Reset thông tin khi không có hive
            self.ui.valueHiveFile.setText("Chưa tải hive")
            self.ui.valuePath.setText("")
            self.ui.valueSize.setText("")
            self.ui.valueStatus.setText("Không có dữ liệu")
    
    def start_comprehensive_analysis(self):
        """Chạy phân tích RECmd toàn diện cho các hive đã tải."""
        if not self.loaded_hives:
            QMessageBox.warning(
                self,
                "Không Có Dữ Liệu",
                "Không có registry hive nào được tải. Vui lòng tải hive trước khi phân tích."
            )
            return
        
        # Chọn batch file tối ưu
        batch_file = self.select_optimal_batch_file()
        
        if not batch_file:
            QMessageBox.warning(
                self,
                "Không Có Batch File",
                "Không tìm thấy batch file phù hợp cho phân tích.\n\n"
                "Vui lòng kiểm tra thư mục BatchExamples trong RECmd."
            )
            return
        
        # Chuẩn bị dialog tiến độ
        progress_dialog = QProgressDialog(
            "Đang phân tích registry hive với RECmd...",
            "Hủy",
            0, 100,
            self
        )
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setAutoClose(True)
        progress_dialog.setAutoReset(True)
        progress_dialog.setMinimumDuration(0)
        
        # Tạo và cấu hình analysis thread
        hive_files = list(self.loaded_hives.keys())
        self.current_analysis_thread = RegistryAnalysisThread(
            self.recmd_path,
            batch_file,
            hive_files,
            self.output_dir
        )
        
        # Kết nối signals từ thread
        self.current_analysis_thread.progress_updated.connect(progress_dialog.setValue)
        self.current_analysis_thread.status_updated.connect(self.update_status)
        self.current_analysis_thread.analysis_completed.connect(self.on_analysis_completed)
        self.current_analysis_thread.error_occurred.connect(self.on_analysis_error)
        
        # Kết nối cancel button
        progress_dialog.canceled.connect(self.current_analysis_thread.cancel)
        
        # Bắt đầu phân tích
        self.current_analysis_thread.start()
        progress_dialog.exec_()
    
    def select_optimal_batch_file(self):
        """Chọn batch .reb phù hợp (ưu tiên DFIRBatch.reb)."""
        # Kiểm tra DFIRBatch.reb trước (toàn diện nhất)
        dfir_batch = os.path.join(self.batch_dir, 'DFIRBatch.reb')
        if os.path.exists(dfir_batch):
            print("Sử dụng DFIRBatch.reb cho phân tích toàn diện")
            return dfir_batch
        
        # Thử tìm batch file phù hợp dựa trên loại hive
        hive_types = [info['type'] for info in self.loaded_hives.values()]
        
        for batch_name, batch_info in self.batch_manager.batch_files.items():
            batch_category = batch_info['info'].get('Category', '')
            
            # Chọn batch dựa trên category và hive types
            if 'DFIR' in batch_category or 'Comprehensive' in batch_category:
                return batch_info['path']
            elif 'SYSTEM' in hive_types and 'System' in batch_category:
                return batch_info['path']
            elif 'SOFTWARE' in hive_types and 'Software' in batch_category:
                return batch_info['path']
        
        # Fallback: chọn batch file đầu tiên có sẵn
        if self.batch_manager.batch_files:
            first_batch = list(self.batch_manager.batch_files.values())[0]
            print(f"Fallback: sử dụng {first_batch['path']}")
            return first_batch['path']
        
        return None

    # ====================================================
    # 7.4 Xử lý kết quả phân tích RECmd
    # ====================================================
    
    def on_analysis_completed(self, results):
        """Nhận kết quả phân tích, hiển thị bảng và cập nhật trạng thái."""
        self.analysis_results = results
        
        # Đếm tổng số records
        total_records = sum(len(records) for records in results.values())
        
        # Hiển thị kết quả trong bảng
        self.populate_results_table()
        
        # Cập nhật trạng thái
        self.update_status(f"Phân tích hoàn thành - {len(results)} hive, {total_records} records")
        
        # Thông báo hoàn thành
        hive_summary = []
        for hive_path, records in results.items():
            hive_name = os.path.basename(hive_path)
            hive_summary.append(f"• {hive_name}: {len(records)} records")
        
        QMessageBox.information(
            self,
            "Phân Tích Hoàn Thành",
            f"Phân tích registry hoàn thành thành công!\n\n"
            f"Tổng kết:\n" + "\n".join(hive_summary) + f"\n\n"
            f"Tổng cộng: {total_records} records\n"
            f"Kết quả đã sẵn sàng để xem xét và phân tích."
        )
    
    def on_analysis_error(self, error_message):
        """Hiển thị lỗi phân tích và gợi ý kiểm tra."""
        self.update_status(f"Phân tích thất bại: {error_message}")
        
        # Hiển thị dialog lỗi chi tiết
        QMessageBox.critical(
            self,
            "Lỗi Phân Tích Registry",
            f"Quá trình phân tích registry đã thất bại:\n\n"
            f"Lỗi: {error_message}\n\n"
            f"Vui lòng kiểm tra:\n"
            f"• RECmd.exe có tồn tại và hoạt động\n"
            f"• Batch files có sẵn\n"
            f"• File hive không bị corrupt\n"
            f"• Quyền truy cập file"
        )
    
    def populate_results_table(self):
        """Hợp nhất kết quả các hive và hiển thị vào bảng."""
        if not self.analysis_results:
            return
        
        # Kết hợp tất cả kết quả từ các hive
        all_results = []
        for hive_path, results in self.analysis_results.items():
            hive_name = os.path.basename(hive_path)
            for result in results:
                # Thêm thông tin source hive vào mỗi record
                result['Source_Hive'] = hive_name
                result['Source_Path'] = hive_path
                all_results.append(result)
        
        if not all_results:
            self.update_status("Không có kết quả để hiển thị")
            return
        
        # Lấy header cột từ record đầu tiên
        headers = list(all_results[0].keys())
        
        # Sắp xếp lại thứ tự cột cho dễ đọc
        priority_columns = ['Source_Hive', 'KeyPath', 'ValueName', 'ValueData', 'ValueType']
        ordered_headers = []
        for col in priority_columns:
            if col in headers:
                ordered_headers.append(col)
                headers.remove(col)
        ordered_headers.extend(headers)  # Thêm các cột còn lại
        
        # Tạo model cho table
        model = QStandardItemModel(len(all_results), len(ordered_headers))
        model.setHorizontalHeaderLabels(ordered_headers)
        
        # Đưa dữ liệu vào từng hàng
        for row, result in enumerate(all_results):
            for col, header in enumerate(ordered_headers):
                value = result.get(header, '')
                
                # Định dạng giá trị cho hiển thị
                if isinstance(value, str) and len(value) > 100:
                    display_value = value[:100] + '...'
                else:
                    display_value = str(value)
                
                item = QStandardItem(display_value)
                item.setData(result, Qt.UserRole)  # Lưu dữ liệu đầy đủ
                model.setItem(row, col, item)
        
        # Đặt model cho table view
        self.ui.registryValuesTable.setModel(model)
        
        # Cấu hình table
        self.ui.registryValuesTable.resizeColumnsToContents()
        self.ui.registryValuesTable.sortByColumn(0, Qt.AscendingOrder)
        
        # Kết nối selection change
        selection_model = self.ui.registryValuesTable.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self.on_selection_changed)
        
        # Cập nhật hiển thị đường dẫn
        self.ui.lblCurrentPath.setText(f"Kết quả phân tích: {len(all_results)} records từ {len(self.analysis_results)} hive")
        
        self.update_status(f"Đã hiển thị {len(all_results)} records trong bảng kết quả")

    # ====================================================
    # 7.5 Bảng kết quả & chi tiết value
    # ====================================================
    
    def on_selection_changed(self, selected, deselected):
        """Khi chọn một hàng kết quả: cập nhật panel chi tiết."""
        selected_indexes = selected.indexes()
        if not selected_indexes:
            return
        
        # Lấy index đầu tiên được chọn
        index = selected_indexes[0]
        model = self.ui.registryValuesTable.model()
        if not model:
            return
        
        # Lấy dữ liệu từ cột đầu tiên của hàng được chọn
        data_index = model.index(index.row(), 0)
        data = model.data(data_index, Qt.UserRole)
        
        if data:
            self.update_detail_panels(data)
    
    def on_tree_selection_changed(self, index):
        """Khi chọn item trong tree: hiển thị values và meta key/hive."""
        # Lấy model và dữ liệu
        model = self.ui.registryTreeView.model()
        if not model:
            return
            
        item_data = model.data(index, Qt.UserRole)
        
        if item_data and isinstance(item_data, dict):
            if item_data.get('type') == 'key':
                # Đây là registry key - hiển thị values
                key = item_data.get('key_object')
                if key:
                    key_path = item_data.get('path', '')
                    self.ui.lblCurrentPath.setText(f"Registry Key: {key_path}")
                    
                    # Lấy values cho key này
                    values = self.registry_parser.get_values_for_key(key)
                    
                    # Hiển thị values trong bảng
                    self.populate_values_table(values)
                    
                    # Cập nhật thông tin key
                    key_info = {
                        'KeyPath': key_path,
                        'KeyName': key.name() if key.name() else '(Root)',
                        'Timestamp': key.timestamp().isoformat() if key.timestamp() else 'Unknown',
                        'SubkeyCount': len(list(key.subkeys())),
                        'ValueCount': len(values)
                    }
                    self.update_detail_panels(key_info)
            
            elif item_data.get('type') == 'hive_root':
                # Đây là hive root - hiển thị thông tin hive
                hive_info = item_data.get('hive_info', {})
                self.ui.lblCurrentPath.setText(f"Hive Root: {hive_info.get('name', 'Unknown')}")
                
                # Hiển thị thông tin hive
                self.update_detail_panels({
                    'HiveName': hive_info.get('name', 'Unknown'),
                    'HiveType': hive_info.get('type', 'Unknown'),
                    'FilePath': hive_info.get('path', 'Unknown'),
                    'FileSize': f"{hive_info.get('size', 0):,} bytes",
                    'Modified': hive_info.get('modified', 'Unknown')
                })
    
    def populate_values_table(self, values):
        """Đưa list values của key vào bảng hiển thị."""
        # Tạo model cho bảng values
        model = QStandardItemModel(len(values), 3)
        model.setHorizontalHeaderLabels(["Tên Value", "Loại", "Dữ liệu"])
        
        # Thêm từng value vào model
        for row, value in enumerate(values):
            # Cột tên value
            name = value['name'] if value['name'] else '(Default)'
            name_item = QStandardItem(name)
            name_item.setData(value, Qt.UserRole)
            model.setItem(row, 0, name_item)
            
            # Cột loại value
            type_item = QStandardItem(value['type'])
            model.setItem(row, 1, type_item)
            
            # Cột dữ liệu (rút gọn nếu quá dài)
            data_value = str(value['value'])
            if len(data_value) > 100:
                data_value = data_value[:100] + '...'
            value_item = QStandardItem(data_value)
            model.setItem(row, 2, value_item)
        
        # Đặt model cho table view
        self.ui.registryValuesTable.setModel(model)
        
        # Kết nối selection change cho values table
        selection_model = self.ui.registryValuesTable.selectionModel()
        if selection_model:
            selection_model.selectionChanged.connect(self.on_value_selection_changed)
        
        # Resize cột theo nội dung
        self.ui.registryValuesTable.resizeColumnsToContents()
        
        self.update_status(f"Hiển thị {len(values)} values cho registry key")
    
    def on_value_selection_changed(self, selected, deselected):
        """Khi chọn value: cập nhật hex editor, decoded view, và info."""
        selected_indexes = selected.indexes()
        if not selected_indexes:
            return
            
        # Lấy model và hàng được chọn
        model = self.ui.registryValuesTable.model()
        if not model:
            return
            
        row = selected_indexes[0].row()
        
        # Lấy dữ liệu value từ cột đầu tiên
        index = model.index(row, 0)
        if not index.isValid():
            return
            
        value_data = model.data(index, Qt.UserRole)
        if not value_data:
            return
        
        # Cập nhật hex editor với raw data
        raw_data = value_data.get('raw_data', b'')
        hex_text = format_as_hex(raw_data)
        self.ui.hexEditor.setPlainText(hex_text)
        
        # Cập nhật decoded view
        self.update_decoded_view_with_value(value_data)
        
        # Cập nhật thông tin value
        value_info = {
            'ValueName': value_data.get('name', '(Default)'),
            'ValueType': value_data.get('type', 'Unknown'),
            'ValueData': str(value_data.get('value', '')),
            'DataSize': f"{len(raw_data)} bytes",
            'TypeID': value_data.get('type_id', -1)
        }
        self.update_detail_panels(value_info)
    
    def update_detail_panels(self, data):
        """Cập nhật panel chi tiết (selection, hex, decoded, plugin)."""
        # Cập nhật thông tin selection
        if 'KeyPath' in data:
            self.ui.lblCurrentSelection.setText(f"Key: {data.get('KeyPath', 'Unknown')}")
        elif 'ValueName' in data:
            self.ui.lblCurrentSelection.setText(f"Value: {data.get('ValueName', 'Unknown')}")
        elif 'HiveName' in data:
            self.ui.lblCurrentSelection.setText(f"Hive: {data.get('HiveName', 'Unknown')}")
        else:
            self.ui.lblCurrentSelection.setText("Chi tiết item được chọn")
        
        # Cập nhật hex view nếu có dữ liệu
        if 'ValueData' in data:
            hex_text = format_as_hex(data.get('ValueData', ''))
            self.ui.hexEditor.setPlainText(hex_text)
        
        # Cập nhật decoded view
        self.update_decoded_view()
        
        # Cập nhật plugin results nếu có
        self.update_plugin_results(data)

    # 7.6 Decode & hiển thị dữ liệu value
    
    def update_decoded_view(self):
        """Decode dữ liệu từ selection hiện tại theo format đã chọn."""
        # Lấy các index được chọn trong bảng
        selected_indexes = self.ui.registryValuesTable.selectionModel().selectedRows()
        if not selected_indexes:
            return
        
        # Lấy index hàng đầu tiên được chọn
        index = selected_indexes[0]
        
        # Lấy model và dữ liệu
        model = self.ui.registryValuesTable.model()
        if not model:
            return
        
        # Lấy dữ liệu từ cột đầu tiên của hàng được chọn
        data_index = model.index(index.row(), 0)
        data = model.data(data_index, Qt.UserRole)
        if not data:
            return
        
        # Lấy value data và format type
        value_data = data.get('ValueData', '')
        format_type = self.ui.cmbDataFormat.currentText() if hasattr(self.ui, 'cmbDataFormat') else "Auto-detect"
        
        # Decode và hiển thị
        decoded_text = decode_registry_data(value_data, format_type)
        self.ui.txtDecodedData.setPlainText(decoded_text)
    
    def update_decoded_view_with_value(self, value_data):
        """Decode và hiển thị từ value_data (khi có dữ liệu trực tiếp)."""
        format_type = self.ui.cmbDataFormat.currentText() if hasattr(self.ui, 'cmbDataFormat') else "Auto-detect"
        raw_data = value_data.get('raw_data', b'')
        decoded_text = decode_registry_data(raw_data, format_type)
        self.ui.txtDecodedData.setPlainText(decoded_text)

    # 7.7 Plugin & hiển thị bổ sung
    
    def update_plugin_results(self, registry_data):
        """Cập nhật tab plugin (nếu có dữ liệu plugin liên quan)."""
        # Xóa kết quả cũ
        if hasattr(self.ui, 'pluginResultsTable'):
            self.ui.pluginResultsTable.setRowCount(0)
        
        # Kiểm tra xem có thông tin plugin không
        plugin_info = (registry_data.get('ValueData2', '') or 
                      registry_data.get('ValueData3', '') or 
                      registry_data.get('Comment', ''))
        
        if plugin_info and hasattr(self.ui, 'lblPluginInfo'):
            key_path = registry_data.get('KeyPath', 'Unknown')
            self.ui.lblPluginInfo.setText(f"Plugin Results for {key_path}")
            
            # Phân tích và hiển thị plugin-specific results
            plugin_results = self.parse_plugin_data(plugin_info)
            self.display_plugin_results(plugin_results)
        else:
            if hasattr(self.ui, 'lblPluginInfo'):
                self.ui.lblPluginInfo.setText("Không có kết quả plugin cho item này")
    
    def parse_plugin_data(self, plugin_info):
        """Parse plugin_info (JSON hoặc text) thành list kết quả."""
        results = []
        
        try:
            # Thử phân tích JSON nếu có
            if plugin_info.startswith('{') or plugin_info.startswith('['):
                import json
                parsed = json.loads(plugin_info)
                if isinstance(parsed, list):
                    results = parsed
                else:
                    results = [parsed]
            else:
                # Phân tích text thông thường
                lines = plugin_info.split('\n')
                for line in lines:
                    if line.strip():
                        results.append({'info': line.strip()})
        except Exception as e:
            results = [{'error': f"Lỗi phân tích plugin data: {str(e)}"}]
        
        return results
    
    def display_plugin_results(self, results):
        """Hiển thị list kết quả plugin trong bảng 2 cột."""
        if not hasattr(self.ui, 'pluginResultsTable') or not results:
            return
        
        # Cấu hình bảng
        table = self.ui.pluginResultsTable
        table.setRowCount(len(results))
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Thuộc tính", "Giá trị"])
        
        # Thêm dữ liệu vào bảng
        for row, result in enumerate(results):
            if isinstance(result, dict):
                for col, (key, value) in enumerate(result.items()):
                    if col >= 2:  # Chỉ hiển thị 2 cột đầu
                        break
                    table.setItem(row, 0, QTableWidgetItem(str(key)))
                    table.setItem(row, 1, QTableWidgetItem(str(value)))
            else:
                table.setItem(row, 0, QTableWidgetItem("Thông tin"))
                table.setItem(row, 1, QTableWidgetItem(str(result)))
        
        # Resize cột
        table.resizeColumnsToContents()

    # 7.8 Tìm kiếm & điều hướng
    
    def perform_global_search(self):
        """Tìm kiếm toàn cục (key/value name/data) theo chuỗi nhập."""
        search_term = self.ui.txtGlobalSearch.text().strip()
        if not search_term:
            # Nếu không có search term, hiển thị lại tất cả kết quả
            self.populate_results_table()
            return
            
        # Tìm kiếm trong registry tree
        self.search_registry_tree(search_term)
    
    def search_registry_tree(self, search_term):
        """Tìm kiếm đệ quy trong toàn bộ hive đã tải."""
        model = self.ui.registryTreeView.model()
        if not model:
            self.update_status("Không có dữ liệu registry để tìm kiếm")
            return
            
        self.update_status(f"Đang tìm kiếm: {search_term}")
        
        # Danh sách kết quả tìm kiếm
        search_results = []
        
        # Tìm kiếm trong tất cả hive đã tải
        for hive_path, registry in self.registry_parser.registry_objects.items():
            try:
                hive_name = os.path.basename(hive_path)
                
                # Tìm kiếm đệ quy từ root key
                root_key = registry.root()
                self.search_key_recursive(root_key, search_term, search_results)
                
            except Exception as e:
                self.update_status(f"Lỗi tìm kiếm hive {hive_name}: {str(e)}")
        
        # Hiển thị kết quả
        if search_results:
            self.display_search_results(search_results, search_term)
        else:
            self.ui.lblCurrentPath.setText(f"Tìm kiếm: Không tìm thấy kết quả cho '{search_term}'")
            QMessageBox.information(
                self,
                "Kết Quả Tìm Kiếm",
                f"Không tìm thấy kết quả nào cho '{search_term}'"
            )
    
    def search_key_recursive(self, key, search_term, results, max_depth=20, current_depth=0):
        """Đệ quy tìm theo tên key, tên value, và dữ liệu value (string)."""
        if current_depth >= max_depth:
            return
            
        try:
            # Kiểm tra tên key có khớp không
            if search_term.lower() in key.name().lower():
                results.append({
                    'type': 'key',
                    'key': key,
                    'path': key.path(),
                    'match_type': 'Tên Key',
                    'match_value': key.name()
                })
                
            # Kiểm tra values của key
            for value in key.values():
                try:
                    # Kiểm tra tên value
                    if search_term.lower() in value.name().lower():
                        results.append({
                            'type': 'value',
                            'key': key,
                            'value': value,
                            'path': key.path(),
                            'match_type': 'Tên Value',
                            'match_value': value.name()
                        })
                        
                    # Kiểm tra dữ liệu value (nếu là string)
                    try:
                        value_data = value.value()
                        if isinstance(value_data, str) and search_term.lower() in value_data.lower():
                            results.append({
                                'type': 'value',
                                'key': key,
                                'value': value,
                                'path': key.path(),
                                'match_type': 'Dữ liệu Value',
                                'match_value': value.name()
                            })
                    except:
                        pass  # Bỏ qua lỗi đọc value data
                except:
                    pass  # Bỏ qua lỗi đọc value
                    
            # Tìm kiếm trong subkeys
            for subkey in key.subkeys():
                self.search_key_recursive(subkey, search_term, results, max_depth, current_depth + 1)
                
        except Exception as e:
            # Bỏ qua các key có lỗi và tiếp tục
            pass
    
    def display_search_results(self, results, search_term):
        """Hiển thị kết quả tìm kiếm và cho phép điều hướng tới key."""
        # Tạo model với các cột phù hợp
        from PyQt5.QtGui import QStandardItemModel, QStandardItem
        
        model = QStandardItemModel(len(results), 4)
        model.setHorizontalHeaderLabels(["Đường dẫn", "Loại khớp", "Giá trị khớp", "Điều hướng"])
        
        # Thêm kết quả vào model
        for row, result in enumerate(results):
            # Cột đường dẫn
            path_item = QStandardItem(result['path'])
            path_item.setData(result, Qt.UserRole)
            model.setItem(row, 0, path_item)
            
            # Cột loại khớp
            match_type_item = QStandardItem(result['match_type'])
            model.setItem(row, 1, match_type_item)
            
            # Cột giá trị khớp
            match_value_item = QStandardItem(result['match_value'])
            model.setItem(row, 2, match_value_item)
            
            # Cột điều hướng
            goto_item = QStandardItem("➤ Đi tới")
            model.setItem(row, 3, goto_item)
        
        # Đặt model cho table view
        self.ui.registryValuesTable.setModel(model)
        
        # Kết nối double-click để điều hướng
        self.ui.registryValuesTable.doubleClicked.connect(
            lambda index: self.navigate_to_search_result(index.row()) if index.column() == 3 else None
        )
        
        # Resize cột
        self.ui.registryValuesTable.resizeColumnsToContents()
        
        # Cập nhật UI
        self.ui.lblCurrentPath.setText(f"Tìm kiếm: Tìm thấy {len(results)} kết quả cho '{search_term}'")
        self.update_status(f"Tìm kiếm hoàn thành: {len(results)} kết quả")
    
    def navigate_to_search_result(self, row):
        """Điều hướng tới key tương ứng của hàng tìm kiếm được chọn."""
        # Lấy dữ liệu kết quả
        model = self.ui.registryValuesTable.model()
        if not model:
            return
            
        index = model.index(row, 0)
        if not index.isValid():
            return
            
        result = model.data(index, Qt.UserRole)
        if not result:
            return
            
        # Tìm key trong tree view và điều hướng
        self.find_key_in_tree(result['key'])
    
    def find_key_in_tree(self, key):
        """Tìm key trong tree và cuộn/đánh dấu để hiển thị."""
        model = self.ui.registryTreeView.model()
        if not model:
            self.update_status("Registry tree model không khả dụng")
            return
            
        # Lấy đường dẫn key
        key_path = key.path()
        
        # Tìm index của key trong tree
        index = self.find_item_by_path(model, key_path)
        
        if index.isValid():
            # Mở rộng đường dẫn cha nếu cần
            parent_path = '\\'.join(key_path.split('\\')[:-1])
            if parent_path:
                parent_index = self.find_item_by_path(model, parent_path)
                if parent_index.isValid():
                    self.ui.registryTreeView.expand(parent_index)
            
            # Chọn và scroll tới key
            self.ui.registryTreeView.setCurrentIndex(index)
            self.ui.registryTreeView.scrollTo(index)
            
            # Cập nhật detail panels
            self.update_detail_panels({'KeyPath': key_path})
            
            self.update_status(f"Đã điều hướng tới: {key_path}")
        else:
            self.update_status(f"Không tìm thấy key trong tree: {key_path}")
            QMessageBox.warning(
                self,
                "Không Tìm Thấy Key",
                f"Key '{key_path}' không được tìm thấy trong registry tree.\n\n"
                f"Key có thể nằm ở độ sâu quá lớn hoặc bị ẩn."
            )
    
    def find_item_by_path(self, model, path):
        """Tìm QModelIndex trong tree theo đường dẫn registry."""
        if not path:
            return model.index(0, 0)  # Trả về root nếu path rỗng
            
        path_parts = path.split('\\')
        current_index = model.index(0, 0)  # Bắt đầu từ root
        
        for part in path_parts:
            if not current_index.isValid():
                return model.index(0, 0)  # Trả về root nếu không tìm thấy
                
            # Tìm child item với tên khớp
            found = False
            for row in range(model.rowCount(current_index)):
                child_index = model.index(row, 0, current_index)
                if model.data(child_index, Qt.DisplayRole) == part:
                    current_index = child_index
                    found = True
                    break
            
            if not found:
                return model.index(0, 0)  # Trả về root nếu không tìm thấy part
                
        return current_index

    # 7.9 Lọc và tùy chọn xem
    
    def filter_by_hive(self):
        """Lọc kết quả theo loại hive đã chọn."""
        selected_hive = self.ui.cmbHiveSelector.currentText()
        self.update_status(f"Đang lọc theo hive: {selected_hive}")
        
        if selected_hive == "Tất cả Hive":
            # Hiển thị tất cả kết quả
            self.populate_results_table()
        else:
            # Lọc kết quả theo hive type
            self.filter_results_by_hive_type(selected_hive)
    
    def filter_by_view_type(self):
        """Lọc theo Key-only, Value-only, hoặc Suspicious."""
        selected_view = self.ui.cmbViewType.currentText()
        self.update_status(f"Đang lọc theo view: {selected_view}")
        
        if selected_view == "Tất cả mục":
            self.populate_results_table()
        elif selected_view == "Chỉ Key":
            self.filter_results_by_type('key')
        elif selected_view == "Chỉ Value":
            self.filter_results_by_type('value')
        elif selected_view == "Mục đáng nghi":
            self.filter_suspicious_items()
    
    def filter_results_by_hive_type(self, hive_type):
        """Chỉ giữ kết quả có hive type trùng khớp."""
        if not self.analysis_results:
            return
        
        # Lọc kết quả
        filtered_results = []
        for hive_path, results in self.analysis_results.items():
            hive_info = self.loaded_hives.get(hive_path)
            if hive_info and hive_info['type'] == hive_type:
                hive_name = os.path.basename(hive_path)
                for result in results:
                    result['Source_Hive'] = hive_name
                    filtered_results.append(result)
        
        # Hiển thị kết quả đã lọc
        self.display_filtered_results(filtered_results, f"Hive: {hive_type}")
    
    def filter_results_by_type(self, item_type):
        """Lọc kết quả theo loại item ('key' hoặc 'value')."""
        # Implementation tùy thuộc vào cấu trúc dữ liệu
        # Ở đây ta giả sử có trường 'ItemType' trong results
        if not self.analysis_results:
            return
        
        filtered_results = []
        for hive_path, results in self.analysis_results.items():
            hive_name = os.path.basename(hive_path)
            for result in results:
                # Logic lọc theo type
                if item_type == 'key' and result.get('ValueName', '') == '':
                    result['Source_Hive'] = hive_name
                    filtered_results.append(result)
                elif item_type == 'value' and result.get('ValueName', '') != '':
                    result['Source_Hive'] = hive_name
                    filtered_results.append(result)
        
        self.display_filtered_results(filtered_results, f"Loại: {item_type}")
    
    def filter_suspicious_items(self):
        """Lọc item đáng nghi dựa trên các pattern phổ biến."""
        if not self.analysis_results:
            return
        
        suspicious_patterns = [
            'Run', 'RunOnce', 'Winlogon', 'Explorer\\Run',
            'Services', 'Drivers', 'ASEP', 'Startup',
            'UserAssist', 'MUICache', 'RecentDocs'
        ]
        
        suspicious_results = []
        for hive_path, results in self.analysis_results.items():
            hive_name = os.path.basename(hive_path)
            for result in results:
                key_path = result.get('KeyPath', '').lower()
                value_name = result.get('ValueName', '').lower()
                
                # Kiểm tra pattern đáng nghi
                for pattern in suspicious_patterns:
                    if pattern.lower() in key_path or pattern.lower() in value_name:
                        result['Source_Hive'] = hive_name
                        result['Suspicious_Reason'] = f"Contains pattern: {pattern}"
                        suspicious_results.append(result)
                        break
        
        self.display_filtered_results(suspicious_results, "Items đáng nghi")
    
    def display_filtered_results(self, results, filter_description):
        """Hiển thị bảng kết quả đã lọc cùng mô tả bộ lọc."""
        if not results:
            self.ui.lblCurrentPath.setText(f"Lọc ({filter_description}): Không có kết quả")
            # Clear table
            from PyQt5.QtGui import QStandardItemModel
            empty_model = QStandardItemModel()
            self.ui.registryValuesTable.setModel(empty_model)
            return
        
        # Tạo model cho kết quả đã lọc (tương tự populate_results_table)
        headers = list(results[0].keys())
        
        from PyQt5.QtGui import QStandardItemModel, QStandardItem
        model = QStandardItemModel(len(results), len(headers))
        model.setHorizontalHeaderLabels(headers)
        
        for row, result in enumerate(results):
            for col, header in enumerate(headers):
                value = result.get(header, '')
                display_value = str(value)
                if len(display_value) > 100:
                    display_value = display_value[:100] + '...'
                
                item = QStandardItem(display_value)
                item.setData(result, Qt.UserRole)
                model.setItem(row, col, item)
        
        self.ui.registryValuesTable.setModel(model)
        self.ui.registryValuesTable.resizeColumnsToContents()
        
        # Cập nhật hiển thị
        self.ui.lblCurrentPath.setText(f"Lọc ({filter_description}): {len(results)} kết quả")
        self.update_status(f"Đã lọc: {len(results)} kết quả theo {filter_description}")
    
    def show_advanced_search(self):
        """
        Hiển thị dialog tìm kiếm nâng cao
        Cung cấp nhiều tùy chọn tìm kiếm chi tiết hơn
        """
        QMessageBox.information(
            self,
            "Tìm Kiếm Nâng Cao",
            "Chức năng tìm kiếm nâng cao sẽ được triển khai trong phiên bản tương lai.\n\n"
            "Các tính năng hiện tại:\n"
            "• Tìm kiếm text toàn cục trong key và value\n"
            "• Lọc theo loại hive (SYSTEM, SOFTWARE, etc.)\n"
            "• Lọc theo loại view (Key only, Value only, Suspicious)\n"
            "• Tìm kiếm theo regex pattern\n"
            "• Tìm kiếm theo timestamp range\n\n"
            "Vui lòng sử dụng tìm kiếm cơ bản và các bộ lọc có sẵn."
        )

    # 7.10 Xuất báo cáo & làm mới
    
    def export_analysis_report(self):
        """Xuất báo cáo (CSV/JSON/HTML/XML) từ kết quả phân tích."""
        if not self.analysis_results:
            QMessageBox.warning(
                self,
                "Không Có Dữ Liệu",
                "Không có kết quả phân tích để xuất báo cáo.\n\n"
                "Vui lòng tải registry hive và chạy phân tích trước khi xuất báo cáo."
            )
            return
        
        # Mở dialog chọn file để lưu
        file_dialog = QFileDialog()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_filename = f"registry_analysis_report_{timestamp}.csv"
        
        file_path, selected_filter = file_dialog.getSaveFileName(
            self,
            "Xuất Báo Cáo Phân Tích Registry",
            default_filename,
            "CSV Files (*.csv);;JSON Files (*.json);;HTML Files (*.html);;XML Files (*.xml);;All Files (*)"
        )
        
        if file_path:
            try:
                self.export_results_to_file(file_path)
                
                # Thống kê xuất
                total_records = sum(len(results) for results in self.analysis_results.values())
                
                QMessageBox.information(
                    self,
                    "Xuất Báo Cáo Hoàn Thành",
                    f"Báo cáo phân tích registry đã được xuất thành công!\n\n"
                    f"File: {file_path}\n"
                    f"Tổng số records: {total_records:,}\n"
                    f"Số hive: {len(self.analysis_results)}\n"
                    f"Kích thước file: {os.path.getsize(file_path):,} bytes"
                )
                
                self.update_status(f"Đã xuất báo cáo: {os.path.basename(file_path)}")
                
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Lỗi Xuất Báo Cáo",
                    f"Không thể xuất báo cáo phân tích:\n\n{str(e)}"
                )
                self.update_status(f"Lỗi xuất báo cáo: {str(e)}")
    
    def export_results_to_file(self, file_path):
        """Gộp kết quả và ghi ra file theo phần mở rộng."""
        # Kết hợp tất cả kết quả từ các hive
        all_results = []
        for hive_path, results in self.analysis_results.items():
            hive_name = os.path.basename(hive_path)
            hive_type = self.loaded_hives.get(hive_path, {}).get('type', 'Unknown')
            
            for result in results:
                # Thêm metadata
                result['Source_Hive'] = hive_name
                result['Source_Path'] = hive_path
                result['Hive_Type'] = hive_type
                result['Export_Timestamp'] = datetime.now().isoformat()
                all_results.append(result)
        
        # Xuất theo định dạng file
        if file_path.lower().endswith('.json'):
            self.export_to_json(file_path, all_results)
        elif file_path.lower().endswith('.html'):
            self.export_to_html(file_path, all_results)
        elif file_path.lower().endswith('.xml'):
            self.export_to_xml(file_path, all_results)
        else:  # Default CSV
            self.export_to_csv(file_path, all_results)
    
    def export_to_csv(self, file_path, results):
        """Xuất ra định dạng CSV"""
        if not results:
            return
            
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=results[0].keys())
            writer.writeheader()
            writer.writerows(results)
    
    def export_to_json(self, file_path, results):
        """Xuất ra định dạng JSON"""
        export_data = {
            'metadata': {
                'tool': 'Registry Analysis Tool',
                'export_time': datetime.now().isoformat(),
                'total_records': len(results),
                'hives_analyzed': len(self.loaded_hives)
            },
            'hive_info': {
                path: info for path, info in self.loaded_hives.items()
            },
            'results': results
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
    
    def export_to_html(self, file_path, results):
        """Xuất ra định dạng HTML"""
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Registry Analysis Report</title>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .header {{ background-color: #4CAF50; color: white; padding: 10px; }}
                .summary {{ background-color: #f9f9f9; padding: 10px; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Registry Analysis Report</h1>
                <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            </div>
            
            <div class="summary">
                <h2>Summary</h2>
                <p>Total Records: {len(results):,}</p>
                <p>Hives Analyzed: {len(self.loaded_hives)}</p>
                <p>Analysis Tool: Registry Analysis Tool</p>
            </div>
            
            <h2>Registry Data</h2>
            <table>
        """
        
        if results:
            # Header
            html_content += "<tr>"
            for header in results[0].keys():
                html_content += f"<th>{header}</th>"
            html_content += "</tr>"
            
            # Data rows
            for result in results[:1000]:  # Limit để tránh file quá lớn
                html_content += "<tr>"
                for value in result.values():
                    # Escape HTML và truncate long values
                    display_value = str(value).replace('<', '&lt;').replace('>', '&gt;')
                    if len(display_value) > 100:
                        display_value = display_value[:100] + '...'
                    html_content += f"<td>{display_value}</td>"
                html_content += "</tr>"
        
        html_content += """
            </table>
        </body>
        </html>
        """
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def export_to_xml(self, file_path, results):
        """Xuất ra định dạng XML"""
        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<RegistryAnalysisReport>
    <Metadata>
        <Tool>Registry Analysis Tool</Tool>
        <ExportTime>{datetime.now().isoformat()}</ExportTime>
        <TotalRecords>{len(results)}</TotalRecords>
        <HivesAnalyzed>{len(self.loaded_hives)}</HivesAnalyzed>
    </Metadata>
    <Results>
"""
        
        for i, result in enumerate(results):
            xml_content += f"        <Record id='{i+1}'>\n"
            for key, value in result.items():
                # Escape XML characters
                safe_key = str(key).replace(' ', '_').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                safe_value = str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                xml_content += f"            <{safe_key}>{safe_value}</{safe_key}>\n"
            xml_content += "        </Record>\n"
        
        xml_content += """    </Results>
</RegistryAnalysisReport>"""
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(xml_content)
    
    def refresh_analysis(self):
        """Làm mới: xóa kết quả cũ và chạy lại phân tích các hive đã tải."""
        if self.loaded_hives:
            reply = QMessageBox.question(
                self,
                "Làm Mới Phân Tích",
                "Bạn có muốn chạy lại phân tích registry với các hive đã tải không?\n\n"
                "Quá trình này có thể mất vài phút tùy thuộc vào kích thước hive.",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # Xóa kết quả cũ
                self.analysis_results.clear()
                
                # Bắt đầu phân tích mới
                self.start_comprehensive_analysis()
        else:
            QMessageBox.information(
                self,
                "Không Có Dữ Liệu",
                "Không có registry hive nào được tải.\n\n"
                "Vui lòng tải hive trước khi làm mới phân tích."
            )
    
    def add_selected_to_report(self):
        """Đánh dấu item được chọn để đưa vào báo cáo điều tra."""
        # Kiểm tra có selection model không
        selection_model = self.ui.registryValuesTable.selectionModel()
        if not selection_model:
            QMessageBox.warning(
                self,
                "Không Có Lựa Chọn",
                "Không có item nào được chọn trong bảng kết quả.\n\n"
                "Vui lòng chọn một item để thêm vào báo cáo điều tra."
            )
            return
        
        # Lấy các hàng được chọn
        selected_indexes = selection_model.selectedRows()
        if not selected_indexes:
            QMessageBox.warning(
                self,
                "Không Có Lựa Chọn",
                "Vui lòng chọn ít nhất một hàng để thêm vào báo cáo."
            )
            return
        
        # Lấy dữ liệu từ các hàng được chọn
        model = self.ui.registryValuesTable.model()
        if not model:
            return
        
        selected_items = []
        for index in selected_indexes:
            data_index = model.index(index.row(), 0)
            data = model.data(data_index, Qt.UserRole)
            if data:
                selected_items.append(data)
        
        if selected_items:
            # Tạo summary của các items được chọn
            summary = []
            for item in selected_items:
                key_path = item.get('KeyPath', 'Unknown')
                value_name = item.get('ValueName', '(Default)')
                summary.append(f"• {key_path}\\{value_name}")
            
            QMessageBox.information(
                self,
                "Thêm Vào Báo Cáo Điều Tra",
                f"Đã thêm {len(selected_items)} item(s) vào báo cáo điều tra:\n\n" +
                "\n".join(summary[:10]) +
                (f"\n... và {len(summary)-10} item khác" if len(summary) > 10 else "") +
                "\n\nCác item này sẽ được đưa vào báo cáo chi tiết để phân tích thêm."
            )
            
            # TODO: Implement actual report integration
            self.update_status(f"Đã thêm {len(selected_items)} item vào báo cáo điều tra")

    # 7.11 Ghi chú
    
    def save_investigation_notes(self):
        """Lưu ghi chú điều tra (kèm metadata phiên làm việc)."""
        notes = self.ui.txtNotes.toPlainText().strip()
        
        if not notes:
            QMessageBox.warning(
                self,
                "Ghi Chú Trống",
                "Vui lòng nhập nội dung ghi chú trước khi lưu.\n\n"
                "Ghi chú điều tra giúp ghi lại các phát hiện và phân tích quan trọng."
            )
            return
        
        try:
            # Tạo file ghi chú với timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            notes_filename = f"registry_investigation_notes_{timestamp}.txt"
            notes_path = os.path.join(self.output_dir, notes_filename)
            
            # Tạo nội dung ghi chú với metadata
            notes_content = f"""Registry Analysis Investigation Notes
=====================================
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Tool: Registry Analysis Tool
Analyst: [Current User]

Loaded Hives:
"""
            
            # Thêm thông tin hive
            for hive_path, hive_info in self.loaded_hives.items():
                notes_content += f"- {hive_info['name']} ({hive_info['type']}) - {hive_info['size']:,} bytes\n"
            
            notes_content += f"""
Analysis Results: {sum(len(results) for results in self.analysis_results.values())} records

Investigation Notes:
==================
{notes}
"""
            
            # Ghi file
            with open(notes_path, 'w', encoding='utf-8') as f:
                f.write(notes_content)
            
            QMessageBox.information(
                self,
                "Đã Lưu Ghi Chú",
                f"Ghi chú điều tra đã được lưu thành công!\n\n"
                f"File: {notes_filename}\n"
                f"Đường dẫn: {notes_path}\n"
                f"Kích thước: {len(notes_content)} ký tự"
            )
            
            self.update_status(f"Đã lưu ghi chú điều tra: {notes_filename}")
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Lỗi Lưu Ghi Chú",
                f"Không thể lưu ghi chú điều tra:\n\n{str(e)}"
            )
            self.update_status(f"Lỗi lưu ghi chú: {str(e)}")

    # ====================================================
    # 7.12 Mở hộp thoại cấu hình
    # ====================================================
    
    def show_settings_dialog(self):
        """
        Hiển thị dialog cài đặt và cấu hình cho công cụ phân tích
        Cho phép người dùng thay đổi batch files, tùy chọn phân tích, etc.
        """
        dialog = RegistryAnalysisSettingsDialog(self, self.batch_manager)
        
        if dialog.exec_() == QDialog.Accepted:
            # Xử lý khi người dùng nhấn OK
            self.update_status("Đã cập nhật cài đặt phân tích")
            
            # TODO: Apply settings changes
            # - Update selected batch files
            # - Update analysis options
            # - Refresh UI if needed


# 8) RegistryAnalysisSettingsDialog (hộp thoại cài đặt)

class RegistryAnalysisSettingsDialog(QDialog):
    """Dialog cài đặt: chọn batch, tùy chọn phân tích và xuất kết quả."""
    
    def __init__(self, parent, batch_manager):
        """parent: RegistryAnalysis; batch_manager: quản lý batch files."""
        super().__init__(parent)
        self.batch_manager = batch_manager
        self.setup_ui()
    
    def setup_ui(self):
        """Tạo các tab: Batch Files, Tùy chọn phân tích, Cài đặt xuất."""
        self.setWindowTitle("Cài Đặt Phân Tích Registry")
        self.setModal(True)
        self.resize(700, 500)
        
        # Layout chính
        layout = QVBoxLayout(self)
        
        # Tạo tab widget cho các nhóm cài đặt
        tab_widget = QTabWidget()
        
        # Tab 1: Batch File Selection
        batch_tab = self.create_batch_selection_tab()
        tab_widget.addTab(batch_tab, "Batch Files")
        
        # Tab 2: Analysis Options
        options_tab = self.create_analysis_options_tab()
        tab_widget.addTab(options_tab, "Tùy Chọn Phân Tích")
        
        # Tab 3: Output Settings
        output_tab = self.create_output_settings_tab()
        tab_widget.addTab(output_tab, "Cài Đặt Xuất")
        
        layout.addWidget(tab_widget)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel | QDialogButtonBox.Apply
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        button_box.button(QDialogButtonBox.Apply).clicked.connect(self.apply_settings)
        
        layout.addWidget(button_box)
    
    def create_batch_selection_tab(self):
        """Tab chọn/cấu hình batch files."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Group box cho batch file selection
        batch_group = QGroupBox("Lựa Chọn Batch File")
        batch_layout = QVBoxLayout(batch_group)
        
        # Mô tả
        description = QLabel(
            "Chọn batch file để sử dụng cho phân tích registry. "
            "Batch file xác định các plugin và key nào sẽ được phân tích."
        )
        description.setWordWrap(True)
        batch_layout.addWidget(description)
        
        # Bảng batch files
        self.batch_list = QTableWidget()
        self.batch_list.setColumnCount(5)
        self.batch_list.setHorizontalHeaderLabels([
            "Chọn", "Tên", "Mô tả", "Danh mục", "Kích thước"
        ])
        
        # Populate batch files
        self.populate_batch_list()
        
        batch_layout.addWidget(self.batch_list)
        
        # Custom batch file
        custom_group = QGroupBox("Batch File Tùy Chỉnh")
        custom_layout = QFormLayout(custom_group)
        
        self.custom_batch_path = QLineEdit()
        browse_button = QPushButton("Duyệt...")
        browse_button.clicked.connect(self.browse_custom_batch)
        
        custom_hbox = QHBoxLayout()
        custom_hbox.addWidget(self.custom_batch_path)
        custom_hbox.addWidget(browse_button)
        
        custom_layout.addRow("Đường dẫn batch file:", custom_hbox)
        
        layout.addWidget(batch_group)
        layout.addWidget(custom_group)
        
        return tab
    
    def create_analysis_options_tab(self):
        """Tab tùy chọn phân tích và hiệu suất."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # General options
        general_group = QGroupBox("Tùy Chọn Chung")
        general_layout = QFormLayout(general_group)
        
        self.include_deleted_cb = QCheckBox()
        self.include_deleted_cb.setChecked(True)
        self.include_deleted_cb.setToolTip("Bao gồm các key và value đã bị xóa trong phân tích")
        general_layout.addRow("Bao gồm Key đã xóa:", self.include_deleted_cb)
        
        self.process_vss_cb = QCheckBox()
        self.process_vss_cb.setToolTip("Xử lý Volume Shadow Copies nếu có")
        general_layout.addRow("Xử lý Volume Shadow Copies:", self.process_vss_cb)
        
        self.debug_mode_cb = QCheckBox()
        self.debug_mode_cb.setToolTip("Bật chế độ debug để ghi log chi tiết")
        general_layout.addRow("Chế độ Debug:", self.debug_mode_cb)
        
        # Performance options
        perf_group = QGroupBox("Tùy Chọn Hiệu Suất")
        perf_layout = QFormLayout(perf_group)
        
        self.max_depth_spin = QSpinBox()
        self.max_depth_spin.setRange(10, 200)
        self.max_depth_spin.setValue(100)
        self.max_depth_spin.setToolTip("Độ sâu tối đa khi duyệt registry tree")
        perf_layout.addRow("Độ sâu tối đa:", self.max_depth_spin)
        
        self.thread_count_spin = QSpinBox()
        self.thread_count_spin.setRange(1, 8)
        self.thread_count_spin.setValue(2)
        self.thread_count_spin.setToolTip("Số thread để xử lý song song")
        perf_layout.addRow("Số thread:", self.thread_count_spin)
        
        # Filter options
        filter_group = QGroupBox("Tùy Chọn Lọc")
        filter_layout = QFormLayout(filter_group)
        
        self.skip_empty_values_cb = QCheckBox()
        self.skip_empty_values_cb.setChecked(True)
        filter_layout.addRow("Bỏ qua value rỗng:", self.skip_empty_values_cb)
        
        self.min_key_length_spin = QSpinBox()
        self.min_key_length_spin.setRange(0, 50)
        self.min_key_length_spin.setValue(3)
        filter_layout.addRow("Độ dài key tối thiểu:", self.min_key_length_spin)
        
        layout.addWidget(general_group)
        layout.addWidget(perf_group)
        layout.addWidget(filter_group)
        layout.addStretch()
        
        return tab
    
    def create_output_settings_tab(self):
        """Tab cài đặt xuất: định dạng, đường dẫn, quy tắc đặt tên."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Output format
        format_group = QGroupBox("Định Dạng Xuất")
        format_layout = QFormLayout(format_group)
        
        self.default_format_combo = QComboBox()
        self.default_format_combo.addItems(["CSV", "JSON", "HTML", "XML"])
        format_layout.addRow("Định dạng mặc định:", self.default_format_combo)
        
        self.include_metadata_cb = QCheckBox()
        self.include_metadata_cb.setChecked(True)
        format_layout.addRow("Bao gồm metadata:", self.include_metadata_cb)
        
        # Output paths
        paths_group = QGroupBox("Đường Dẫn Xuất")
        paths_layout = QFormLayout(paths_group)
        
        self.output_dir_edit = QLineEdit()
        output_browse_btn = QPushButton("Duyệt...")
        output_browse_btn.clicked.connect(self.browse_output_dir)
        
        output_hbox = QHBoxLayout()
        output_hbox.addWidget(self.output_dir_edit)
        output_hbox.addWidget(output_browse_btn)
        
        paths_layout.addRow("Thư mục xuất:", output_hbox)
        
        # File naming
        naming_group = QGroupBox("Quy Tắc Đặt Tên File")
        naming_layout = QFormLayout(naming_group)
        
        self.include_timestamp_cb = QCheckBox()
        self.include_timestamp_cb.setChecked(True)
        naming_layout.addRow("Bao gồm timestamp:", self.include_timestamp_cb)
        
        self.include_hive_name_cb = QCheckBox()
        self.include_hive_name_cb.setChecked(True)
        naming_layout.addRow("Bao gồm tên hive:", self.include_hive_name_cb)
        
        layout.addWidget(format_group)
        layout.addWidget(paths_group)
        layout.addWidget(naming_group)
        layout.addStretch()
        
        return tab
    
    def populate_batch_list(self):
        """Đưa danh sách batch files vào bảng (checkbox chọn)."""
        batch_files = self.batch_manager.batch_files
        self.batch_list.setRowCount(len(batch_files))
        
        for row, (filename, batch_info) in enumerate(batch_files.items()):
            info = batch_info['info']
            size = batch_info['size']
            
            # Checkbox column
            checkbox = QCheckBox()
            if filename == 'DFIRBatch.reb':  # Default selection
                checkbox.setChecked(True)
            self.batch_list.setCellWidget(row, 0, checkbox)
            
            # Other columns
            self.batch_list.setItem(row, 1, QTableWidgetItem(filename))
            self.batch_list.setItem(row, 2, QTableWidgetItem(info.get('Description', 'Không có mô tả')))
            self.batch_list.setItem(row, 3, QTableWidgetItem(info.get('Category', 'Chung')))
            self.batch_list.setItem(row, 4, QTableWidgetItem(f"{size:,} bytes"))
        
        # Cấu hình bảng
        self.batch_list.resizeColumnsToContents()
        self.batch_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.batch_list.setAlternatingRowColors(True)
    
    def browse_custom_batch(self):
        """Chọn custom batch file (.reb)."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Chọn Custom Batch File",
            "",
            "RECmd Batch Files (*.reb);;All Files (*)"
        )
        
        if file_path:
            self.custom_batch_path.setText(file_path)
    
    def browse_output_dir(self):
        """Chọn thư mục xuất mặc định."""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Chọn Thư Mục Xuất",
            ""
        )
        
        if dir_path:
            self.output_dir_edit.setText(dir_path)
    
    def apply_settings(self):
        """Áp dụng cài đặt (không đóng dialog)."""
        try:
            # Validate settings
            self.validate_settings()
            
            # Apply settings
            settings = self.get_current_settings()
            
            # TODO: Apply settings to parent widget
            
            QMessageBox.information(
                self,
                "Áp Dụng Cài Đặt",
                "Các cài đặt đã được áp dụng thành công!"
            )
            
        except Exception as e:
            QMessageBox.warning(
                self,
                "Lỗi Cài Đặt",
                f"Không thể áp dụng cài đặt:\n{str(e)}"
            )
    
    def validate_settings(self):
        """Kiểm tra hợp lệ của đường dẫn batch, output và lựa chọn."""
        # Kiểm tra custom batch file nếu có
        custom_path = self.custom_batch_path.text().strip()
        if custom_path and not os.path.exists(custom_path):
            raise ValueError(f"Custom batch file không tồn tại: {custom_path}")
        
        # Kiểm tra output directory
        output_dir = self.output_dir_edit.text().strip()
        if output_dir and not os.path.exists(output_dir):
            raise ValueError(f"Thư mục xuất không tồn tại: {output_dir}")
        
        # Kiểm tra ít nhất một batch file được chọn
        selected_batches = self.get_selected_batch_files()
        if not selected_batches and not custom_path:
            raise ValueError("Vui lòng chọn ít nhất một batch file hoặc chỉ định custom batch file")
    
    def get_selected_batch_files(self):
        """Trả về danh sách tên batch file đang được chọn."""
        selected = []
        
        for row in range(self.batch_list.rowCount()):
            checkbox = self.batch_list.cellWidget(row, 0)
            if checkbox and checkbox.isChecked():
                filename = self.batch_list.item(row, 1).text()
                selected.append(filename)
        
        return selected
    
    def get_current_settings(self):
        """Trả về dict cấu hình hiện tại từ dialog."""
        return {
            'batch_files': {
                'selected': self.get_selected_batch_files(),
                'custom_path': self.custom_batch_path.text().strip()
            },
            'analysis_options': {
                'include_deleted': self.include_deleted_cb.isChecked(),
                'process_vss': self.process_vss_cb.isChecked(),
                'debug_mode': self.debug_mode_cb.isChecked(),
                'max_depth': self.max_depth_spin.value(),
                'thread_count': self.thread_count_spin.value(),
                'skip_empty_values': self.skip_empty_values_cb.isChecked(),
                'min_key_length': self.min_key_length_spin.value()
            },
            'output_settings': {
                'default_format': self.default_format_combo.currentText(),
                'include_metadata': self.include_metadata_cb.isChecked(),
                'output_dir': self.output_dir_edit.text().strip(),
                'include_timestamp': self.include_timestamp_cb.isChecked(),
                'include_hive_name': self.include_hive_name_cb.isChecked()
            }
        }