# -*- coding: utf-8 -*-

import os
import sys
import csv
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

# Registry parsing
try:
    import Registry.Registry as Registry
    REGISTRY_AVAILABLE = True
except ImportError:
    Registry = None
    REGISTRY_AVAILABLE = False
    print("Warning: python-registry not installed. Install with: pip install python-registry")

# PyQt5
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QMessageBox, QFileDialog,
    QTableWidgetItem, QProgressDialog, QApplication,
    QComboBox, QLabel, QPushButton, QTextEdit, QTabWidget,
    QAbstractItemView, QMenu, QAction, QListWidgetItem, QTreeWidgetItem,
    QHeaderView
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QDateTime, QModelIndex
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QIcon, QColor, QFont

# Import UI - CHÚ Ý: import đúng tên file UI
from views.pages.analysis_ui.registry_analysis_ui import Ui_RegistryAnalysisWidget

# ============= Utility Functions (giữ nguyên từ code cũ) =============

def format_as_hex(data):
    """Format data as hex dump with ASCII preview."""
    if not data:
        return "No data"
    
    try:
        if isinstance(data, str):
            data = data.encode("utf-8", errors="ignore")
        
        lines = []
        for offset in range(0, len(data), 16):
            chunk = data[offset:offset+16]
            hex_bytes = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            lines.append(f"{offset:08X}  {hex_bytes:<48} |{ascii_part}|")
        return "\n".join(lines)
    except Exception as e:
        return f"Error formatting hex: {str(e)}"

def decode_registry_data(data, format_type):
    """Decode registry data based on selected format."""
    if not data:
        return "No data to decode"
    
    try:
        if format_type == "Auto-detect":
            return auto_decode_data(data)
        elif format_type == "UTF-16 String":
            if isinstance(data, bytes):
                return data.decode("utf-16le", errors="ignore").rstrip('\x00')
            return str(data)
        elif format_type == "UTF-8 String":
            if isinstance(data, bytes):
                return data.decode("utf-8", errors="ignore").rstrip('\x00')
            return str(data)
        elif format_type == "DWORD (32-bit)":
            return decode_dword(data)
        elif format_type == "QWORD (64-bit)":
            return decode_qword(data)
        elif format_type == "Windows FILETIME":
            return decode_filetime(data)
        elif format_type == "SID":
            return decode_sid(data)
        elif format_type == "GUID":
            return decode_guid(data)
        else:
            return str(data)
    except Exception as e:
        return f"Decode error: {str(e)}"

def auto_decode_data(data):
    """Auto-detect format and decode data."""
    if not data:
        return "No data"
    
    try:
        # Try as number
        if isinstance(data, int):
            return f"Integer: {data}\nHex: 0x{data:X}"
        
        # Try as string
        if isinstance(data, str):
            return f"String: {data}"
        
        # Try as bytes
        if isinstance(data, bytes):
            # Try UTF-16 first (common in Windows)
            try:
                utf16 = data.decode("utf-16le", errors="strict").rstrip('\x00')
                if utf16.isprintable() or '\n' in utf16:
                    return f"UTF-16 String: {utf16}"
            except:
                pass
            
            # Try UTF-8
            try:
                utf8 = data.decode("utf-8", errors="strict").rstrip('\x00')
                if utf8.isprintable():
                    return f"UTF-8 String: {utf8}"
            except:
                pass
            
            # Check for common patterns
            if len(data) == 4:
                value = int.from_bytes(data, byteorder="little")
                return f"DWORD: {value}\nHex: 0x{value:08X}"
            elif len(data) == 8:
                value = int.from_bytes(data, byteorder="little")
                return f"QWORD: {value}\nHex: 0x{value:016X}"
            
            # Default to hex
            return format_as_hex(data)
            
        return str(data)
    except Exception as e:
        return f"Auto-decode error: {str(e)}"

def decode_dword(data):
    """Decode DWORD (32-bit) value."""
    try:
        if isinstance(data, int):
            return f"DWORD: {data}\nHex: 0x{data:08X}\nBinary: {bin(data)}"
        elif isinstance(data, bytes) and len(data) == 4:
            value = int.from_bytes(data, byteorder="little")
            return f"DWORD: {value}\nHex: 0x{value:08X}\nBinary: {bin(value)}"
        return str(data)
    except Exception as e:
        return f"DWORD decode error: {str(e)}"

def decode_qword(data):
    """Decode QWORD (64-bit) value."""
    try:
        if isinstance(data, int):
            return f"QWORD: {data}\nHex: 0x{data:016X}"
        elif isinstance(data, bytes) and len(data) == 8:
            value = int.from_bytes(data, byteorder="little")
            return f"QWORD: {value}\nHex: 0x{value:016X}"
        return str(data)
    except Exception as e:
        return f"QWORD decode error: {str(e)}"

