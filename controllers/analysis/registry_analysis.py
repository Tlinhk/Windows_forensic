# -*- coding: utf-8 -*-

import os
import csv
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Thư viện Registry
try:
    import Registry.Registry as Registry
    REGISTRY_AVAILABLE = True
except ImportError:
    Registry = None
    REGISTRY_AVAILABLE = False

# PyQt5
from PyQt5.QtWidgets import (
    QWidget, QMessageBox, QFileDialog, QTableWidgetItem, 
    QProgressDialog, QApplication, QMenu, QListWidgetItem
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QFont

from views.pages.analysis_ui.registry_analysis_ui import Ui_RegistryAnalysisWidget


# ============================================================================
# LỚP GIẢI MÃ DỮ LIỆU - Tổng hợp tất cả các hàm giải mã
# ============================================================================

class RegistryDataDecoder:
    """Bộ giải mã dữ liệu registry tập trung."""
    
    @staticmethod
    def decode(data, format_type="Tự động phát hiện"):
        """Phương thức giải mã chính."""
        if not data:
            return "Không có dữ liệu"
            
        decoders = {
            "Auto-detect": RegistryDataDecoder._auto_decode,
            "UTF-16 String": lambda d: d.decode("utf-16le", errors="ignore").rstrip('\x00') if isinstance(d, bytes) else str(d),
            "UTF-8 String": lambda d: d.decode("utf-8", errors="ignore").rstrip('\x00') if isinstance(d, bytes) else str(d),
            "DWORD (32-bit)": RegistryDataDecoder._decode_dword,
            "QWORD (64-bit)": RegistryDataDecoder._decode_qword,
            "Windows FILETIME": RegistryDataDecoder._decode_filetime,
            "Hex Dump": RegistryDataDecoder._format_hex
        }
        
        try:
            decoder = decoders.get(format_type, str)
            return decoder(data)
        except Exception as e:
            return f"Lỗi giải mã: {str(e)}"
    
    @staticmethod
    def _auto_decode(data):
        """Tự động phát hiện và giải mã."""
        if isinstance(data, int):
            return f"Số nguyên: {data}\nHex: 0x{data:X}"
        elif isinstance(data, str):
            return f"Chuỗi: {data}"
        elif isinstance(data, bytes):
            # Try UTF-16 first
            try:
                utf16 = data.decode("utf-16le", errors="strict").rstrip('\x00')
                if utf16.isprintable():
                    return f"UTF-16: {utf16}"
            except:
                pass
            
            # Check common patterns
            if len(data) == 4:
                value = int.from_bytes(data, byteorder="little")
                return f"DWORD: {value} (0x{value:08X})"
            elif len(data) == 8:
                value = int.from_bytes(data, byteorder="little")
                return f"QWORD: {value} (0x{value:016X})"
            
            return RegistryDataDecoder._format_hex(data)
        return str(data)
    
    @staticmethod
    def _decode_dword(data):
        """Giải mã giá trị DWORD."""
        if isinstance(data, int):
            return f"DWORD: {data}\nHex: 0x{data:08X}"
        elif isinstance(data, bytes) and len(data) == 4:
            value = int.from_bytes(data, byteorder="little")
            return f"DWORD: {value}\nHex: 0x{value:08X}"
        return str(data)
    
    @staticmethod
    def _decode_qword(data):
        """Giải mã giá trị QWORD."""
        if isinstance(data, int):
            return f"QWORD: {data}\nHex: 0x{data:016X}"
        elif isinstance(data, bytes) and len(data) == 8:
            value = int.from_bytes(data, byteorder="little")
            return f"QWORD: {value}\nHex: 0x{value:016X}"
        return str(data)
    
    @staticmethod
    def _decode_filetime(data):
        """Giải mã Windows FILETIME."""
        if isinstance(data, bytes) and len(data) == 8:
            filetime = int.from_bytes(data, byteorder="little")
            if filetime == 0:
                return "FILETIME: Not set"
            dt = datetime(1601, 1, 1) + timedelta(microseconds=filetime/10)
            return f"FILETIME: {dt.strftime('%Y-%m-%d %H:%M:%S')}"
        return "Invalid FILETIME"
    
    @staticmethod
    def _format_hex(data):
        """Định dạng dạng hex dump."""
        if isinstance(data, str):
            data = data.encode("utf-8", errors="ignore")
        
        lines = []
        for offset in range(0, len(data), 16):
            chunk = data[offset:offset+16]
            hex_bytes = ' '.join(f'{b:02x}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            lines.append(f"{offset:08X}  {hex_bytes:<48} |{ascii_part}|")
        return "\n".join(lines)


# ============================================================================
# LUỒNG PHÂN TÍCH
# ============================================================================

class RegistryAnalysisThread(QThread):
    """Luồng xử lý phân tích RECmd."""
    
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
            results = {}
            total = len(self.hive_files)

            for i, hive_file in enumerate(self.hive_files):
                if self.is_cancelled:
                    break

                self.status_updated.emit(f"Đang phân tích {os.path.basename(hive_file)}...")
                result = self._run_recmd(hive_file)
                if result:
                    results[hive_file] = result

                self.progress_updated.emit(int((i + 1) / total * 100))
            
            if not self.is_cancelled:
                self.analysis_completed.emit(results)
                
        except Exception as e:
            self.error_occurred.emit(str(e))
    
    def _run_recmd(self, hive_file):
        """Run RECmd on single hive."""
        hive_name = os.path.splitext(os.path.basename(hive_file))[0]
        output_csv = os.path.join(self.output_dir, f"{hive_name}_analysis.csv")
        
        cmd = [
            self.recmd_path, "-f", hive_file,
            "--bn", self.batch_file,
            "--csv", self.output_dir,
            "--csvf", f"{hive_name}_analysis.csv",
            "--nl"
        ]
        
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
        
        stdout, stderr = process.communicate()
        
        if process.returncode == 0 and os.path.exists(output_csv):
            return self._parse_csv(output_csv)
        return None
    
    def _parse_csv(self, csv_file):
        """Parse RECmd CSV output."""
        results = []
        with open(csv_file, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                results.append(row)
        return results


# ============================================================================
# MAIN WIDGET - Simplified
# ============================================================================

class RegistryAnalysis(QWidget):
    """Optimized Registry Analysis Widget."""
    
    # Known forensic keys for quick analysis
    FORENSIC_KEYS = {
        "USERASSIST": "Lịch sử thực thi chương trình (mã hóa ROT13)",
        "RUN": "Chương trình khởi động tự động",
        "SHELLBAGS": "Lịch sử truy cập thư mục",
        "TYPEDURLS": "URLs đã nhập trong IE/Edge",
        "MOUNTEDDEVICES": "Lịch sử thiết bị lưu trữ",
        "USBSTOR": "Lịch sử thiết bị USB"
    }
    
    def __init__(self, main_window=None):
        super().__init__()
        self.main_window = main_window
        self.ui = Ui_RegistryAnalysisWidget()
        self.ui.setupUi(self)
        
        # Core state
        self.current_case_id = None
        self.loaded_hives = {}
        self.analysis_results = {}
        self.decoder = RegistryDataDecoder()
        
        # Models
        self.tree_model = QStandardItemModel()
        self.table_model = QStandardItemModel()
        
        # Initialize
        self._init_paths()
        self._setup_ui()
        self._connect_signals()
        
        # Auto-load case if available
        if main_window and hasattr(main_window, 'current_case_id'):
            QTimer.singleShot(100, lambda: self.load_case(main_window.current_case_id))
    
    def _init_paths(self):
        """Initialize tool paths."""
        try:
            from utils.path_utils import get_tools_dir
            self.tools_dir = get_tools_dir()
        except:
            self.tools_dir = os.path.join(os.path.dirname(__file__), "..", "..", "tools")
            
        self.recmd_path = os.path.join(self.tools_dir, "RECmd", "RECmd.exe")
        self.batch_dir = os.path.join(self.tools_dir, "RECmd", "BatchExamples")
        self.output_dir = None
    
    def _setup_ui(self):
        """Setup UI components."""
        # Tree
        self.tree_model.setHorizontalHeaderLabels(["Registry Keys"])
        self.ui.registryTree.setModel(self.tree_model)
        self.ui.registryTree.setContextMenuPolicy(Qt.CustomContextMenu)
        
        # Table
        self.ui.valuesTable.setModel(self.table_model)
        
        # Views
        self.ui.hexView.setReadOnly(True)
        self.ui.hexView.setFont(QFont("Consolas", 9))
        self.ui.decodedView.setReadOnly(True)
        
        # Timeline
        self.ui.timelineTable.setColumnCount(4)
        self.ui.timelineTable.setHorizontalHeaderLabels(["Time", "Key", "Action", "Details"])
        
        # Initial state
        self.ui.btnLoadSelectedHive.setEnabled(False)
        self._update_status("Ready")
    
    def _connect_signals(self):
        """Connect all signals."""
        # Toolbar
        self.ui.cmbHiveArtifacts.currentIndexChanged.connect(self._on_hive_selected)
        self.ui.btnLoadSelectedHive.clicked.connect(self._load_selected_hive)
        self.ui.btnRefreshHives.clicked.connect(self._refresh_hives)
        self.ui.btnExport.clicked.connect(self._show_export_menu)
        
        # Tree/Table
        self.ui.registryTree.clicked.connect(self._on_tree_clicked)
        self.ui.registryTree.customContextMenuRequested.connect(self._show_context_menu)
        self.ui.valuesTable.selectionModel().selectionChanged.connect(self._on_value_selected)
        
        # Actions
        self.ui.btnExpandAll.clicked.connect(self.ui.registryTree.expandAll)
        self.ui.btnCollapseAll.clicked.connect(self.ui.registryTree.collapseAll)
        self.ui.btnCopyPath.clicked.connect(self._copy_path)
        self.ui.cmbFormat.currentTextChanged.connect(self._update_decoded_view)
    
    # ========== CASE MANAGEMENT ==========
    
    def showEvent(self, event):
        """Handle widget show event."""
        super().showEvent(event)
        if self.main_window and hasattr(self.main_window, 'current_case_id'):
            case_id = self.main_window.current_case_id
            if case_id != self.current_case_id:
                self.load_case(case_id) if case_id else self._reset_state()
    
    def load_case(self, case_id):
        """Load case data."""
        if case_id != self.current_case_id:
            self._reset_state()
            
        self.current_case_id = case_id
        self.ui.caseInfoLabel.setText(f"Case ID: {case_id}")
        
        try:
            from models.db_manager import DatabaseManager
            db = DatabaseManager()
            db.connect()
            
            case_info = db.get_case_with_investigator(case_id)
            if case_info and case_info.get('archive_path'):
                self.output_dir = os.path.join(case_info['archive_path'], "analysis_results", "registry")
                os.makedirs(self.output_dir, exist_ok=True)
                self._load_hive_artifacts(db)
            
            db.disconnect()
        except Exception as e:
            print(f"Error loading case: {e}")
            self._set_temp_output()
    
    def _reset_state(self):
        """Reset to empty state."""
        self.loaded_hives.clear()
        self.analysis_results.clear()
        self.tree_model.clear()
        self.table_model.clear()
        self.ui.hexView.clear()
        self.ui.decodedView.clear()
        self.ui.timelineTable.setRowCount(0)
        self.ui.cmbHiveArtifacts.clear()
        self.ui.cmbHiveArtifacts.addItem("-- Select Registry Hive --", None)
    
    # ========== HIVE OPERATIONS ==========
    
    def _load_hive_artifacts(self, db):
        """Load hive artifacts from database."""
        self.ui.cmbHiveArtifacts.clear()
        self.ui.cmbHiveArtifacts.addItem("-- Select Registry Hive --", None)
        
        artifacts = db.get_artifacts_by_case(self.current_case_id)
        
        # Filter registry artifacts
        hive_keywords = ['SYSTEM', 'SOFTWARE', 'SAM', 'SECURITY', 'NTUSER', 'USRCLASS', 'DEFAULT', 'REGISTRY']
        
        for artifact in artifacts:
            name = artifact.get('name', '').upper()
            path = artifact.get('source_path', '').upper()
            
            if any(keyword in name or keyword in path for keyword in hive_keywords):
                hive_type = self._detect_hive_type(name or path)
                display = f"{artifact.get('name')} ({hive_type})"
                self.ui.cmbHiveArtifacts.addItem(display, artifact)
    
    def _on_hive_selected(self, index):
        """Handle hive selection."""
        self.ui.btnLoadSelectedHive.setEnabled(index > 0)
    
    def _load_selected_hive(self):
        """Load selected hive file."""
        artifact = self.ui.cmbHiveArtifacts.currentData()
        if not artifact:
            return
            
        source_path = artifact.get('source_path')
        if not source_path or not os.path.exists(source_path):
            QMessageBox.warning(self, "Error", f"Hive file not found:\n{source_path}")
            return
        
        self._process_hive(source_path)
        
        # Auto-analyze if needed
        if not self.analysis_results:
            QTimer.singleShot(500, self._start_analysis)
    
    def _process_hive(self, file_path):
        """Process single hive file."""
        if not REGISTRY_AVAILABLE:
            QMessageBox.warning(self, "Missing Library", "python-registry not installed")
            return
        
        try:
            registry = Registry.Registry(file_path)
            
            self.loaded_hives[file_path] = {
                "path": file_path,
                "name": os.path.basename(file_path),
                "type": self._detect_hive_type(file_path),
                "registry": registry
            }
            
            self._build_tree()
            self._update_timeline()
            self._update_status(f"Loaded: {os.path.basename(file_path)}", "green")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load hive:\n{str(e)}")
    
    def _refresh_hives(self):
        """Refresh hive list."""
        if self.current_case_id:
            self.load_case(self.current_case_id)
    
    # ========== TREE/TABLE OPERATIONS ==========
    
    def _build_tree(self):
        """Build registry tree view."""
        self.tree_model.clear()
        self.tree_model.setHorizontalHeaderLabels(["Registry Keys"])
        
        for path, info in self.loaded_hives.items():
            hive_item = QStandardItem(f"{info['name']} ({info['type']})")
            hive_item.setData({"type": "hive", "info": info}, Qt.UserRole)
            self.tree_model.appendRow(hive_item)
            
            try:
                root = info['registry'].root()
                self._add_key_to_tree(hive_item, root, info['registry'])
            except:
                pass
        
        self.ui.registryTree.expandToDepth(0)
    
    def _add_key_to_tree(self, parent_item, key, registry, depth=0):
        """Add registry key to tree recursively."""
        if depth >= 20:  # Limit depth
            return
        
        try:
            key_name = key.name() or "Root"
            key_item = QStandardItem(key_name)
            key_item.setData({
                "type": "key",
                "key": key,
                "path": key.path(),
                "registry": registry
            }, Qt.UserRole)
            
            parent_item.appendRow(key_item)
            
            for subkey in key.subkeys():
                self._add_key_to_tree(key_item, subkey, registry, depth + 1)
        except:
            pass
    
    def _on_tree_clicked(self, index):
        """Handle tree item click."""
        item = self.tree_model.itemFromIndex(index)
        if not item:
            return
        
        data = item.data(Qt.UserRole)
        if not data:
            return
        
        if data["type"] == "key":
            self._show_key_values(data["key"])
            self.ui.txtCurrentPath.setText(data["path"])
            self._analyze_key(data["path"])
    
    def _show_key_values(self, key):
        """Display key values in table."""
        self.table_model.clear()
        self.table_model.setHorizontalHeaderLabels(["Name", "Type", "Data"])
        
        try:
            for value in key.values():
                name = QStandardItem(value.name() or "(Default)")
                name.setData(value.raw_data(), Qt.UserRole)
                
                type_item = QStandardItem(value.value_type_str())
                data_item = QStandardItem(self._format_value(value))
                
                self.table_model.appendRow([name, type_item, data_item])
            
            self.ui.valuesTable.resizeColumnsToContents()
        except:
            pass
    
    def _on_value_selected(self, selected, deselected):
        """Handle value selection."""
        indexes = selected.indexes()
        if not indexes:
            return
        
        row = indexes[0].row()
        name_item = self.table_model.item(row, 0)
        
        if name_item:
            raw_data = name_item.data(Qt.UserRole)
            if raw_data:
                self.ui.hexView.setPlainText(self.decoder._format_hex(raw_data))
                self._update_decoded_view()
    
    def _update_decoded_view(self):
        """Update decoded data view."""
        indexes = self.ui.valuesTable.selectionModel().selectedIndexes()
        if not indexes:
            return
        
        row = indexes[0].row()
        name_item = self.table_model.item(row, 0)
        
        if name_item:
            raw_data = name_item.data(Qt.UserRole)
            if raw_data:
                format_type = self.ui.cmbFormat.currentText()
                decoded = self.decoder.decode(raw_data, format_type)
                self.ui.decodedView.setPlainText(decoded)
    
    # ========== ANALYSIS ==========
    
    def _analyze_key(self, path):
        """Analyze registry key for forensic artifacts."""
        path_upper = path.upper()
        
        analysis = f"Registry Key Analysis\n{'='*50}\n"
        analysis += f"Path: {path}\n\n"
        
        # Check known forensic keys
        for key_pattern, description in self.FORENSIC_KEYS.items():
            if key_pattern in path_upper:
                analysis += f"⚠️ Detected: {description}\n"
                break
        
        self.ui.analysisView.setHtml(f"<pre>{analysis}</pre>")
    
    def _start_analysis(self):
        """Start RECmd analysis."""
        if not self.loaded_hives:
            return
        
        if not self.output_dir:
            self._set_temp_output()
        
        # Find batch file
        import glob
        batch_files = glob.glob(os.path.join(self.batch_dir, "*.reb"))
        if not batch_files:
            QMessageBox.warning(self, "Error", "No RECmd batch files found")
            return
        
        progress = QProgressDialog("Running RECmd analysis...", "Cancel", 0, 100, self)
        progress.setWindowModality(Qt.WindowModal)
        
        thread = RegistryAnalysisThread(
            self.recmd_path,
            batch_files[0],
            list(self.loaded_hives.keys()),
            self.output_dir
        )
        
        thread.progress_updated.connect(progress.setValue)
        thread.analysis_completed.connect(self._on_analysis_done)
        thread.error_occurred.connect(lambda e: QMessageBox.critical(self, "Error", e))
        
        progress.canceled.connect(thread.cancel)
        thread.start()
        progress.exec_()
    
    def _on_analysis_done(self, results):
        """Handle analysis completion."""
        self.analysis_results = results
        total = sum(len(r) for r in results.values())
        self._update_status(f"Analysis complete: {total} records", "green")
    
    # ========== TIMELINE ==========
    
    def _update_timeline(self):
        """Update timeline table."""
        self.ui.timelineTable.setRowCount(0)
        events = []
        
        for path, info in self.loaded_hives.items():
            try:
                self._collect_timeline(info['registry'].root(), events, info['name'])
            except:
                pass
        
        # Sort and display top 100
        events.sort(key=lambda x: x['time'], reverse=True)
        
        for i, event in enumerate(events[:100]):
            self.ui.timelineTable.insertRow(i)
            self.ui.timelineTable.setItem(i, 0, QTableWidgetItem(event['time'].strftime('%Y-%m-%d %H:%M:%S')))
            self.ui.timelineTable.setItem(i, 1, QTableWidgetItem(event['key']))
            self.ui.timelineTable.setItem(i, 2, QTableWidgetItem(event['action']))
            self.ui.timelineTable.setItem(i, 3, QTableWidgetItem(event['details']))
    
    def _collect_timeline(self, key, events, hive_name, depth=0):
        """Collect timeline events."""
        if depth >= 3:  # Limit depth for performance
            return
        
        try:
            if key.timestamp():
                events.append({
                    'time': key.timestamp(),
                    'key': key.path(),
                    'action': 'Modified',
                    'details': f'Hive: {hive_name}'
                })
            
            for subkey in key.subkeys():
                self._collect_timeline(subkey, events, hive_name, depth + 1)
        except:
            pass
    
    # ========== EXPORT ==========
    
    def _show_export_menu(self):
        """Show export menu."""
        menu = QMenu()
        menu.addAction("Run Analysis", self._start_analysis)
        menu.addSeparator()
        menu.addAction("Export CSV", self._export_csv)
        menu.exec_(self.ui.btnExport.mapToGlobal(self.ui.btnExport.rect().bottomLeft()))
    
    def _export_csv(self):
        """Export analysis to CSV."""
        if not self.analysis_results:
            QMessageBox.warning(self, "No Data", "No analysis results to export")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "", "CSV Files (*.csv)")
        if file_path:
            try:
                with open(file_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(['Hive', 'Key Path', 'Value Name', 'Value Type', 'Value Data'])
                    
                    for hive_file, results in self.analysis_results.items():
                        hive_name = os.path.basename(hive_file)
                        for result in results:
                            writer.writerow([
                                hive_name,
                                result.get('KeyPath', ''),
                                result.get('ValueName', ''),
                                result.get('ValueType', ''),
                                result.get('ValueData', '')
                            ])
                
                QMessageBox.information(self, "Success", f"Exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Export failed:\n{str(e)}")
    
    # ========== HELPERS ==========
    
    def _show_context_menu(self, position):
        """Show tree context menu."""
        menu = QMenu()
        menu.addAction("Copy Path", self._copy_path)
        menu.exec_(self.ui.registryTree.mapToGlobal(position))
    
    def _copy_path(self):
        """Copy current path to clipboard."""
        path = self.ui.txtCurrentPath.text()
        if path:
            QApplication.clipboard().setText(path)
            self._update_status("Path copied", "green")
    
    def _format_value(self, value):
        """Format registry value for display."""
        try:
            data = value.value()
            if isinstance(data, str):
                return data.replace('\x00', '').strip()
            elif isinstance(data, bytes):
                try:
                    return data.decode('utf-16le', errors='ignore').rstrip('\x00')
                except:
                    return f"<Binary: {len(data)} bytes>"
            return str(data)
        except:
            return "<Error>"
    
    def _detect_hive_type(self, path):
        """Detect hive type from path/name."""
        path_upper = str(path).upper()
        
        hive_types = {
            'SYSTEM': 'SYSTEM',
            'SOFTWARE': 'SOFTWARE', 
            'SAM': 'SAM',
            'SECURITY': 'SECURITY',
            'NTUSER': 'NTUSER',
            'USRCLASS': 'USRCLASS',
            'DEFAULT': 'DEFAULT'
        }
        
        for keyword, hive_type in hive_types.items():
            if keyword in path_upper:
                return hive_type
        return 'UNKNOWN'
    
    def _update_status(self, message, color="green"):
        """Update status indicator."""
        colors = {"green": "#90EE90", "yellow": "#FFD700", "red": "#FF6B6B"}
        self.ui.statusIndicator.setText(f"● {message}")
        self.ui.statusIndicator.setStyleSheet(f"color: {colors.get(color, '#90EE90')}")
        self.ui.statusBar.showMessage(message, 5000)
    
    def _set_temp_output(self):
        """Set temporary output directory."""
        self.output_dir = os.path.join(os.path.dirname(__file__), "temp", "registry")
        os.makedirs(self.output_dir, exist_ok=True)