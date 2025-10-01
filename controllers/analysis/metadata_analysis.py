# ==================== THƯ VIỆN CẦN THIẾT ====================
from PyQt5.QtWidgets import QWidget, QFileDialog, QMessageBox, QTreeWidgetItem, QListWidgetItem
from PyQt5.QtCore import Qt, QLoggingCategory, QUrl, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QTextCharFormat, QBrush, QColor

import os
import mimetypes
import subprocess
import json
from datetime import datetime

from views.pages.analysis_ui.metadata_analysis_ui import Ui_Form


# ==================== LỚP CHÍNH ====================
class MetadataAnalysis(QWidget):
    """Công cụ phân tích metadata cho file/thư mục - Phiên bản tối ưu."""

    def __init__(self, main_window=None):
        super().__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        
        # Thuộc tính cốt lõi
        self.main_window = main_window
        self.current_case_id = None
        self.db_manager = None
        self.current_file_path = None
        self.exiftool_path = self._find_exiftool()
        self.current_metadata = {}
        
        # Thiết lập
        QLoggingCategory.setFilterRules("qt.gui.icc=false")
        self._connect_signals()
        self._clear_ui()
        
        # Tải dữ liệu ban đầu
        if main_window and hasattr(main_window, 'current_case_id'):
            QTimer.singleShot(100, lambda: self.load_case_data(main_window.current_case_id))

    def _connect_signals(self):
        """Kết nối các tín hiệu giao diện người dùng - hợp nhất"""
        connections = [
            (self.ui.searchMetadataLineEdit.textChanged, self._filter_metadata),
            (self.ui.btnRefreshEvidence.clicked, self.refresh_evidence_list),
            (self.ui.evidenceListWidget.itemClicked, self._on_evidence_clicked),
            (self.ui.btnExportMetadata.clicked, self._export_metadata),
            (self.ui.btnRefreshMap.clicked, self._refresh_map),
            (self.ui.rawSearchLineEdit.textChanged, lambda t: self._search_text(self.ui.rawTextEdit, t)),
            (self.ui.hexSearchLineEdit.textChanged, lambda t: self._search_text(self.ui.hexTextEdit, t)),
            (self.ui.stringsSearchLineEdit.textChanged, lambda t: self._search_text(self.ui.stringsTextEdit, t)),
        ]
        
        for signal, handler in connections:
            try:
                signal.connect(handler)
            except:
                pass

    # ==================== QUẢN LÝ VỤ VIỆC ====================
    def showEvent(self, event):
        super().showEvent(event)
        if self.main_window and hasattr(self.main_window, 'current_case_id'):
            case_id = self.main_window.current_case_id
            if case_id != self.current_case_id:
                self.load_case_data(case_id) if case_id else self._clear_evidence_list()

    def load_case_data(self, case_id):
        """Tải vụ việc và bằng chứng - đơn giản hóa"""
        self.current_case_id = case_id
        try:
            from models.db_manager import DatabaseManager
            self.db_manager = DatabaseManager()
            if self.db_manager.connect():
                case_info = self.db_manager.get_case_with_investigator(case_id)
                if case_info:
                    self.ui.caseTitleLabel.setText(case_info['title'])
                self._load_evidence()
                self.db_manager.disconnect()
        except Exception as e:
            print(f"Error loading case: {e}")

    def _load_evidence(self):
        """Tải các hiện vật bằng chứng có thể phân tích"""
        try:
            artifacts = self.db_manager.get_artifacts_by_case(self.current_case_id)
            self.ui.evidenceListWidget.clear()
            
            count = 0
            for artifact in artifacts:
                if self._is_analyzable(artifact):
                    item_text = self._format_evidence_item(artifact)
                    item = QListWidgetItem(item_text)
                    item.setData(Qt.UserRole, artifact)
                    self.ui.evidenceListWidget.addItem(item)
                    count += 1
            
            self.ui.evidenceCountLabel.setText(str(count))
            if count == 0:
                self.ui.evidenceListWidget.addItem(QListWidgetItem("No analyzable files found"))
                
        except Exception as e:
            print(f"Error loading evidence: {e}")

    def _is_analyzable(self, artifact):
        """Kiểm tra xem hiện vật có thể phân tích được không - đơn giản hóa"""
        source_path = artifact.get('source_path', '')
        if not source_path or not os.path.exists(source_path):
            return False
            
        analyzable_extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif', 
                               '.pdf', '.docx', '.xlsx', '.pptx', '.exe', '.dll'}
        ext = os.path.splitext(source_path)[1].lower()
        return ext in analyzable_extensions

    def _format_evidence_item(self, artifact):
        """Định dạng văn bản hiển thị của mục bằng chứng"""
        name = artifact.get('name', 'Unknown')
        evidence_type = artifact.get('evidence_type', 'Unknown')
        
        try:
            size = os.path.getsize(artifact.get('source_path', ''))
            size_str = f" - {self._format_size(size)}"
        except:
            size_str = ""
            
        return f"{name} ({evidence_type}){size_str}"

    def _clear_evidence_list(self):
        """Xóa danh sách bằng chứng"""
        self.current_case_id = None
        self.ui.evidenceListWidget.clear()
        self.ui.evidenceCountLabel.setText("0")

    def refresh_evidence_list(self):
        """Làm mới danh sách bằng chứng"""
        if self.current_case_id:
            self._load_evidence()

    def _on_evidence_clicked(self, item):
        """Xử lý sự kiện nhấp vào mục bằng chứng"""
        artifact = item.data(Qt.UserRole)
        if not artifact:
            return
            
        source_path = artifact.get('source_path')
        if source_path and os.path.exists(source_path):
            self.analyze_file(source_path)
            self._log_activity(f"METADATA_ANALYSIS: {artifact.get('name', 'Unknown')}")
        else:
            QMessageBox.warning(self, "Error", f"File not found: {source_path}")

    # ==================== PHÂN TÍCH CHÍNH ====================
    def analyze_file(self, file_path):
        """Phương thức phân tích chính - được tối ưu hóa"""
        if not os.path.exists(file_path):
            QMessageBox.warning(self, "Error", "File not found")
            return

        self.current_file_path = file_path
        self._clear_ui()

        # Thông tin cơ bản
        self._set_basic_info(file_path)
        
        # Trích xuất metadata dựa trên loại file
        metadata = self._extract_metadata(file_path)
        self.current_metadata = metadata
        
        # Cập nhật giao diện người dùng
        self._update_ui(file_path, metadata)
        
        # Phân tích bảo mật
        security_issues = self._analyze_security(file_path, metadata)
        self._update_security_alerts(security_issues)

    def _set_basic_info(self, file_path):
        """Thiết lập thông tin cơ bản của file"""
        name = os.path.basename(file_path)
        size = self._format_size(os.path.getsize(file_path))
        file_type = mimetypes.guess_type(file_path)[0] or self._guess_file_type(name)
        
        self.ui.fileNameValueLabel.setText(name)
        self.ui.fileSizeValueLabel.setText(size)
        self.ui.fileTypeValueLabel.setText(file_type)
        self.ui.currentFileLabel.setText(f"Analyzing: {name}")
        
        # Hình thu nhỏ
        try:
            pix = QPixmap(file_path)
            if not pix.isNull():
                scaled = pix.scaled(220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.ui.thumbnailLabel.setPixmap(scaled)
                self.ui.thumbnailLabel.setText("")
            else:
                self.ui.thumbnailLabel.setText("No preview available")
        except:
            self.ui.thumbnailLabel.setText("No preview available")

    def _extract_metadata(self, file_path):
        """Trích xuất metadata bằng phương thức tốt nhất hiện có"""
        metadata = {'tags': {}, 'author': '-', 'gps': None, 'times': {}}
        
        # Thử ExifTool trước (toàn diện nhất)
        if self.exiftool_path:
            try:
                metadata = self._extract_with_exiftool(file_path)
            except:
                pass
        
        # Dự phòng cho việc trích xuất theo loại file cụ thể
        if not metadata['tags']:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in {'.docx', '.xlsx', '.pptx'}:
                metadata.update(self._extract_office_metadata(file_path))
            elif ext == '.pdf':
                metadata.update(self._extract_pdf_metadata(file_path))
            elif ext in {'.exe', '.dll'}:
                metadata.update(self._extract_pe_metadata(file_path))
            elif ext in {'.jpg', '.jpeg', '.png', '.tiff', '.tif'}:
                metadata.update(self._extract_image_metadata(file_path))
        
        return metadata

    def _extract_with_exiftool(self, file_path):
        """Trích xuất metadata bằng ExifTool"""
        cmd = [self.exiftool_path, "-j", "-G1", "-n", "-a", file_path]
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        
        if result.returncode != 0:
            raise RuntimeError("ExifTool failed")
            
        data = json.loads(result.stdout)[0] if result.stdout else {}
        
        # Trích xuất thông tin chính
        author = self._extract_author(data)
        gps = self._extract_gps(data)
        times = self._extract_times(data)
        
        return {'tags': data, 'author': author, 'gps': gps, 'times': times}

    def _extract_author(self, tags):
        """Trích xuất thông tin tác giả từ các thẻ"""
        author_fields = ["XMP-dc:Creator", "XMP:Creator", "EXIF:Artist", "IFD0:Artist"]
        device_fields = ["IFD0:Make", "EXIF:Make", "IFD0:Model", "EXIF:Model"]
        
        author = None
        for field in author_fields:
            if field in tags and tags[field]:
                author = tags[field]
                if isinstance(author, list):
                    author = ", ".join(map(str, author))
                break
        
        make = tags.get("IFD0:Make") or tags.get("EXIF:Make") or ""
        model = tags.get("IFD0:Model") or tags.get("EXIF:Model") or ""
        device = f"{make} {model}".strip()
        
        if author and device:
            return f"{author} / {device}"
        return author or device or "-"

    def _extract_gps(self, tags):
        """Trích xuất tọa độ GPS"""
        lat = tags.get("GPS:GPSLatitude") or tags.get("Composite:GPSLatitude")
        lon = tags.get("GPS:GPSLongitude") or tags.get("Composite:GPSLongitude")
        
        try:
            if lat is not None and lon is not None:
                return {"lat": float(lat), "lng": float(lon)}
        except:
            pass
        return None

    def _extract_times(self, tags):
        """Trích xuất thông tin dấu thời gian"""
        time_fields = {
            'original': ["EXIF:DateTimeOriginal", "QuickTime:CreateDate", "XMP:DateTimeOriginal"],
            'create': ["EXIF:CreateDate", "XMP:CreateDate", "PDF:CreateDate"],
            'modify': ["EXIF:ModifyDate", "XMP:ModifyDate", "PDF:ModifyDate"]
        }
        
        times = {}
        for key, fields in time_fields.items():
            for field in fields:
                if field in tags and tags[field]:
                    times[key] = self._normalize_datetime(str(tags[field]))
                    break
            else:
                times[key] = "-"
        
        return times

    def _update_ui(self, file_path, metadata):
        """Cập nhật giao diện với metadata đã trích xuất"""
        # Tác giả/Thiết bị
        self.ui.authorDeviceValueLabel.setText(metadata.get('author', '-'))
        
        # GPS
        gps = metadata.get('gps')
        if gps:
            lat, lng = gps['lat'], gps['lng']
            self.ui.currentLocationLabel.setText(f"{lat:.6f}, {lng:.6f}")
            self.ui.currentLocationLabel.setStyleSheet("color: #28a745; font-weight: bold;")
            self._update_map(lat, lng)
        else:
            self.ui.currentLocationLabel.setText("No GPS data")
            self.ui.currentLocationLabel.setStyleSheet("color: #6c757d; font-style: italic;")
            self._reset_map()
        
        # Cây metadata
        self._populate_metadata_tree(metadata.get('tags', {}))
        
        # Các khung văn bản
        self._populate_text_views(file_path, metadata)

    def _populate_metadata_tree(self, tags):
        """Điền dữ liệu vào cây metadata - đơn giản hóa"""
        tree = self.ui.metadataTreeWidget
        tree.clear()
        
        if not tags:
            return
            
        groups = {}
        for key, value in tags.items():
            group_name = key.split(':')[0] if ':' in key else 'Other'
            tag_name = key.split(':', 1)[1] if ':' in key else key
            
            if group_name not in groups:
                groups[group_name] = QTreeWidgetItem([group_name, "", ""])
                tree.addTopLevelItem(groups[group_name])
            
            # Convert value to string
            if isinstance(value, list):
                value_str = ", ".join(map(str, value))
            else:
                value_str = str(value)
            
            child = QTreeWidgetItem(["", tag_name, value_str])
            groups[group_name].addChild(child)
        
        tree.expandAll()

    def _populate_text_views(self, file_path, metadata):
        """Điền dữ liệu vào các khung văn bản thô, hex và chuỗi"""
        # Văn bản thô - thông tin chuyên sâu cho điều tra viên
        insights = self._generate_insights(file_path, metadata)
        self.ui.rawTextEdit.setPlainText(insights)
        
        # Hex và chuỗi
        try:
            with open(file_path, 'rb') as f:
                data = f.read(1024 * 1024)  # 1MB max
            
            self.ui.hexTextEdit.setPlainText(self._to_hex(data))
            self.ui.stringsTextEdit.setPlainText('\n'.join(self._extract_strings(data)))
        except:
            self.ui.hexTextEdit.setPlainText("Error reading file")
            self.ui.stringsTextEdit.setPlainText("Error reading file")

    # ==================== PHÂN TÍCH BẢO MẬT ====================
    def _analyze_security(self, file_path, metadata):
        """Phân tích các vấn đề bảo mật - đơn giản hóa"""
        issues = []
        
        # Kiểm tra tên file
        name = os.path.basename(file_path).lower()
        if name.count('.') > 1:
            issues.append("Multiple file extensions detected")
        if name.startswith('.'):
            issues.append("Hidden file detected")
        
        # Kiểm tra metadata
        tags = metadata.get('tags', {})
        suspicious_authors = {'unknown', 'user', 'admin', 'system', 'root'}
        for key, value in tags.items():
            if 'author' in key.lower() or 'creator' in key.lower():
                if str(value).lower() in suspicious_authors:
                    issues.append(f"Suspicious author: {value}")
        
        # Kiểm tra kích thước file
        try:
            size = os.path.getsize(file_path)
            if size == 0:
                issues.append("Empty file")
            elif size > 100 * 1024 * 1024:
                issues.append(f"Large file: {size / (1024*1024):.1f} MB")
        except:
            pass
        
        return issues

    def _update_security_alerts(self, issues):
        """Cập nhật giao diện cảnh báo bảo mật"""
        try:
            if issues:
                self.ui.alertTitle.setText("Security Alerts")
                self.ui.alertTitle.setStyleSheet("font-weight: bold; color: #dc3545;")
                self.ui.alertText.setText('\n'.join(f"• {issue}" for issue in issues))
                self.ui.alertText.setStyleSheet("color: #dc3545;")
            else:
                self.ui.alertTitle.setText("No Issues Found")
                self.ui.alertTitle.setStyleSheet("font-weight: bold; color: #28a745;")
                self.ui.alertText.setText("No security concerns detected")
                self.ui.alertText.setStyleSheet("color: #6c757d;")
        except:
            pass

    # ==================== CHỨC NĂNG TÌM KIẾM ====================
    def _filter_metadata(self, text):
        """Lọc cây metadata"""
        pattern = text.lower().strip()
        tree = self.ui.metadataTreeWidget
        
        for i in range(tree.topLevelItemCount()):
            group = tree.topLevelItem(i)
            group_match = False
            
            for j in range(group.childCount()):
                child = group.child(j)
                child_text = f"{child.text(1)} {child.text(2)}".lower()
                match = not pattern or pattern in child_text
                child.setHidden(not match)
                if match:
                    group_match = True
            
            group.setHidden(not group_match)

    def _search_text(self, text_edit, search_text):
        """Tìm kiếm và làm nổi bật văn bản - đơn giản hóa"""
        if not search_text:
            self._clear_highlights(text_edit)
            return
        
        # Làm nổi bật đơn giản
        cursor = text_edit.textCursor()
        cursor.select(cursor.Document)
        cursor.setCharFormat(cursor.charFormat())  # Clear formatting
        
        content = text_edit.toPlainText().lower()
        search_lower = search_text.lower()
        
        # Định dạng làm nổi bật
        highlight_format = QTextCharFormat()
        highlight_format.setBackground(QBrush(QColor("#ffff00")))
        
        # Tìm và làm nổi bật các kết quả khớp
        start = 0
        while True:
            pos = content.find(search_lower, start)
            if pos == -1:
                break
            
            cursor.setPosition(pos)
            cursor.setPosition(pos + len(search_text), cursor.KeepAnchor)
            cursor.setCharFormat(highlight_format)
            start = pos + 1

    def _clear_highlights(self, text_edit):
        """Xóa làm nổi bật văn bản"""
        cursor = text_edit.textCursor()
        cursor.select(cursor.Document)
        cursor.setCharFormat(cursor.charFormat())

    # ==================== CHỨC NĂNG BẢN ĐỒ ====================
    def _update_map(self, lat, lng):
        """Cập nhật bản đồ với tọa độ GPS"""
        try:
            url = f"https://maps.google.com/maps?q={lat},{lng}&ll={lat},{lng}&z=16"
            self.ui.mapView.setUrl(QUrl(url))
        except:
            pass

    def _reset_map(self):
        """Đặt lại bản đồ về mặc định"""
        try:
            self.ui.mapView.setUrl(QUrl("https://maps.google.com"))
        except:
            pass

    def _refresh_map(self):
        """Làm mới bản đồ với dữ liệu GPS hiện tại"""
        gps = self.current_metadata.get('gps')
        if gps:
            self._update_map(gps['lat'], gps['lng'])
            QMessageBox.information(self, "Map", "Map refreshed with GPS location")
        else:
            QMessageBox.information(self, "Map", "No GPS data available")

    # ==================== CHỨC NĂNG XUẤT DỮ LIỆU ====================
    def _export_metadata(self):
        """Xuất metadata sang JSON"""
        if not self.current_file_path:
            QMessageBox.information(self, "Export", "Please select a file first")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Metadata",
            f"{os.path.basename(self.current_file_path)}_metadata.json",
            "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.current_metadata, f, indent=2, ensure_ascii=False)
                QMessageBox.information(self, "Export", f"Exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.warning(self, "Export Error", str(e))

    # ==================== CÁC PHƯƠNG THỨC TIỆN ÍCH ====================
    def _find_exiftool(self):
        """Tìm tệp thực thi ExifTool"""
        # Kiểm tra biến môi trường
        env_path = os.environ.get("EXIFTOOL_PATH")
        if env_path and os.path.exists(env_path):
            return env_path
        
        # Kiểm tra các vị trí phổ biến
        base_dir = os.path.dirname(__file__)
        search_paths = [
            os.path.join(base_dir, "..", "..", "tools", "exiftool"),
            os.path.join(base_dir, "..", "..", "..", "tools", "exiftool")
        ]
        
        for search_path in search_paths:
            if os.path.isdir(search_path):
                for filename in os.listdir(search_path):
                    if filename.lower().startswith("exiftool") and filename.endswith(".exe"):
                        return os.path.join(search_path, filename)
        
        return None

    def _clear_ui(self):
        """Xóa tất cả các phần tử giao diện người dùng"""
        defaults = [
            (self.ui.thumbnailLabel, "setPixmap", QPixmap()),
            (self.ui.thumbnailLabel, "setText", "No preview"),
            (self.ui.fileNameValueLabel, "setText", "-"),
            (self.ui.fileTypeValueLabel, "setText", "-"),
            (self.ui.fileSizeValueLabel, "setText", "-"),
            (self.ui.authorDeviceValueLabel, "setText", "-"),
            (self.ui.currentFileLabel, "setText", "No file selected"),
            (self.ui.currentLocationLabel, "setText", "No GPS data"),
            (self.ui.metadataTreeWidget, "clear", None),
            (self.ui.rawTextEdit, "clear", None),
            (self.ui.hexTextEdit, "clear", None),
            (self.ui.stringsTextEdit, "clear", None),
        ]
        
        for widget, method, value in defaults:
            try:
                if value is None:
                    getattr(widget, method)()
                else:
                    getattr(widget, method)(value)
            except:
                pass

    def _log_activity(self, action):
        """Ghi nhật ký hoạt động vào cơ sở dữ liệu"""
        if not self.current_case_id or not self.db_manager:
            return
        try:
            self.db_manager.log_activity(
                case_id=self.current_case_id,
                action=action,
                tool_used="Metadata Analysis"
            )
        except:
            pass

    def _format_size(self, size_bytes):
        """Định dạng kích thước file"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def _guess_file_type(self, filename):
        """Đoán loại file từ phần mở rộng"""
        ext = os.path.splitext(filename)[1].lower()
        types = {
            '.jpg': 'JPEG Image', '.jpeg': 'JPEG Image', '.png': 'PNG Image',
            '.pdf': 'PDF Document', '.docx': 'Word Document', '.xlsx': 'Excel Spreadsheet',
            '.exe': 'Executable File', '.dll': 'Dynamic Library'
        }
        return types.get(ext, 'Unknown File')

    def _normalize_datetime(self, dt_string):
        """Chuẩn hóa chuỗi ngày giờ"""
        if not dt_string or dt_string == "-":
            return "-"
        # Chuẩn hóa đơn giản - thay thế dấu hai chấm trong phần ngày
        try:
            if ":" in dt_string[:10]:
                parts = dt_string.split()
                date_part = parts[0].replace(":", "-", 2)
                time_part = parts[1] if len(parts) > 1 else "00:00:00"
                return f"{date_part} {time_part}"
        except:
            pass
        return dt_string

    def _generate_insights(self, file_path, metadata):
        """Tạo thông tin chuyên sâu cho điều tra viên"""
        insights = ["=== File Analysis Summary ==="]
        
        # Thông tin cơ bản
        insights.append(f"File: {os.path.basename(file_path)}")
        insights.append(f"Size: {self._format_size(os.path.getsize(file_path))}")
        
        # Tác giả/Thiết bị
        author = metadata.get('author', '-')
        if author != '-':
            insights.append(f"Author/Device: {author}")
        
        # GPS
        gps = metadata.get('gps')
        if gps:
            lat, lng = gps['lat'], gps['lng']
            insights.append(f"Location: {lat:.6f}, {lng:.6f}")
            insights.append(f"Map: https://maps.google.com/?q={lat},{lng}")
        
        # Dấu thời gian
        times = metadata.get('times', {})
        for key, value in times.items():
            if value != '-':
                insights.append(f"{key.title()} Date: {value}")
        
        # Mã băm file
        try:
            md5, sha1, sha256 = self._compute_hashes(file_path)
            insights.append(f"MD5: {md5}")
            insights.append(f"SHA1: {sha1}")
            insights.append(f"SHA256: {sha256}")
        except:
            pass
        
        return '\n'.join(insights)

    def _compute_hashes(self, file_path):
        """Tính toán mã băm file"""
        import hashlib
        md5 = hashlib.md5()
        sha1 = hashlib.sha1()
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b""):
                md5.update(chunk)
                sha1.update(chunk)
                sha256.update(chunk)
        
        return md5.hexdigest(), sha1.hexdigest(), sha256.hexdigest()

    def _to_hex(self, data, width=16):
        """Chuyển đổi dữ liệu nhị phân thành dạng hex"""
        lines = []
        for i in range(0, len(data), width):
            chunk = data[i:i + width]
            hex_bytes = " ".join(f"{b:02x}" for b in chunk)
            ascii_chars = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            lines.append(f"{i:08x}  {hex_bytes:<{width * 3}} |{ascii_chars}|")
        return '\n'.join(lines)

    def _extract_strings(self, data, min_len=4):
        """Trích xuất các chuỗi có thể in từ dữ liệu nhị phân"""
        import re
        pattern = rb'[\x20-\x7E]{' + str(min_len).encode() + rb',}'
        matches = re.findall(pattern, data)
        return [m.decode('ascii', errors='ignore') for m in matches[:1000]]  # Giới hạn kết quả

    # ==================== CÁC PHƯƠNG THỨC TRÍCH XUẤT ĐƠN GIẢN HÓA ====================
    def _extract_office_metadata(self, file_path):
        """Trích xuất metadata Office - đơn giản hóa"""
        try:
            from docx import Document
            doc = Document(file_path)
            props = doc.core_properties
            
            tags = {}
            if props.author: tags['Author'] = props.author
            if props.title: tags['Title'] = props.title
            if props.created: tags['Created'] = props.created.strftime("%Y-%m-%d %H:%M:%S")
            if props.modified: tags['Modified'] = props.modified.strftime("%Y-%m-%d %H:%M:%S")
            
            return {'tags': tags, 'author': props.author or '-'}
        except:
            return {'tags': {}, 'author': '-'}

    def _extract_pdf_metadata(self, file_path):
        """Trích xuất metadata PDF - đơn giản hóa"""
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            meta = reader.metadata or {}
            
            tags = {}
            for key, value in meta.items():
                clean_key = str(key).lstrip('/')
                tags[clean_key] = str(value)
            
            author = tags.get('Author', tags.get('Creator', '-'))
            return {'tags': tags, 'author': author}
        except:
            return {'tags': {}, 'author': '-'}

    def _extract_pe_metadata(self, file_path):
        """Trích xuất metadata PE - đơn giản hóa"""
        try:
            import pefile
            pe = pefile.PE(file_path, fast_load=True)
            
            tags = {
                'Machine': hex(pe.FILE_HEADER.Machine),
                'Sections': pe.FILE_HEADER.NumberOfSections,
                'Compiled': datetime.utcfromtimestamp(pe.FILE_HEADER.TimeDateStamp).strftime("%Y-%m-%d %H:%M:%S")
            }
            
            return {'tags': tags, 'author': 'PE File'}
        except:
            return {'tags': {}, 'author': '-'}

    def _extract_image_metadata(self, file_path):
        """Trích xuất metadata hình ảnh - phương án dự phòng đơn giản hóa"""
        try:
            from PIL import Image
            from PIL.ExifTags import TAGS
            
            with Image.open(file_path) as img:
                exif = img._getexif() or {}
                tags = {}
                
                for tag_id, value in exif.items():
                    tag_name = TAGS.get(tag_id, str(tag_id))
                    tags[tag_name] = str(value)
                
                # Trích xuất tác giả/thiết bị
                make = tags.get('Make', '')
                model = tags.get('Model', '')
                artist = tags.get('Artist', '')
                
                author = artist if artist else f"{make} {model}".strip() or '-'
                
                return {'tags': tags, 'author': author}
        except:
            return {'tags': {}, 'author': '-'}