def decode_filetime(data):
    """Decode Windows FILETIME to readable datetime."""
    try:
        if isinstance(data, bytes) and len(data) == 8:
            filetime = int.from_bytes(data, byteorder="little")
            if filetime == 0:
                return "FILETIME: Not set (0)"
            # Convert from Windows epoch (1601) to Unix epoch
            dt = datetime(1601, 1, 1) + timedelta(microseconds=filetime/10)
            return f"FILETIME: {dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\nRaw: {filetime}"
        return f"Invalid FILETIME data"
    except Exception as e:
        return f"FILETIME decode error: {str(e)}"

def decode_sid(data):
    """Decode Windows Security Identifier."""
    try:
        if isinstance(data, bytes) and len(data) >= 8:
            revision = data[0]
            sub_auth_count = data[1]
            authority = int.from_bytes(data[2:8], byteorder="big")
            
            sid_string = f"S-{revision}-{authority}"
            
            for i in range(sub_auth_count):
                if 8 + (i * 4) + 4 <= len(data):
                    sub_auth = int.from_bytes(data[8+(i*4):8+(i*4)+4], byteorder="little")
                    sid_string += f"-{sub_auth}"
            
            return f"SID: {sid_string}"
        return "Invalid SID data"
    except Exception as e:
        return f"SID decode error: {str(e)}"

def decode_guid(data):
    """Decode GUID/UUID."""
    try:
        if isinstance(data, bytes) and len(data) == 16:
            # Format: {XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}
            p1 = data[0:4][::-1].hex()
            p2 = data[4:6][::-1].hex()
            p3 = data[6:8][::-1].hex()
            p4 = data[8:10].hex()
            p5 = data[10:16].hex()
            
            guid = f"{{{p1}-{p2}-{p3}-{p4}-{p5}}}".upper()
            return f"GUID: {guid}"
        return "Invalid GUID data"
    except Exception as e:
        return f"GUID decode error: {str(e)}"

# ============= Registry Analysis Thread (giữ nguyên) =============

class RegistryAnalysisThread(QThread):
    """Thread for running RECmd analysis without blocking UI."""
    
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    analysis_completed = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, recmd_path, batch_file, hive_files, output_dir):
        super().__init__()
        self.recmd_path = recmd_path
        self.batch_file = batch_file
        self.hive_files = hive_files
        self.output_dir = output_dir
        self.is_cancelled = False
        
    def cancel(self):
        self.is_cancelled = True
        
    def run(self):
        try:
            total_hives = len(self.hive_files)
            results = {}
            
            for i, hive_file in enumerate(self.hive_files):
                if self.is_cancelled:
                    break
                    
                hive_name = os.path.basename(hive_file)
                self.status_updated.emit(f"Analyzing {hive_name}...")
                
                result = self.run_recmd_analysis(hive_file)
                if result:
                    results[hive_file] = result
                    
                progress = int((i + 1) / total_hives * 100)
                self.progress_updated.emit(progress)
                
            if not self.is_cancelled:
                self.analysis_completed.emit(results)
                
        except Exception as e:
            self.error_occurred.emit(str(e))
            
    def run_recmd_analysis(self, hive_file):
        """Run RECmd on a single hive file."""
        try:
            hive_name = os.path.splitext(os.path.basename(hive_file))[0]
            output_csv = os.path.join(self.output_dir, f"{hive_name}_analysis.csv")
            
            cmd = [
                self.recmd_path,
                "-f", hive_file,
                "--bn", self.batch_file,
                "--csv", self.output_dir,
                "--csvf", f"{hive_name}_analysis.csv",
                "--nl"
            ]
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode == 0 and os.path.exists(output_csv):
                return self.parse_csv_results(output_csv)
            else:
                raise Exception(f"RECmd failed: {stderr}")
                
        except Exception as e:
            raise Exception(f"Error analyzing {os.path.basename(hive_file)}: {str(e)}")
            
    def parse_csv_results(self, csv_file):
        """Parse CSV results from RECmd."""
        results = []
        try:
            with open(csv_file, "r", encoding="utf-8", errors="ignore") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    results.append(row)
            return results
        except Exception as e:
            raise Exception(f"Error reading CSV {csv_file}: {str(e)}")

# ============= Main Registry Analysis Widget =============

class RegistryAnalysis(QWidget):
    """Registry Analysis Widget - phù hợp với UI mới."""
    
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.ui = Ui_RegistryAnalysisWidget()
        self.ui.setupUi(self)
        
        # Initialize paths
        self._initialize_paths()
        
        # State management
        self.loaded_hives = {}
        self.analysis_results = {}
        self.bookmarks = []
        self.timeline_events = []
        self.current_case_id = None
        self.current_analysis_thread = None
        self.registry_objects = {}  # Cache registry objects
        
        # Models cho QTreeView và QTableView
        self.tree_model = QStandardItemModel()
        self.table_model = QStandardItemModel()
        
        # Setup UI
        self.setup_ui()
        self.setup_connections()
        self.setup_quick_access()
        
        # Load case data if available
        if main_window and hasattr(main_window, 'current_case_id'):
            self.load_case_data(main_window.current_case_id)
            
    def _initialize_paths(self):
        """Initialize tool paths."""
        try:
            from utils.path_utils import get_tools_dir, get_temp_dir
            self.tools_dir = get_tools_dir()
            self.recmd_path = os.path.join(self.tools_dir, "RECmd", "RECmd.exe")
            self.batch_dir = os.path.join(self.tools_dir, "RECmd", "BatchExamples")
            temp_root = get_temp_dir() if callable(get_temp_dir) else "temp"
            self.output_dir = os.path.join(temp_root, "registry_analysis")
        except:
            # Fallback paths
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            self.tools_dir = os.path.join(base_dir, "tools")
            self.recmd_path = os.path.join(self.tools_dir, "RECmd", "RECmd.exe")
            self.batch_dir = os.path.join(self.tools_dir, "RECmd", "BatchExamples")
            self.output_dir = os.path.join(base_dir, "temp", "registry_analysis")
            
        os.makedirs(self.output_dir, exist_ok=True)
        
    def setup_ui(self):
        """Setup UI components."""
        # Set window properties
        self.setWindowTitle("Registry Analysis - Digital Forensics Tool")
        
        # Update header
        self.update_case_info()
        self.update_status("Ready")
        
        # Setup models cho QTreeView
        self.tree_model.setHorizontalHeaderLabels(["Registry Keys"])
        self.ui.registryTree.setModel(self.tree_model)
        self.ui.registryTree.setContextMenuPolicy(Qt.CustomContextMenu)
        
        # Setup model cho QTableView
        self.ui.valuesTable.setModel(self.table_model)
        self.ui.valuesTable.setContextMenuPolicy(Qt.CustomContextMenu)
        
        # Configure hex view
        self.ui.hexView.setReadOnly(True)
        font = QFont("Consolas", 9)
        self.ui.hexView.setFont(font)
        
        # Configure decoded view
        self.ui.decodedView.setReadOnly(True)
        
        # Setup timeline table
        self.setup_timeline_table()
        
        # Set initial splitter sizes
        self.ui.mainSplitter.setSizes([350, 850])
        self.ui.verticalSplitter.setSizes([400, 200])
        
    def setup_connections(self):
        """Connect signals and slots."""
        # Toolbar actions
        self.ui.btnLoadHive.clicked.connect(self.load_registry_hives)
        self.ui.cmbQuickLoad.currentIndexChanged.connect(self.on_quick_load_selected)
        self.ui.txtSearch.textChanged.connect(self.on_search_text_changed)
        self.ui.txtSearch.returnPressed.connect(self.perform_search)
        self.ui.btnSearchOptions.clicked.connect(self.show_search_menu)
        self.ui.btnExport.clicked.connect(self.show_export_menu)
        self.ui.btnTools.clicked.connect(self.show_tools_menu)
        
        # Tree actions
        self.ui.registryTree.clicked.connect(self.on_tree_item_clicked)
        self.ui.registryTree.customContextMenuRequested.connect(self.show_tree_context_menu)
        self.ui.btnExpandAll.clicked.connect(lambda: self.ui.registryTree.expandAll())
        self.ui.btnCollapseAll.clicked.connect(lambda: self.ui.registryTree.collapseAll())
        self.ui.txtTreeFilter.textChanged.connect(self.filter_tree)
        
        # Table selection
        self.ui.valuesTable.selectionModel().selectionChanged.connect(self.on_value_selected)
        
        # Bookmarks
        self.ui.btnAddBookmark.clicked.connect(self.add_bookmark)
        self.ui.btnRemoveBookmark.clicked.connect(self.remove_bookmark)
        self.ui.btnGoToBookmark.clicked.connect(self.go_to_bookmark)
        self.ui.bookmarksList.itemDoubleClicked.connect(self.bookmark_double_clicked)
        
        # Quick Access
        self.ui.quickAccessList.itemDoubleClicked.connect(self.quick_access_double_clicked)
        
        # Format combo
        self.ui.cmbFormat.currentTextChanged.connect(self.update_decoded_view)
        
        # Notes
        self.ui.btnSaveNotes.clicked.connect(self.save_notes)
        
        # Path bar
        self.ui.btnCopyPath.clicked.connect(self.copy_current_path)
        
    def setup_quick_access(self):
        """Setup quick access locations - already populated in UI."""
        pass  # Quick access items already set in UI file
            
    def setup_timeline_table(self):
        """Setup timeline table columns."""
        self.ui.timelineTable.setColumnCount(4)
        self.ui.timelineTable.setHorizontalHeaderLabels(
            ["Timestamp", "Key", "Action", "Details"]
        )
        self.ui.timelineTable.horizontalHeader().setStretchLastSection(True)
        self.ui.timelineTable.setAlternatingRowColors(True)
        self.ui.timelineTable.setSortingEnabled(True)
        
    def load_case_data(self, case_id):
        """Load case-specific data."""
        self.current_case_id = case_id
        self.update_case_info()
        
        # Try to auto-load registry files from case
        try:
            from models.db_manager import DatabaseManager
            db = DatabaseManager()
            db.connect()
            
            case_info = db.get_case_with_investigator(case_id)
            if case_info and case_info.get('archive_path'):
                self.auto_load_case_registry(case_info['archive_path'])
        except Exception as e:
            print(f"Error loading case data: {e}")
            
    def update_case_info(self):
        """Update case information in header."""
        if self.current_case_id:
            self.ui.caseInfoLabel.setText(f"Case ID: {self.current_case_id}")
        else:
            self.ui.caseInfoLabel.setText("Case: Not Selected")
            
    def update_status(self, status, color="green"):
        """Update status indicator."""
        color_map = {
            "green": "#90EE90",
            "yellow": "#FFD700",
            "red": "#FF6B6B"
        }
        self.ui.statusIndicator.setText(f"● {status}")
        self.ui.statusIndicator.setStyleSheet(f"color: {color_map.get(color, '#90EE90')}; font-size: 12px;")
        
        # Also update status bar
        self.ui.statusBar.showMessage(status, 5000)
            
    def auto_load_case_registry(self, archive_path):
        """Auto-load registry files from case archive."""
        archive_path = Path(archive_path)
        if not archive_path.exists():
            return
            
        # Common registry file patterns
        patterns = [
            "**/*SYSTEM", "**/*SOFTWARE", "**/*SAM", 
            "**/*SECURITY", "**/*NTUSER.DAT", "**/*UsrClass.dat"
        ]
        
        registry_files = []
        for pattern in patterns:
            registry_files.extend(archive_path.glob(pattern))
            
        if registry_files:
            # Update quick load combo
            self.ui.cmbQuickLoad.clear()
            self.ui.cmbQuickLoad.addItem("Quick Load...")
            
            for file in registry_files[:10]:  # Limit to 10 files
                self.ui.cmbQuickLoad.addItem(file.name, str(file))
                
            self.update_status(f"Found {len(registry_files)} registry files", "green")
            
    def load_registry_hives(self):
        """Load registry hive files."""
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.ExistingFiles)
        file_dialog.setNameFilter("Registry Hives (*);;All Files (*)")
        file_dialog.setWindowTitle("Select Registry Hive Files")
        
        if file_dialog.exec_():
            files = file_dialog.selectedFiles()
            if files:
                self.process_hive_files(files)
                
    def process_hive_files(self, file_paths):
        """Process and load hive files."""
        if not REGISTRY_AVAILABLE:
            QMessageBox.warning(
                self,
                "Missing Dependency",
                "python-registry library is not installed.\n"
                "Please install it with: pip install python-registry"
            )
            return
            
        valid_hives = []
        
        for file_path in file_paths:
            try:
                # Parse registry file
                registry = Registry.Registry(file_path)
                self.registry_objects[file_path] = registry
                
                hive_info = {
                    "path": file_path,
                    "name": os.path.basename(file_path),
                    "type": self.detect_hive_type(file_path),
                    "size": os.path.getsize(file_path),
                    "modified": datetime.fromtimestamp(os.path.getmtime(file_path)),
                    "registry": registry
                }
                
                valid_hives.append(hive_info)
                self.loaded_hives[file_path] = hive_info
                
            except Exception as e:
                print(f"Error loading {file_path}: {e}")
                
        if valid_hives:
            self.build_registry_tree()
            self.update_timeline()
            self.update_status(f"Loaded {len(valid_hives)} hive(s)", "green")
            
            # Start analysis
            self.start_comprehensive_analysis()
            
    def detect_hive_type(self, file_path):
        """Detect hive type from filename."""
        filename = os.path.basename(file_path).upper()
        
        if "SYSTEM" in filename:
            return "SYSTEM"
        elif "SOFTWARE" in filename:
            return "SOFTWARE"
        elif "SAM" in filename:
            return "SAM"
        elif "SECURITY" in filename:
            return "SECURITY"
        elif "NTUSER" in filename:
            return "NTUSER"
        elif "USRCLASS" in filename:
            return "USRCLASS"
        elif "DEFAULT" in filename:
            return "DEFAULT"
        else:
            return "UNKNOWN"
            
    def build_registry_tree(self):
        """Build registry tree view với QStandardItemModel."""
        self.tree_model.clear()
        self.tree_model.setHorizontalHeaderLabels(["Registry Keys"])
        
        for hive_path, hive_info in self.loaded_hives.items():
            # Create hive root item
            hive_item = QStandardItem(f"{hive_info['name']} ({hive_info['type']})")
            hive_item.setData({
                "type": "hive",
                "path": hive_path,
                "info": hive_info
            }, Qt.UserRole)
            
            self.tree_model.appendRow(hive_item)
            
            # Add registry keys
            try:
                registry = hive_info['registry']
                root = registry.root()
                self.add_key_to_tree(hive_item, root, registry)
            except Exception as e:
                error_item = QStandardItem(f"Error: {str(e)}")
                hive_item.appendRow(error_item)
                
        # Expand first level
        self.ui.registryTree.expandToDepth(0)
        
    def add_key_to_tree(self, parent_item, key, registry, depth=0, max_depth=50):
        """Recursively add registry keys to tree."""
        if depth >= max_depth:
            return
            
        try:
            # Create item for this key
            key_name = key.name() if key.name() else "Root"
            key_item = QStandardItem(key_name)
            key_item.setData({
                "type": "key",
                "key": key,
                "path": key.path(),
                "registry": registry
            }, Qt.UserRole)
            
            parent_item.appendRow(key_item)
            
            # Add subkeys
            for subkey in key.subkeys():
                self.add_key_to_tree(key_item, subkey, registry, depth + 1, max_depth)
                
        except Exception as e:
            pass  # Silently skip problematic keys
            
    def on_tree_item_clicked(self, index):
        """Handle tree item click."""
        item = self.tree_model.itemFromIndex(index)
        if not item:
            return
            
        data = item.data(Qt.UserRole)
        if not data:
            return
            
        if data["type"] == "key":
            # Show key values
            self.show_key_values(data["key"])
            
            # Update path
            self.ui.txtCurrentPath.setText(data["path"])
            
            # Update analysis
            self.analyze_key(data["key"], data["path"])
            
        elif data["type"] == "hive":
            # Show hive info
            self.show_hive_info(data["info"])
            
    def show_key_values(self, key):
        """Display values for selected key in QTableView."""
        # Clear table model
        self.table_model.clear()
        self.table_model.setHorizontalHeaderLabels(["Name", "Type", "Data"])
        
        try:
            values = []
            for value in key.values():
                values.append({
                    "name": value.name() if value.name() else "(Default)",
                    "type": value.value_type_str(),
                    "data": self.format_value_data(value),
                    "raw_data": value.raw_data()
                })
                
            # Populate model
            for val in values:
                row = []
                name_item = QStandardItem(val["name"])
                name_item.setData(val["raw_data"], Qt.UserRole)  # Store raw data
                row.append(name_item)
                row.append(QStandardItem(val["type"]))
                row.append(QStandardItem(str(val["data"])))
                self.table_model.appendRow(row)
                
            # Auto-resize columns
            self.ui.valuesTable.resizeColumnsToContents()
            
        except Exception as e:
            print(f"Error showing values: {e}")
            
    def format_value_data(self, value):
        """Format value data for display."""
        try:
            data = value.value()
            if isinstance(data, str):
                return data.replace('\x00', '').strip()
            elif isinstance(data, (int, float)):
                return str(data)
            elif isinstance(data, bytes):
                try:
                    return data.decode('utf-16le', errors='ignore').rstrip('\x00')
                except:
                    return f"<Binary: {len(data)} bytes>"
            elif isinstance(data, list):
                return "; ".join(str(item) for item in data[:5])
            else:
                return str(data)
        except:
            return "<Error reading value>"
            
    def on_value_selected(self, selected, deselected):
        """Handle value selection."""
        indexes = selected.indexes()
        if not indexes:
            return
            
        # Get the first column (name) of selected row
        row = indexes[0].row()
        name_item = self.table_model.item(row, 0)
        
        if name_item:
            # Get raw data stored in item
            raw_data = name_item.data(Qt.UserRole)
            
            if raw_data:
                # Update hex view
                self.ui.hexView.setPlainText(format_as_hex(raw_data))
                
                # Update decoded view
                self.update_decoded_view()
            
    def update_decoded_view(self):
        """Update decoded data view."""
        # Get selected row
        indexes = self.ui.valuesTable.selectionModel().selectedIndexes()
        if not indexes:
            return
            
        row = indexes[0].row()
        name_item = self.table_model.item(row, 0)
        
        if name_item:
            raw_data = name_item.data(Qt.UserRole)
            
            if raw_data:
                format_type = self.ui.cmbFormat.currentText()
                decoded = decode_registry_data(raw_data, format_type)
                self.ui.decodedView.setPlainText(decoded)
            
    def analyze_key(self, key, path):
        """Analyze registry key for forensic artifacts."""
        analysis_text = f"Registry Key Analysis\n"
        analysis_text += f"{'='*50}\n"
        analysis_text += f"Path: {path}\n"
        analysis_text += f"Last Modified: {key.timestamp()}\n\n"
        
        # Check for known forensic artifacts
        path_upper = path.upper()
        
        if "USERASSIST" in path_upper:
            analysis_text += "📌 UserAssist Key Detected\n"
            analysis_text += "This key contains program execution history.\n"
            analysis_text += "Values are ROT13 encoded.\n"
            
        elif "RUN" in path_upper and "RUNONCE" not in path_upper:
            analysis_text += "🚀 Autostart Entry Detected\n"
            analysis_text += "Programs listed here run at user logon.\n"
            
        elif "SHELLBAGS" in path_upper:
            analysis_text += "📁 Shellbags Detected\n"
            analysis_text += "Contains folder access history and preferences.\n"
            
        elif "TYPEDURLS" in path_upper:
            analysis_text += "🌐 Typed URLs Detected\n"
            analysis_text += "Contains URLs typed in Internet Explorer/Edge.\n"
            
        elif "MOUNTEDDEVICES" in path_upper:
            analysis_text += "💾 Mounted Devices Detected\n"
            analysis_text += "Shows history of connected storage devices.\n"
            
        elif "USBSTOR" in path_upper:
            analysis_text += "🔌 USB Storage Device History\n"
            analysis_text += "Contains information about connected USB devices.\n"
            
        self.ui.analysisView.setHtml(f"<pre>{analysis_text}</pre>")
        
    def update_timeline(self):
        """Update timeline with registry modifications."""
        self.ui.timelineTable.setRowCount(0)
        timeline_events = []
        
        for hive_path, hive_info in self.loaded_hives.items():
            try:
                registry = hive_info['registry']
                self.collect_timeline_events(registry.root(), timeline_events, hive_info['name'])
            except:
                pass
                
        # Sort by timestamp
        timeline_events.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Add to table (limit to 100 most recent)
        self.ui.timelineTable.setRowCount(min(len(timeline_events), 100))
        
        for i, event in enumerate(timeline_events[:100]):
            self.ui.timelineTable.setItem(i, 0, QTableWidgetItem(event['timestamp'].strftime('%Y-%m-%d %H:%M:%S')))
            self.ui.timelineTable.setItem(i, 1, QTableWidgetItem(event['key']))
            self.ui.timelineTable.setItem(i, 2, QTableWidgetItem(event['action']))
            self.ui.timelineTable.setItem(i, 3, QTableWidgetItem(event['details']))
            
        self.ui.timelineTable.resizeColumnsToContents()
        
    def collect_timeline_events(self, key, events, hive_name, depth=0, max_depth=3):
        """Collect timeline events from registry keys."""
        if depth >= max_depth:
            return
            
        try:
            if key.timestamp():
                events.append({
                    'timestamp': key.timestamp(),
                    'key': key.path(),
                    'action': 'Modified',
                    'details': f'Hive: {hive_name}'
                })
                
            for subkey in key.subkeys():
                self.collect_timeline_events(subkey, events, hive_name, depth + 1, max_depth)
        except:
            pass
            
    def add_bookmark(self):
        """Add current location to bookmarks."""
        current_index = self.ui.registryTree.currentIndex()
        if not current_index.isValid():
            return
            
        item = self.tree_model.itemFromIndex(current_index)
        if not item:
            return
            
        data = item.data(Qt.UserRole)
        if data and data["type"] == "key":
            bookmark_text = data["path"]
            
            # Check if already bookmarked
            for i in range(self.ui.bookmarksList.count()):
                if self.ui.bookmarksList.item(i).text() == bookmark_text:
                    return
                    
            # Add bookmark
            list_item = QListWidgetItem(bookmark_text)
            list_item.setData(Qt.UserRole, data)
            self.ui.bookmarksList.addItem(list_item)
            self.bookmarks.append(data)
            
            self.update_status("Bookmark added", "green")
            
    def remove_bookmark(self):
        """Remove selected bookmark."""
        current = self.ui.bookmarksList.currentItem()
        if current:
            row = self.ui.bookmarksList.row(current)
            self.ui.bookmarksList.takeItem(row)
            if row < len(self.bookmarks):
                del self.bookmarks[row]
                
    def go_to_bookmark(self):
        """Navigate to selected bookmark."""
        current = self.ui.bookmarksList.currentItem()
        if current:
            data = current.data(Qt.UserRole)
            if data:
                # Find and select the item in tree
                self.find_and_select_tree_item(data["path"])
                
    def bookmark_double_clicked(self, item):
        """Handle bookmark double-click."""
        self.go_to_bookmark()
        
    def quick_access_double_clicked(self, item):
        """Handle quick access double-click."""
        text = item.text()
        
        # Map quick access items to registry paths
        quick_paths = {
            "🔧 Run/RunOnce Keys": [
                "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Run",
                "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\RunOnce"
            ],
            "👤 UserAssist": ["SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\UserAssist"],
            "📁 Recent Documents": ["SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Explorer\\RecentDocs"],
            "🌐 TypedURLs": ["SOFTWARE\\Microsoft\\Internet Explorer\\TypedURLs"],
            "🔌 USB Devices": ["SYSTEM\\CurrentControlSet\\Enum\\USBSTOR"],
            "🖥️ Network History": ["SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\NetworkList"],
            "📦 Installed Software": ["SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall"],
            "⚙️ Services": ["SYSTEM\\CurrentControlSet\\Services"],
            "🕒 System Time Zone": ["SYSTEM\\CurrentControlSet\\Control\\TimeZoneInformation"],
            "🔐 Security Settings": ["SECURITY\\Policy"]
        }
        
        if text in quick_paths:
            for path in quick_paths[text]:
                self.find_and_select_tree_item(path)
                break
                
    def find_and_select_tree_item(self, target_path):
        """Find and select item in tree by path."""
        # Implementation would search tree and select matching item
        self.update_status(f"Navigating to: {target_path}", "yellow")
        
    def on_quick_load_selected(self, index):
        """Handle quick load selection."""
        if index <= 0:
            return
            
        file_path = self.ui.cmbQuickLoad.itemData(index)
        if file_path and os.path.exists(file_path):
            self.process_hive_files([file_path])
            
    def on_search_text_changed(self, text):
        """Handle search text change."""
        if len(text) >= 3:
            # Could implement live search
            pass
            
    def perform_search(self):
        """Perform registry search."""
        search_text = self.ui.txtSearch.text()
        if not search_text:
            return
            
        self.update_status(f"Searching for: {search_text}", "yellow")
        
        # Search implementation would go here
        QMessageBox.information(self, "Search", f"Search functionality for '{search_text}' is being implemented.")
        
    def filter_tree(self, text):
        """Filter tree view."""
        # Tree filtering implementation
        pass
        
    def copy_current_path(self):
        """Copy current path to clipboard."""
        path = self.ui.txtCurrentPath.text()
        if path:
            QApplication.clipboard().setText(path)
            self.update_status("Path copied to clipboard", "green")
            
    def save_notes(self):
        """Save investigation notes."""
        notes = self.ui.notesEdit.toPlainText()
        if notes:
            # Save to database or file
            self.update_status("Notes saved", "green")
            
    def show_hive_info(self, hive_info):
        """Show hive information."""
        info_text = f"Hive Information\n"
        info_text += f"{'='*50}\n"
        info_text += f"Name: {hive_info['name']}\n"
        info_text += f"Type: {hive_info['type']}\n"
        info_text += f"Path: {hive_info['path']}\n"
        info_text += f"Size: {hive_info['size']:,} bytes\n"
        info_text += f"Modified: {hive_info['modified']}\n"
        
        self.ui.analysisView.setHtml(f"<pre>{info_text}</pre>")
        
    def show_tree_context_menu(self, position):
        """Show context menu for tree."""
        menu = QMenu()
        
        copy_path = menu.addAction("📋 Copy Path")
        add_bookmark = menu.addAction("⭐ Add Bookmark")
        menu.addSeparator()
        export_key = menu.addAction("💾 Export Key")
        
        action = menu.exec_(self.ui.registryTree.mapToGlobal(position))
        
        if action == copy_path:
            self.copy_current_path()
        elif action == add_bookmark:
            self.add_bookmark()
            
    def show_search_menu(self):
        """Show search options menu."""
        menu = QMenu()
        
        menu.addAction("🔍 Case Sensitive").setCheckable(True)
        menu.addAction("📝 Regular Expression").setCheckable(True)
        menu.addAction("🗑️ Include Deleted").setCheckable(True)
        
        menu.exec_(self.ui.btnSearchOptions.mapToGlobal(self.ui.btnSearchOptions.rect().bottomLeft()))
        
    def show_export_menu(self):
        """Show export options menu."""
        menu = QMenu()
        
        menu.addAction("📄 Export as HTML", self.export_html)
        menu.addAction("📊 Export as CSV", self.export_csv)
        menu.addAction("📝 Export as Text", self.export_text)
        menu.addSeparator()
        menu.addAction("📦 Export All Results", self.export_all)
        
        menu.exec_(self.ui.btnExport.mapToGlobal(self.ui.btnExport.rect().bottomLeft()))
        
    def show_tools_menu(self):
        """Show tools menu."""
        menu = QMenu()
        
        menu.addAction("🔬 Run RECmd Analysis", self.start_comprehensive_analysis)
        menu.addAction("🔄 Refresh", self.refresh_view)
        menu.addSeparator()
        menu.addAction("⚙️ Settings", self.show_settings)
        menu.addAction("❓ Help", self.show_help)
        
        menu.exec_(self.ui.btnTools.mapToGlobal(self.ui.btnTools.rect().bottomLeft()))
        
    def start_comprehensive_analysis(self):
        """Start RECmd analysis."""
        if not self.loaded_hives:
            QMessageBox.warning(self, "No Hives", "Please load registry hives first.")
            return
            
        # Find batch file
        batch_file = os.path.join(self.batch_dir, "DFIRBatch.reb")
        if not os.path.exists(batch_file):
            # Find any batch file
            import glob
            batch_files = glob.glob(os.path.join(self.batch_dir, "*.reb"))
            if batch_files:
                batch_file = batch_files[0]
            else:
                QMessageBox.warning(self, "No Batch File", "No RECmd batch files found.")
                return
                
        # Create progress dialog
        progress = QProgressDialog("Running RECmd analysis...", "Cancel", 0, 100, self)
        progress.setWindowModality(Qt.WindowModal)
        
        # Create analysis thread
        hive_files = list(self.loaded_hives.keys())
        self.current_analysis_thread = RegistryAnalysisThread(
            self.recmd_path, batch_file, hive_files, self.output_dir
        )
        
        # Connect signals
        self.current_analysis_thread.progress_updated.connect(progress.setValue)
        self.current_analysis_thread.status_updated.connect(lambda s: self.update_status(s, "yellow"))
        self.current_analysis_thread.analysis_completed.connect(self.on_analysis_completed)
        self.current_analysis_thread.error_occurred.connect(self.on_analysis_error)
        
        progress.canceled.connect(self.current_analysis_thread.cancel)
        
        # Start analysis
        self.current_analysis_thread.start()
        progress.exec_()
        
    def on_analysis_completed(self, results):
        """Handle analysis completion."""
        self.analysis_results = results
        total_records = sum(len(r) for r in results.values())
        
        self.update_status(f"Analysis complete: {total_records} records", "green")
        
        QMessageBox.information(
            self,
            "Analysis Complete",
            f"RECmd analysis completed successfully!\n"
            f"Found {total_records} forensic artifacts."
        )
        
    def on_analysis_error(self, error):
        """Handle analysis error."""
        self.update_status(f"Analysis failed: {error}", "red")
        QMessageBox.critical(self, "Analysis Error", f"Analysis failed:\n{error}")
        
    def refresh_view(self):
        """Refresh current view."""
        if self.loaded_hives:
            self.build_registry_tree()
            self.update_timeline()
            self.update_status("View refreshed", "green")
            
    def export_html(self):
        """Export as HTML."""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export HTML Report", "registry_report.html", "HTML Files (*.html)"
        )
        if filepath:
            # Export implementation
            self.update_status("Report exported", "green")
            
    def export_csv(self):
        """Export as CSV."""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export CSV", "registry_data.csv", "CSV Files (*.csv)"
        )
        if filepath:
            # Export implementation
            self.update_status("CSV exported", "green")
            
    def export_text(self):
        """Export as text."""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export Text", "registry_report.txt", "Text Files (*.txt)"
        )
        if filepath:
            # Export implementation
            self.update_status("Text exported", "green")
            
    def export_all(self):
        """Export all results."""
        # Export all implementation
        self.update_status("Exporting all results...", "yellow")
        
    def show_settings(self):
        """Show settings dialog."""
        QMessageBox.information(self, "Settings", "Settings dialog - Under development")
        
    def show_help(self):
        """Show help."""
        help_text = """
        Registry Analysis Tool - Quick Guide
        
        1. Load Hives: Click 'Load Hive' or use Quick Load
        2. Navigate: Use tree view to browse registry structure
        3. Search: Enter search terms to find keys/values
        4. Analyze: View automated analysis in Analysis tab
        5. Timeline: Check Timeline tab for modification history
        6. Export: Export results in various formats
        
        Quick Access provides shortcuts to common forensic locations.
        """
        QMessageBox.information(self, "Help", help_text)