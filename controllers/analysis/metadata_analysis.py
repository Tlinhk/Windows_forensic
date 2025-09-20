from PyQt5.QtWidgets import QWidget, QFileDialog, QMessageBox, QTreeWidgetItem, QAbstractItemView, QListView, QTreeView, QListWidgetItem
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QLoggingCategory, QUrl, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap

import os
import mimetypes
import subprocess
import json
from datetime import datetime

from views.pages.analysis_ui.metadata_analysis_ui import Ui_Form


class SearchWorker(QThread):
    """Thread riêng để tìm kiếm text mà không làm freeze UI"""

    finished = pyqtSignal()
    error = pyqtSignal(str)
    highlights_ready = pyqtSignal(list, object)  # list of (start_pos, length), format

    def __init__(self, text_edit, search_text: str):
        super().__init__()
        self.text_edit = text_edit
        self.search_text = search_text
        self.is_running = True

    def stop(self):
        """Dừng thread"""
        self.is_running = False

    def run(self):
        """Chạy tìm kiếm trong background thread"""
        if not self.is_running:
            return

        content = self.text_edit.toPlainText()
        if not content or not self.search_text:
            return

        # Tìm kiếm trong visible area để tăng tốc độ
        scrollbar = self.text_edit.verticalScrollBar()
        if scrollbar and self.is_running:
            total_lines = content.count('\n') + 1
            visible_lines = 100
            start_line = max(0, scrollbar.value() - visible_lines)
            end_line = min(total_lines, scrollbar.value() + visible_lines * 2)

            lines = content.split('\n')
            if start_line < len(lines):
                search_area = '\n'.join(lines[start_line:end_line])
                # Tính offset trong toàn bộ document
                local_offset = sum(len(line) + 1 for line in lines[:start_line])
            else:
                search_area = content
                local_offset = 0
        else:
            search_area = content
            local_offset = 0

        if not self.is_running:
            return

        # Tìm và highlight
        from PyQt5.QtGui import QTextCharFormat, QBrush, QColor
        from PyQt5.QtCore import Qt

        format = QTextCharFormat()
        format.setBackground(QBrush(QColor("#ffff00")))
        format.setForeground(QBrush(QColor("#000000")))

        search_lower = self.search_text.lower()
        area_lower = search_area.lower()

        # Tìm trong search area
        index = area_lower.find(search_lower)
        highlight_count = 0
        max_highlights = 500

        highlights = []

        while index != -1 and highlight_count < max_highlights and self.is_running:
            global_index = local_offset + index
            highlights.append((global_index, len(self.search_text)))
            index = area_lower.find(search_lower, index + 1)
            highlight_count += 1

        if not self.is_running:
            return

        # Emit highlights để main thread xử lý
        if highlights:
            self.highlights_ready.emit(highlights, format)
        else:
            # Nếu không có highlights, chỉ cần clear highlighting cũ
            self.highlights_ready.emit([], format)

        self.finished.emit()



class MetadataAnalysis(QWidget):
    """Công cụ phân tích metadata cho file/thư mục trong một trang duy nhất."""

    def __init__(self, main_window=None):
        super(MetadataAnalysis, self).__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        
        # Tích hợp cơ sở dữ liệu để báo cáo
        self.main_window = main_window
        self.current_case_id = None
        self.db_manager = None
        try:
            # Loại bỏ cảnh báo ồn ào từ Qt image loader về ICC profile
            QLoggingCategory.setFilterRules("qt.gui.icc=false")
        except Exception:
            pass

        # Kết nối tương tác
        try:
            self.ui.searchMetadataLineEdit.textChanged.connect(self.filter_metadata_tree)
        except Exception:
            pass

        try:
            self.ui.btnRefreshEvidence.clicked.connect(self.refresh_evidence_list)
        except Exception:
            pass

        try:
            self.ui.evidenceListWidget.itemClicked.connect(self.on_evidence_item_clicked)
        except Exception:
            pass

        try:
            self.ui.btnExportMetadata.clicked.connect(self.export_metadata)
        except Exception:
            pass

        try:
            self.ui.btnRefreshMap.clicked.connect(self.refresh_map_location)
        except Exception:
            pass

        # New search boxes for enhanced tabs - sử dụng tìm kiếm tối ưu hiệu suất
        try:
            self.ui.rawSearchLineEdit.textChanged.connect(lambda: self.filter_text_content_immediate(self.ui.rawTextEdit, self.ui.rawSearchLineEdit.text()))
        except Exception:
            pass

        try:
            self.ui.hexSearchLineEdit.textChanged.connect(lambda: self.filter_text_content_immediate(self.ui.hexTextEdit, self.ui.hexSearchLineEdit.text()))
        except Exception:
            pass

        try:
            self.ui.stringsSearchLineEdit.textChanged.connect(lambda: self.filter_text_content_immediate(self.ui.stringsTextEdit, self.ui.stringsSearchLineEdit.text()))
        except Exception:
            pass

        # State
        self.current_file_path = None
        self.exiftool_path = self._find_exiftool()
        self._last_exiftool_tags = None
        self.current_metadata_dict = {}
        self._search_workers = {}
        self._current_search_edit = None  # Track current search text edit


        # Splitter sizing
        try:
            self.ui.workbenchSplitter.setSizes([260, 520, 520])
        except Exception:
            pass

        self._clear_all()
        
        # Load case data if available
        if main_window and hasattr(main_window, 'current_case_id'):
            self.load_case_data(main_window.current_case_id)

        # Kết nối signal cho search highlighting
        self._setup_search_highlighting()

    def _setup_search_highlighting(self):
        """Thiết lập highlighting cho tìm kiếm"""
        # Tạo signal handler để xử lý highlights từ background thread
        def handle_highlights(highlights, format_obj):
            try:
                if not hasattr(self, 'ui') or not self._current_search_edit:
                    return

                # Sử dụng text_edit đã lưu từ search request
                self.apply_highlights_to_edit(self._current_search_edit, highlights, format_obj)

            except Exception as e:
                print(f"Error handling highlights: {e}")

        # Kết nối với SearchWorker signal
        if not hasattr(self, '_highlights_handler'):
            self._highlights_handler = handle_highlights

    def closeEvent(self, event):
        """Cleanup khi widget bị đóng"""
        # Dừng tất cả search workers
        if hasattr(self, '_search_workers'):
            for worker in self._search_workers.values():
                worker.stop()
                worker.wait()
            self._search_workers.clear()

        # Dừng search timer
        if hasattr(self, '_search_timer'):
            self._search_timer.stop()

        # Reset current search edit
        self._current_search_edit = None

        super().closeEvent(event)
    
    def showEvent(self, event):
        """Override showEvent để refresh case data khi widget được hiển thị (tương tự file_analysis)."""
        super().showEvent(event)
        
        # Kiểm tra và cập nhật case_id từ main_window
        if self.main_window and hasattr(self.main_window, 'current_case_id'):
            main_case_id = self.main_window.current_case_id
            # Nếu case đã thay đổi, load case mới
            if main_case_id != self.current_case_id:
                if main_case_id:
                    QTimer.singleShot(100, lambda: self.load_case_data(main_case_id))
                else:
                    # Nếu không có case, reset về trạng thái rỗng
                    self.current_case_id = None
                    # Clear evidence list
                    self.ui.evidenceListWidget.clear()
                    self.ui.evidenceCountLabel.setText("0")

    # ===== Case Management =====
    def set_current_case(self, case_id):
        """Set current case and reload data - called from main window"""
        if case_id != self.current_case_id:
            self.current_case_id = case_id
            self.load_case_data(case_id)
    
    def load_case_data(self, case_id):
        """Load case information for database integration"""
        self.current_case_id = case_id
        
        try:
            from models.db_manager import DatabaseManager
            self.db_manager = DatabaseManager()
            self.db_manager.connect()
            
            case_info = self.db_manager.get_case_with_investigator(case_id)
            if case_info:
                print(f"Metadata Analysis loaded case: {case_info['title']} (ID: {case_id})")
                # Update case info in UI
                self.ui.caseTitleLabel.setText(case_info['title'])
            
            # Load evidence artifacts real-time
            self.load_evidence_artifacts_from_case()
            
            self.db_manager.disconnect()
                    
        except Exception as e:
            print(f"Error loading case data: {e}")
            if self.db_manager:
                self.db_manager.disconnect()
    
    def load_evidence_artifacts_from_case(self):
        """Load evidence artifacts từ case hiện tại - real-time approach like file_analysis"""
        if not self.current_case_id:
            return
            
        try:
            if not self.db_manager:
                from models.db_manager import DatabaseManager
                self.db_manager = DatabaseManager()
                self.db_manager.connect()
            
            # Get all artifacts for this case using correct method name
            artifacts = self.db_manager.get_artifacts_by_case(self.current_case_id)
            
            self.ui.evidenceListWidget.clear()
            evidence_count = 0
            
            # Filter for analyzable file artifacts (not just disk images)
            analyzable_artifacts = []
            for artifact in artifacts:
                evidence_type = artifact.get('evidence_type', '').upper()
                name = artifact.get('name', '').upper()
                source_path = artifact.get('source_path', '')
                
                # Check if it's a file that can be analyzed for metadata
                is_analyzable = False
                
                # Check by evidence_type
                analyzable_types = ['IMAGE_JPEG', 'IMAGE_PNG', 'IMAGE_TIFF', 'DOCUMENT_PDF', 
                                   'DOCUMENT_WORD', 'DOCUMENT_EXCEL', 'EXECUTABLE', 'FILE_OTHER']
                if any(file_type in evidence_type for file_type in analyzable_types):
                    is_analyzable = True
                
                # Check by file extension
                if source_path:
                    ext = os.path.splitext(source_path)[1].lower()
                    analyzable_exts = ['.jpg', '.jpeg', '.png', '.tiff', '.tif', '.bmp', '.gif', 
                                      '.pdf', '.docx', '.xlsx', '.pptx', '.exe', '.dll']
                    if ext in analyzable_exts:
                        is_analyzable = True
                
                if is_analyzable and source_path and os.path.exists(source_path):
                    analyzable_artifacts.append(artifact)
            
            # Add to list widget
            for artifact in analyzable_artifacts:
                # Create display text with file size
                display_name = artifact.get('name', 'Unknown')
                evidence_type = artifact.get('evidence_type', 'Unknown')
                
                # Get file size if available
                source_path = artifact.get('source_path', '')
                size_info = ""
                if source_path and os.path.exists(source_path):
                    try:
                        size_bytes = os.path.getsize(source_path)
                        size_info = f" - {self._format_size(size_bytes)}"
                    except:
                        pass
                
                item_text = f"{display_name} ({evidence_type}){size_info}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, artifact)
                self.ui.evidenceListWidget.addItem(item)
                evidence_count += 1
            
            self.ui.evidenceCountLabel.setText(str(evidence_count))
            
            if evidence_count == 0:
                no_files_item = QListWidgetItem("No analyzable files found in this case")
                no_files_item.setData(Qt.UserRole, None)
                self.ui.evidenceListWidget.addItem(no_files_item)
            
        except Exception as e:
            print(f"Error loading evidence artifacts: {e}")
    
    def refresh_evidence_list(self):
        """Refresh the evidence list"""
        self.load_evidence_artifacts_from_case()
        
    def on_evidence_item_clicked(self, item):
        """Handle clicking on evidence item"""
        try:
            artifact_data = item.data(Qt.UserRole)
            if artifact_data and artifact_data.get('source_path'):
                source_path = artifact_data['source_path']
                if os.path.exists(source_path):
                    print(f"Analyzing file: {source_path}")
                    self.analyze_file(source_path)
                    
                    # Save activity log
                    self.log_analysis_activity(artifact_data)
                else:
                    QMessageBox.warning(self, "File Not Found", f"Source file not found: {source_path}")
            else:
                # Handle no data case
                print("No artifact data or no analyzable files")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error loading evidence: {str(e)}")
    
    def log_analysis_activity(self, artifact_data):
        """Log analysis activity to database"""
        try:
            if not self.db_manager:
                from models.db_manager import DatabaseManager
                self.db_manager = DatabaseManager()
                self.db_manager.connect()
            
            file_name = artifact_data.get('name', 'Unknown')
            self.db_manager.log_activity(
                case_id=self.current_case_id,
                action=f"METADATA_ANALYSIS_START: {file_name}",
                tool_used="Metadata Analysis"
            )
            
            self.db_manager.disconnect()
            
        except Exception as e:
            print(f"Error logging activity: {e}")
            if self.db_manager:
                self.db_manager.disconnect()
    
    def export_metadata(self):
        """Export current metadata to JSON"""
        if not self.current_file_path:
            QMessageBox.information(self, "Export Metadata", "Please select a file first")
            return
            
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self, "Export Metadata", 
                f"{os.path.basename(self.current_file_path)}_metadata.json",
                "JSON Files (*.json)"
            )
            
            if not file_path:
                return
                
            # Export metadata from tree widget
            metadata = {}
            tree = self.ui.metadataTreeWidget
            
            for i in range(tree.topLevelItemCount()):
                group_item = tree.topLevelItem(i)
                group_name = group_item.text(0)
                group_data = {}
                
                for j in range(group_item.childCount()):
                    child_item = group_item.child(j)
                    property_name = child_item.text(0)
                    property_value = child_item.text(1)
                    group_data[property_name] = property_value
                
                metadata[group_name] = group_data
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
                
            QMessageBox.information(self, "Export Complete", f"Metadata exported to:\n{file_path}")
            
        except Exception as e:
            QMessageBox.warning(self, "Export Error", f"Failed to export metadata: {str(e)}")
    
    
    def _guess_mime_type(self, filename):
        """Guess MIME type from filename"""
        import mimetypes
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or "application/octet-stream"
    
    def save_metadata_analysis_to_database(self, file_path, author_text, embedded_times, artifact_id=None):
        """Save metadata analysis results to database"""
        try:
            if not self.db_manager:
                from models.db_manager import DatabaseManager
                self.db_manager = DatabaseManager()
            
            if not self.db_manager.connect():
                print("Failed to connect to database for metadata analysis")
                return None
            
            file_name = os.path.basename(file_path)
            
            # Create comprehensive summary
            summary = f"Metadata Analysis - {file_name}\n"
            summary += f"File Type: {self.ui.fileTypeValueLabel.text()}\n"
            summary += f"File Size: {self.ui.fileSizeValueLabel.text()}\n"
            summary += f"Author/Device: {author_text if author_text != '-' else 'Unknown'}\n"
            
            # Add embedded times
            if embedded_times.get('original') != '-':
                summary += f"Original Date: {embedded_times.get('original')}\n"
            if embedded_times.get('create') != '-':
                summary += f"Created Date: {embedded_times.get('create')}\n"
            if embedded_times.get('modify') != '-':
                summary += f"Modified Date: {embedded_times.get('modify')}\n"
            
            # Add risk analysis - UI element removed in new interface
            try:
                # risk_score = self.ui.riskScoreBadgeLabel.text() if hasattr(self.ui, 'riskScoreBadgeLabel') else "0"
                # summary += f"Risk Score: {risk_score}\n"
                summary += "Risk Score: N/A (UI element removed)\n"
                
                # Add alerts - UI element removed in new interface
                # alerts = []
                # try:
                #     for i in range(self.ui.alertsListWidget.count()):
                #         alerts.append(self.ui.alertsListWidget.item(i).text())
                # except:
                #     pass
                #
                # if alerts:
                #     summary += f"Alerts: {'; '.join(alerts[:3])}...\n"  # First 3 alerts
            except:
                pass
            
            # Add GPS if available
            try:
                if self._last_exiftool_tags:
                    lat = self._last_exiftool_tags.get("GPS:GPSLatitude")
                    lon = self._last_exiftool_tags.get("GPS:GPSLongitude")
                    if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                        summary += f"GPS Location: {lat:.6f},{lon:.6f}\n"
            except:
                pass
            
            # Add hashes
            try:
                md5, sha1, sha256 = self._compute_hashes(file_path)
                summary += f"Hashes: MD5={md5[:16]}..., SHA1={sha1[:16]}..., SHA256={sha256[:16]}..."
            except:
                pass
            
            # Save analysis result only if we have a valid artifact_id
            if artifact_id:
                result_id = self.db_manager.add_analysis_result(
                    artifact_id=artifact_id,  # Link to artifact if available
                    tool_used="Metadata Analysis",
                    summary=summary,
                    result_path=None
                )
            else:
                print("No artifact_id available, skipping database save")
                result_id = None
            
            if result_id:
                # Log the activity
                self.db_manager.log_activity(
                    case_id=self.current_case_id,
                    action=f"METADATA_ANALYSIS: {file_name}",
                    tool_used="Metadata Analysis"
                )
                
                print(f"Metadata analysis saved to database: Result ID {result_id}")
            
            self.db_manager.disconnect()
            return result_id
            
        except Exception as e:
            print(f"Error saving metadata analysis to database: {e}")
            if self.db_manager:
                self.db_manager.disconnect()
            return None
    

    # ===== Public API =====
    def analyze_file(self, file_path: str) -> None:
        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "Metadata", "Không tìm thấy tệp cần phân tích")
            return

        self.current_file_path = file_path
        self._clear_all()

        # Summary basics
        file_name = os.path.basename(file_path)
        file_size_bytes = os.path.getsize(file_path)
        file_size_str = self._format_size(file_size_bytes)
        mime_type, _ = mimetypes.guess_type(file_path)
        file_type_str = mime_type or self._guess_file_type_from_ext(file_name)

        self.ui.fileNameValueLabel.setText(file_name)
        self.ui.fileSizeValueLabel.setText(file_size_str)
        self.ui.fileTypeValueLabel.setText(file_type_str)

        # Thumbnail/icon
        self._populate_thumbnail(file_path)

        # Dấu thời gian hệ thống file (lưu để sử dụng nội bộ nhưng không hiển thị vì không có trong UI mới)
        try:
            stat = os.stat(file_path)
            created = self._format_ts(stat.st_ctime)
            modified = self._format_ts(stat.st_mtime)
            accessed = self._format_ts(stat.st_atime)
            changed = modified  # Fallback; true MFT changed requires NTFS APIs
        except Exception:
            created = modified = accessed = changed = "Unknown"

        # Determine type
        ext = os.path.splitext(file_name.lower())[1]
        is_image = ext in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".gif", ".webp", ".heic"}
        is_pdf = ext == ".pdf"
        is_office = ext in {".docx", ".pptx", ".xlsx"}
        is_exe = ext in {".exe", ".dll", ".sys", ".msi"}

        # Tất cả các tab luôn được bật trong UI mới - không cần điều kiện bật/tắt

        # Thu thập metadata kết hợp ExifTool và các thư viện chuyên biệt
        embedded_times = {"create": "-", "modify": "-", "original": "-"}
        author_text = "-"
        raw_dump_text = None
        exif_author = "-"

        # Bước 1: Luôn thử ExifTool trước để lấy metadata tổng quát
        used_exiftool = False
        if self.exiftool_path:
            try:
                exif_author, embedded_times = self._populate_from_exiftool(file_path)
                # Raw: toàn bộ dump văn bản exiftool
                raw_dump_text = self._run_exiftool_raw_text(file_path)
                used_exiftool = True
            except Exception:
                used_exiftool = False

        # Bước 2: Luôn thêm metadata chuyên biệt dựa trên loại file
        try:
            if is_office:
                # LUÔN trích xuất thuộc tính Office bằng python-docx
                office_props = self._extract_office_properties(file_path)
                if office_props:
                    self._populate_metadata_tree_from_dict(office_props, "Office Properties")
                    # Ưu tiên author từ thuộc tính Office
                    author_text = office_props.get("author") or office_props.get("last_modified_by") or "-"
                self._update_gps(None)
                
            elif is_pdf:
                # LUÔN trích xuất thuộc tính PDF bằng pypdf
                pdf_props = self._extract_pdf_properties(file_path)
                if pdf_props:
                    self._populate_metadata_tree_from_dict(pdf_props, "PDF Properties")
                    # Ưu tiên author từ thuộc tính PDF
                    author_text = pdf_props.get("Author") or pdf_props.get("Creator") or "-"
                self._update_gps(None)
                
            elif is_exe:
                # LUÔN trích xuất thông tin PE bằng pefile
                pe_info = self._extract_pe_info(file_path)
                if pe_info:
                    # Chuyển đổi thông tin PE sang định dạng tree
                    pe_tree_data = {k: v for k, v in pe_info.items() if k != "Imports"}
                    self._populate_metadata_tree_from_dict(pe_tree_data, "PE Header")
                    author_text = pe_info.get("Signature", "-")
                self._update_gps(None)
                
            elif is_image:
                # Đối với hình ảnh, ưu tiên thư viện chuyên biệt khi ExifTool không khả dụng
                if not used_exiftool:
                    meta, gps, embedded_times = self._extract_image_metadata(file_path)
                    author_text = self._compose_author_device(meta)
                    self._populate_metadata_tree(meta)
                    self._update_gps(gps)
                else:
                    # ExifTool đã xử lý metadata hình ảnh và GPS
                    pass  # GPS already handled by _populate_from_exiftool
                    
            else:
                # Đối với các loại file khác, chỉ dựa vào ExifTool
                self._update_gps(None)
                
        except Exception as e:
            QMessageBox.warning(self, "Metadata", f"Lỗi phân tích file chuyên biệt: {str(e)}")

        # Bước 3: Fallback về author từ ExifTool nếu không tìm thấy author chuyên biệt
        if not author_text or author_text == "-":
            author_text = exif_author

        # Tác giả/thiết bị
        self.ui.authorDeviceValueLabel.setText(author_text if author_text else "-")

        # Cập nhật ngày tạo/sửa đổi trong panel bên phải nếu có
        try:
            if hasattr(self.ui, 'createdValueLabel') and hasattr(self.ui, 'modifiedValueLabel'):
                if 'created' in locals() and created != 'Unknown':
                    self.ui.createdValueLabel.setText(created)
                if 'modified' in locals() and modified != 'Unknown':
                    self.ui.modifiedValueLabel.setText(modified)
        except Exception:
            pass

        # Cập nhật widget cảnh báo với phân tích bảo mật trong quá trình xử lý
        try:
            if hasattr(self.ui, 'alertText') and hasattr(self.ui, 'alertTitle'):
                self.ui.alertTitle.setText("🔍 Analyzing Security...")
                self.ui.alertTitle.setStyleSheet("font-weight: bold; font-size: 12px; color: #ffc107;")
                self.ui.alertText.setText("Scanning metadata for security issues...")
                self.ui.alertText.setStyleSheet("font-size: 11px; color: #6c757d;")
        except Exception:
            pass

        # Cập nhật nhãn file hiện tại
        self.ui.currentFileLabel.setText(f"Analyzing: {os.path.basename(file_path)}")

        # Xóa cảnh báo bảo mật trước đó
        try:
            if hasattr(self.ui, 'alertText') and hasattr(self.ui, 'alertTitle'):
                self.ui.alertTitle.setText("🔍 Analyzing Security...")
                self.ui.alertTitle.setStyleSheet("font-weight: bold; font-size: 12px; color: #ffc107;")
                self.ui.alertText.setText("Scanning metadata for security issues...")
                self.ui.alertText.setStyleSheet("font-size: 11px; color: #6c757d;")
        except Exception:
            pass

        # Lưu metadata_dict để phân tích bảo mật sau này
        # Thu thập metadata từ tất cả nguồn để phân tích bảo mật
        self.current_metadata_dict = {}
        try:
            # Lấy metadata từ tree widget nếu có
            if hasattr(self.ui, 'metadataTreeWidget'):
                tree = self.ui.metadataTreeWidget
                for i in range(tree.topLevelItemCount()):
                    group_item = tree.topLevelItem(i)
                    group_name = group_item.text(0)
                    for j in range(group_item.childCount()):
                        child_item = group_item.child(j)
                        tag = child_item.text(1)
                        value = child_item.text(2)
                        if tag and value and value not in ('', '-'):
                            self.current_metadata_dict[tag] = value  # Lưu không có prefix nhóm để phân tích bảo mật
        except Exception:
            self.current_metadata_dict = {}

        # Thông tin chi tiết cho điều tra viên + Văn bản thô
        try:
            insights = self._generate_investigator_insights(
                file_path=file_path,
                fs_created=created,
                embedded_original=embedded_times.get("original", "-"),
                author_text=author_text,
                tags=self._last_exiftool_tags if used_exiftool else None,
            )
            combined = insights
            if raw_dump_text:
                combined = combined + "\n\n" + raw_dump_text
            self.ui.rawTextEdit.setPlainText(combined)
            # Xử lý GPS giờ được thực hiện qua bản đồ nhúng
        except Exception:
            if raw_dump_text is not None:
                self.ui.rawTextEdit.setPlainText(raw_dump_text)
            else:
                if not self.ui.rawTextEdit.toPlainText():
                    self.ui.rawTextEdit.setPlainText("")

        # Hex và strings
        self._populate_hex_and_strings(file_path)

        
        # Lưu kết quả phân tích vào cơ sở dữ liệu nếu case được chọn
        if self.current_case_id:
            # Lấy artifact_id từ item hiện được chọn
            try:
                current_item = self.ui.evidenceListWidget.currentItem()
                if current_item:
                    artifact_data = current_item.data(Qt.UserRole)
                    artifact_id = artifact_data.get('id')
                    # Lưu kết quả phân tích metadata với artifact ID hiện có
                    self.save_metadata_analysis_to_database(file_path, author_text, embedded_times, artifact_id)
            except Exception as e:
                print(f"Error saving metadata analysis: {e}")

        # Cập nhật cảnh báo bảo mật sau khi phân tích hoàn tất
        try:
            if hasattr(self.ui, 'alertText') and hasattr(self.ui, 'alertTitle'):
                # Sử dụng metadata_dict đã lưu để phân tích bảo mật
                security_issues = self._analyze_security_issues(file_path, getattr(self, 'current_metadata_dict', {}))

                if security_issues:
                    self.ui.alertTitle.setText("Security Alerts")
                    self.ui.alertTitle.setStyleSheet("font-weight: bold; font-size: 12px; color: #dc3545;")
                    self.ui.alertText.setText("\n".join([f"{issue}" for issue in security_issues]))
                    self.ui.alertText.setStyleSheet("font-size: 11px; color: #dc3545; font-weight: bold;")
                else:
                    self.ui.alertTitle.setText("No Security Issues")
                    self.ui.alertTitle.setStyleSheet("font-weight: bold; font-size: 12px; color: #28a745;")
                    self.ui.alertText.setText("No suspicious metadata patterns detected")
                    self.ui.alertText.setStyleSheet("font-size: 11px; color: #6c757d;")
        except Exception as e:
            print(f"Error updating security alerts: {e}")

    # ===== Tích hợp ExifTool =====
    def _find_exiftool(self) -> str:
        try:
            # 1) Ghi đè từ biến môi trường
            env_path = os.environ.get("EXIFTOOL_PATH")
            if env_path and os.path.exists(env_path):
                return env_path
            # 2) Tìm trong Windows_forensic/tools/exiftool (lên hai cấp)
            here = os.path.dirname(__file__)  # .../Windows_forensic/pages_functions/analysis
            base_ws = os.path.abspath(os.path.join(here, "..", ".."))  # .../Windows_forensic
            tools_dir_ws = os.path.join(base_ws, "tools", "exiftool")
            candidates = [
                os.path.join(tools_dir_ws, "exiftool.exe"),
                os.path.join(tools_dir_ws, "exiftool(-k).exe"),
            ]
            for c in candidates:
                if os.path.exists(c):
                    return c
            if os.path.isdir(tools_dir_ws):
                for name in os.listdir(tools_dir_ws):
                    if name.lower().startswith("exiftool") and name.lower().endswith(".exe"):
                        return os.path.join(tools_dir_ws, name)
            # 3) Fallback: DoAn/tools/exiftool (lên ba cấp)
            base_doan = os.path.abspath(os.path.join(here, "..", "..", ".."))  # .../DoAn
            tools_dir_doan = os.path.join(base_doan, "tools", "exiftool")
            candidates = [
                os.path.join(tools_dir_doan, "exiftool.exe"),
                os.path.join(tools_dir_doan, "exiftool(-k).exe"),
            ]
            for c in candidates:
                if os.path.exists(c):
                    return c
            if os.path.isdir(tools_dir_doan):
                for name in os.listdir(tools_dir_doan):
                    if name.lower().startswith("exiftool") and name.lower().endswith(".exe"):
                        return os.path.join(tools_dir_doan, name)
        except Exception:
            pass
        return None

    def _run_exiftool_json(self, file_path: str) -> dict:
        if not self.exiftool_path:
            raise RuntimeError("ExifTool not found")
        # Cấu hình mặc định sâu nhưng im lặng
        args = ["-j", "-G1", "-n", "-a", "-u", "-U", "-ee3", "-api", "RequestAll=3"]
        cmd = [self.exiftool_path] + args + [file_path]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "ExifTool error")
        data = json.loads(proc.stdout)
        if not data:
            return {}
        return data[0]

    def _run_exiftool_raw_text(self, file_path: str) -> str:
        if not self.exiftool_path:
            return ""
        args = ["-g1", "-sort", "-a", "-u", "-U", "-ee3", "-api", "RequestAll=3"]
        cmd = [self.exiftool_path] + args + [file_path]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if proc.returncode != 0:
            return proc.stderr.strip()
        # Loại bỏ gợi ý tên công cụ rõ ràng để giữ engine trong suốt
        out = proc.stdout
        try:
            out = out.replace("exiftool", "engine").replace("ExifTool", "Engine")
        except Exception:
            pass
        return out

    def _populate_from_exiftool(self, file_path: str):
        tags = self._run_exiftool_json(file_path)
        self._last_exiftool_tags = dict(tags) if isinstance(tags, dict) else None

        # GPS
        gps_lat = self._first_present(tags, ["GPS:GPSLatitude", "Composite:GPSLatitude"])  # số với -n
        gps_lon = self._first_present(tags, ["GPS:GPSLongitude", "Composite:GPSLongitude"])  # số với -n
        gps = None
        try:
            if gps_lat is not None and gps_lon is not None:
                lat = float(gps_lat)
                lon = float(gps_lon)
                gps = {"lat": lat, "lng": lon}
        except Exception:
            gps = None
        self._update_gps(gps)

        # Thời gian nhúng (ưu tiên EXIF, sau đó QuickTime, XMP/PDF)
        emb_original = self._first_present(tags, [
            "EXIF:DateTimeOriginal", "QuickTime:CreateDate", "XMP:DateTimeOriginal", "XMP:CreateDate", "PDF:CreateDate"
        ])
        emb_create = self._first_present(tags, [
            "EXIF:CreateDate", "XMP:CreateDate", "PDF:CreateDate", "QuickTime:CreateDate"
        ])
        emb_modify = self._first_present(tags, [
            "EXIF:ModifyDate", "XMP:ModifyDate", "PDF:ModifyDate", "QuickTime:ModifyDate"
        ])
        embedded_times = {
            "original": self._normalize_exif_datetime(str(emb_original)) if emb_original else "-",
            "create": self._normalize_exif_datetime(str(emb_create)) if emb_create else "-",
            "modify": self._normalize_exif_datetime(str(emb_modify)) if emb_modify else "-",
        }
        # Thời gian nhúng giờ được xử lý trong cấu trúc cây metadata

        # Tác giả/Thiết bị
        creator = self._first_present(tags, [
            "XMP-dc:Creator", "XMP:Creator", "EXIF:Artist", "IFD0:Artist", "XMP:Author"
        ])
        if isinstance(creator, list):
            creator = ", ".join(map(str, creator))
        make = self._first_present(tags, ["IFD0:Make", "EXIF:Make"]) or ""
        model = self._first_present(tags, ["IFD0:Model", "EXIF:Model"]) or ""
        author_text = "-"
        if creator and (make or model):
            author_text = f"{creator} / {make} {model}".strip()
        elif creator:
            author_text = str(creator)
        elif make or model:
            author_text = f"{make} {model}".strip()
        self.ui.authorDeviceValueLabel.setText(author_text if author_text else "-")

        # Cây metadata được nhóm theo gia đình
        self._populate_metadata_tree_exiftool(tags)

        # Thuộc tính tài liệu giờ được bao gồm trong cây metadata chính

        return author_text, embedded_times

    def _populate_metadata_tree_exiftool(self, tags: dict) -> None:
        try:
            tree = self.ui.metadataTreeWidget
            tree.clear()
            group_to_node = {}
            for k, v in tags.items():
                if ":" not in k:
                    group, tag = "Other", k
                else:
                    group, tag = k.split(":", 1)
                # Bỏ qua một số nhóm ồn ào nếu muốn
                # if group in {"File"}: continue
                if group not in group_to_node:
                    node = QTreeWidgetItem([group, "", ""])
                    group_to_node[group] = node
                    tree.addTopLevelItem(node)
                else:
                    node = group_to_node[group]
                child = QTreeWidgetItem(["", tag, self._stringify_exiftool_value(v)])
                node.addChild(child)
            tree.expandAll()
        except Exception:
            pass

    def _stringify_exiftool_value(self, v):
        try:
            if isinstance(v, list):
                return ", ".join(map(str, v))
            return str(v)
        except Exception:
            return ""

    def _first_present(self, d: dict, keys: list):
        for key in keys:
            if key in d and d[key] not in (None, ""):
                return d[key]
        return None
    
    def _populate_metadata_tree_from_dict(self, data: dict, group_name: str) -> None:
        """Điền cây metadata từ dictionary thuộc tính"""
        try:
            tree = self.ui.metadataTreeWidget

            # Tạo hoặc tìm node nhóm
            group_node = None
            for i in range(tree.topLevelItemCount()):
                item = tree.topLevelItem(i)
                if item.text(0) == group_name:
                    group_node = item
                    break

            if group_node is None:
                group_node = QTreeWidgetItem([group_name, "", ""])
                tree.addTopLevelItem(group_node)

            # Thêm thuộc tính vào nhóm
            for key, value in data.items():
                if value not in (None, "", "-"):
                    child = QTreeWidgetItem(["", str(key), str(value)])
                    group_node.addChild(child)

            tree.expandAll()
        except Exception as e:
            print(f"Error in _populate_metadata_tree_from_dict: {e}")
            import traceback
            traceback.print_exc()
    
    def _populate_metadata_tree(self, meta: dict) -> None:
        """Điền cây metadata từ metadata hình ảnh"""
        try:
            tree = self.ui.metadataTreeWidget
            tree.clear()
            
            # Nhóm metadata theo danh mục
            groups = {
                "Image": [
                    "Image Make", "Image Model", "Image Orientation", "Image XResolution", "Image YResolution",
                    "Composite ImageSize", "EXIF ExifImageWidth", "EXIF ExifImageHeight",
                ],
                "Camera Settings": [
                    "EXIF FNumber", "EXIF ExposureTime", "EXIF ISOSpeedRatings", "EXIF ExposureProgram",
                    "EXIF FocalLength", "EXIF Flash", "EXIF MeteringMode", "EXIF LightSource",
                ],
                "GPS": [
                    "GPS GPSLatitude", "GPS GPSLongitude", "GPS GPSAltitude", "GPS GPSMapDatum", "GPS GPSTimeStamp",
                ],
                "File Information": [
                    "Image Software", "EXIF ModifyDate", "EXIF CreateDate", "EXIF DateTimeOriginal", "File Name",
                ],
            }
            
            group_nodes = {}
            for group_name in groups.keys():
                node = QTreeWidgetItem([group_name, "", ""])
                group_nodes[group_name] = node
                tree.addTopLevelItem(node)

            added_keys = set()
            for group_name, keys in groups.items():
                group_item = group_nodes[group_name]
                for key in keys:
                    if key in meta:
                        value = str(meta.get(key, ""))
                        group_item.addChild(QTreeWidgetItem(["", key, value]))
                        added_keys.add(key)

            # Thêm metadata còn lại vào nhóm "Others"
            others = QTreeWidgetItem(["Others", "", ""])
            has_others = False
            for k, v in meta.items():
                if k not in added_keys:
                    others.addChild(QTreeWidgetItem(["", k, str(v)]))
                    has_others = True
            
            if has_others:
                tree.addTopLevelItem(others)

            tree.expandAll()
        except Exception:
            pass

    # ===== Thông tin chi tiết cho điều tra viên =====
    def _generate_investigator_insights(self, file_path: str, fs_created: str, embedded_original: str, author_text: str, tags: dict | None) -> str:
        hints = []
        score = 0

        # Mã băm
        try:
            md5, sha1, sha256 = self._compute_hashes(file_path)
            hints.append(f"Hashes: MD5={md5} | SHA1={sha1} | SHA256={sha256}")
        except Exception:
            pass

        # Sự khác biệt thời gian (đã được đánh dấu trực quan)
        try:
            def parse(dt):
                try:
                    return datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    return None
            t_fs = parse(fs_created)
            t_emb = parse(embedded_original)
            if t_fs and t_emb:
                delta_days = abs((t_fs - t_emb).total_seconds()) / 86400.0
                if delta_days > 1:
                    score += 2
                    hints.append(f"Anomaly: FileCreated vs EmbeddedOriginal differ by ~{delta_days:.1f} days")
        except Exception:
            pass

        # Chỉ báo phần mềm chỉnh sửa
        try:
            software = None
            if tags:
                for k in ("EXIF:Software", "IFD0:Software", "XMP:Software", "XMP:CreatorTool"):
                    if k in tags and tags[k]:
                        software = str(tags[k])
                        break
            if software:
                sw_low = software.lower()
                editors = ["photoshop", "lightroom", "gimp", "snapseed", "pixelmator", "paint.net", "canva"]
                if any(e in sw_low for e in editors):
                    score += 1
                    hints.append(f"Indicator: Editing software present ({software})")
        except Exception:
            pass

        # Metadata thiếu trong hình ảnh (có thể bị xóa)
        try:
            ext = os.path.splitext(file_path.lower())[1]
            if ext in (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp") and tags is not None:
                # Đếm nhóm EXIF
                exif_keys = [k for k in tags.keys() if k.startswith("EXIF:") or k.startswith("IFD0:")]
                if len(exif_keys) < 3:
                    score += 1
                    hints.append("Indicator: Very few EXIF tags detected (possible metadata stripping)")
        except Exception:
            pass

        # Ngữ cảnh tác giả/thiết bị
        if author_text and author_text != "-":
            hints.append(f"Author/Device: {author_text}")

        # Ngữ cảnh GPS + liên kết bản đồ
        try:
            lat = lon = None
            if tags and "GPS:GPSLatitude" in tags and "GPS:GPSLongitude" in tags:
                lat = tags.get("GPS:GPSLatitude")
                lon = tags.get("GPS:GPSLongitude")
            if isinstance(lat, (float, int)) and isinstance(lon, (float, int)):
                maps = f"https://maps.google.com/?q={lat},{lon}"
                hints.append(f"Location: {lat:.6f},{lon:.6f} | Map: {maps}")
        except Exception:
            pass

        # Phân tích rủi ro được đơn giản hóa trong UI mới - chỉ bao gồm trong văn bản thô

        # Điểm tổng kết trong văn bản
        hints_text = [f"Risk Score (heuristic): {score}"] + hints
        preface = "=== Investigator Insights ===\n" + "\n".join(f"- {h}" for h in hints_text)
        return preface

    def _compute_hashes(self, file_path: str):
        import hashlib
        md5 = hashlib.md5()
        sha1 = hashlib.sha1()
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                md5.update(chunk)
                sha1.update(chunk)
                sha256.update(chunk)
        return md5.hexdigest(), sha1.hexdigest(), sha256.hexdigest()

    # _build_exiftool_flags function removed - flags are now hardcoded in individual methods

    # ===== Trợ giúp UI - đơn giản hóa cho giao diện mới =====

    # ===== Đặt lại UI =====
    def _clear_all(self) -> None:
        try:
            self.ui.thumbnailLabel.setPixmap(QPixmap())
            self.ui.thumbnailLabel.setText("Thumbnail / Preview")
            self.ui.fileNameValueLabel.setText("-")
            self.ui.fileTypeValueLabel.setText("-")
            self.ui.fileSizeValueLabel.setText("-")
            self.ui.authorDeviceValueLabel.setText("-")
            self.ui.currentFileLabel.setText("No file selected")
            
            try:
                self.ui.metadataTreeWidget.clear()
            except Exception:
                pass
            try:
                self.ui.rawTextEdit.clear()
                self.ui.hexTextEdit.clear()
                self.ui.stringsTextEdit.clear()
            except Exception:
                pass
            try:
                self.ui.currentLocationLabel.setText("No GPS data available")
                self.ui.currentLocationLabel.setStyleSheet("font-style: italic; color: #6c757d;")
            except Exception:
                pass
        except Exception:
            pass

    # ===== Trợ giúp tóm tắt nhanh =====
    def _populate_thumbnail(self, file_path: str) -> None:
        """Điền thumbnail từ hình ảnh"""
        try:
            pix = QPixmap(file_path)
            if not pix.isNull():
                scaled = pix.scaled(220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.ui.thumbnailLabel.setPixmap(scaled)
                self.ui.thumbnailLabel.setText("")
            else:
                self.ui.thumbnailLabel.setText("Thumbnail / Preview")
        except Exception:
            self.ui.thumbnailLabel.setText("Thumbnail / Preview")

    def _update_gps(self, gps: dict) -> None:
        """Cập nhật thông tin GPS"""
        try:
            if gps and isinstance(gps, dict) and 'lat' in gps and 'lng' in gps:
                lat, lng = gps['lat'], gps['lng']
                # Cập nhật bản đồ nhúng
                self._update_embedded_map(lat, lng)
                # Cập nhật nhãn vị trí
                self.ui.currentLocationLabel.setText(f"{lat:.6f}, {lng:.6f}")
                self.ui.currentLocationLabel.setStyleSheet("QLabel { color: #28a745; font-weight: bold; }")
                # Dữ liệu GPS có sẵn - bật chức năng làm mới bản đồ
            else:
                # Không có dữ liệu GPS
                self.ui.currentLocationLabel.setText("Không có dữ liệu GPS")
                self.ui.currentLocationLabel.setStyleSheet("QLabel { color: #6c757d; font-style: italic; }")
                # Đặt lại bản đồ về mặc định
                self._reset_embedded_map()
        except Exception:
            pass

    # Cảnh báo khác biệt không còn trong UI mới - được xử lý trong văn bản thông tin chi tiết

    # ===== Trích xuất dữ liệu =====
    def _extract_image_metadata(self, file_path: str):
        meta = {}
        gps = None
        embedded = {"create": "-", "modify": "-", "original": "-"}
        # exifread
        try:
            import exifread  # type: ignore

            with open(file_path, "rb") as f:
                tags = exifread.process_file(f, details=False)
            for k, v in tags.items():
                meta[str(k)] = str(v)

            gps = self._parse_gps_from_exifread(tags)
            embedded["original"] = meta.get("EXIF DateTimeOriginal", "-")
            embedded["create"] = meta.get("EXIF CreateDate", meta.get("Image DateTime", "-"))
            embedded["modify"] = meta.get("EXIF ModifyDate", meta.get("Image DateTime", "-"))
            for key in list(embedded.keys()):
                embedded[key] = self._normalize_exif_datetime(embedded[key])
            return meta, gps, embedded
        except Exception:
            pass

        # Dự phòng Pillow
        try:
            from PIL import Image  # type: ignore
            from PIL.ExifTags import TAGS, GPSTAGS  # type: ignore

            def get_exif(img):
                info = img._getexif() or {}
                result = {}
                for tag, value in info.items():
                    decoded = TAGS.get(tag, tag)
                    result[str(decoded)] = value
                return result

            with Image.open(file_path) as img:
                exif = get_exif(img)
                for k, v in exif.items():
                    meta[str(k)] = str(v)

                gps_info = exif.get("GPSInfo")
                if gps_info:
                    gps = self._parse_gps_from_pillow(gps_info, GPSTAGS)

                embedded["original"] = str(exif.get("DateTimeOriginal", "-") or "-")
                embedded["create"] = str(exif.get("CreateDate", exif.get("DateTime", "-") or "-"))
                embedded["modify"] = str(exif.get("ModifyDate", exif.get("DateTime", "-") or "-"))
                for key in list(embedded.keys()):
                    embedded[key] = self._normalize_exif_datetime(embedded[key])
            return meta, gps, embedded
        except Exception:
            return meta, None, embedded

    def _extract_pdf_properties(self, file_path: str) -> dict:
        props = {}
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(file_path)
            meta = reader.metadata or {}
            for k, v in meta.items():
                key = str(k).lstrip("/")
                props[key] = str(v)
        except Exception:
            pass
        return props

    def _analyze_security_issues(self, file_path: str, metadata_dict: dict) -> list:
        """Phân tích metadata để tìm các vấn đề bảo mật có thể chỉ ra hoạt động độc hại"""
        issues = []

        try:
            # Kiểm tra phần mở rộng file đáng ngờ trong metadata
            file_name = os.path.basename(file_path).lower()

            # Kiểm tra phần mở rộng kép (có thể là malware)
            if file_name.count('.') > 1:
                parts = file_name.split('.')
                if len(parts) >= 3 and parts[-2] + '.' + parts[-1] != 'docx':  # Cho phép phần mở rộng kép bình thường như .tar.gz, .docx
                    issues.append(f"Double file extension detected: {'.'.join(parts[-2:])}")

            # Kiểm tra tên tác giả đáng ngờ
            author_keys = ['Author', 'Creator', 'LastModifiedBy', 'LastSavedBy', 'Company', 'Manager']
            for key in author_keys:
                if key in metadata_dict and metadata_dict[key]:
                    author = str(metadata_dict[key]).lower()
                    suspicious_authors = ['unknown', 'user', 'admin', 'administrator', 'system', 'root', 'test']
                    if author in suspicious_authors:
                        issues.append(f"Suspicious author name: {metadata_dict[key]}")

            # Kiểm tra sửa đổi gần đây nhưng ngày tạo cũ (có thể bị giả mạo)
            created_keys = ['CreateDate', 'CreationDate', 'DateCreated']
            modified_keys = ['ModifyDate', 'LastModified', 'DateModified']
            created_val = None
            modified_val = None

            for key in created_keys:
                if key in metadata_dict and metadata_dict[key] and metadata_dict[key] != '-':
                    created_val = metadata_dict[key]
                    break

            for key in modified_keys:
                if key in metadata_dict and metadata_dict[key] and metadata_dict[key] != '-':
                    modified_val = metadata_dict[key]
                    break

            if created_val and modified_val:
                try:
                    # Simple check if modified is much newer than created
                    if '2025' in modified_val and '2010' in created_val:
                        issues.append("File recently modified but claims old creation date")
                except:
                    pass

            # Kiểm tra script hoặc macro nhúng trong file Office
            if file_path.lower().endswith(('.docx', '.xlsx', '.pptx', '.doc', '.xls', '.ppt')):
                macro_keys = ['Macro', 'VBA', 'EmbeddedScript', 'Script']
                for key in macro_keys:
                    if key in metadata_dict and metadata_dict[key]:
                        issues.append("Embedded macros/VBA detected in Office document")
                        break

            # Kiểm tra kích thước file đáng ngờ
            try:
                file_size = os.path.getsize(file_path)
                if file_size == 0:
                    issues.append("Empty file detected")
                elif file_size > 100 * 1024 * 1024:  # 100MB
                    issues.append(f"Large file size: {file_size / (1024*1024):.1f} MB")
            except:
                pass

            # Kiểm tra công cụ tạo file đáng ngờ    
            software_keys = ['Software', 'Producer', 'CreatorTool', 'Generator']
            for key in software_keys:
                if key in metadata_dict and metadata_dict[key]:
                    software = str(metadata_dict[key]).lower()
                    suspicious_software = ['malware', 'virus', 'trojan', 'hack', 'exploit', 'suspicious']
                    for sw in suspicious_software:
                        if sw in software:
                            issues.append(f"Suspicious software detected: {metadata_dict[key]}")
                            break

            # Kiểm tra file ẩn
            if os.path.basename(file_path).startswith('.'):
                issues.append("Hidden file detected (starts with '.')")

            # Kiểm tra nội dung thực thi trong file không phải thực thi
            if not file_path.lower().endswith(('.exe', '.dll', '.com', '.bat', '.cmd', '.scr', '.msi')):
                try:
                    with open(file_path, 'rb') as f:
                        content = f.read(1024)  # Đọc 1KB đầu tiên
                        if b'MZ' in content or b'PK\x03\x04' in content:  # Header MZ hoặc ZIP
                            issues.append("Executable or archive content detected in non-executable file")
                except:
                    pass

        except Exception as e:
            issues.append(f"Error during security analysis: {str(e)}")

        return issues

    def _extract_office_properties(self, file_path: str) -> dict:
        """Trích xuất thuộc tính Office từ file"""
        props = {}
        try:
            from docx import Document  # type: ignore

            doc = Document(file_path)
            core = doc.core_properties

            # Danh sách thuộc tính có sẵn trong python-docx
            available_props = {
                "title": core.title,
                "subject": core.subject,
                "author": core.author,
                "last_modified_by": core.last_modified_by,
                "revision": core.revision,
                "created": self._format_dt(core.created) if core.created else "",
                "modified": self._format_dt(core.modified) if core.modified else "",
                "category": core.category,
                "comments": core.comments,
                "keywords": core.keywords,
                "content_status": core.content_status,
                "identifier": core.identifier,
                "language": core.language,
                "version": core.version,
            }

            # Lọc bỏ các giá trị None và rỗng
            props = {k: v for k, v in available_props.items() if v not in (None, "")}

        except Exception as e:
            print(f"Error extracting Office properties: {e}")

        return props

    def _extract_pe_info(self, file_path: str) -> dict:
        """Trích xuất thông tin PE từ file thực thi"""
        info = {}
        try:
            import pefile  # type: ignore

            pe = pefile.PE(file_path, fast_load=True)
            pe.parse_data_directories()

            compile_time = None
            try:
                ts = pe.FILE_HEADER.TimeDateStamp
                compile_time = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S UTC")
            except Exception:
                pass

            info.update({
                "Machine": hex(pe.FILE_HEADER.Machine) if hasattr(pe.FILE_HEADER, "Machine") else "",
                "NumberOfSections": getattr(pe.FILE_HEADER, "NumberOfSections", ""),
                "TimeDateStamp": compile_time or "",
                "Characteristics": hex(pe.FILE_HEADER.Characteristics) if hasattr(pe.FILE_HEADER, "Characteristics") else "",
                "EntryPoint": hex(pe.OPTIONAL_HEADER.AddressOfEntryPoint) if hasattr(pe, "OPTIONAL_HEADER") else "",
                "ImageBase": hex(pe.OPTIONAL_HEADER.ImageBase) if hasattr(pe, "OPTIONAL_HEADER") else "",
                "Subsystem": getattr(pe.OPTIONAL_HEADER, "Subsystem", ""),
                "DllCharacteristics": getattr(pe.OPTIONAL_HEADER, "DllCharacteristics", ""),
                "Signature": "Signed" if hasattr(pe, "DIRECTORY_ENTRY_SECURITY") else "Unsigned",
            })

            imports = []
            try:
                for entry in getattr(pe, "DIRECTORY_ENTRY_IMPORT", []) or []:
                    dll_name = entry.dll.decode(errors="ignore") if entry.dll else ""
                    for imp in entry.imports or []:
                        func = imp.name.decode(errors="ignore") if imp.name else f"Ordinal_{imp.ordinal}"
                        imports.append((dll_name, func))
            except Exception:
                pass

            info["Imports"] = imports
        except Exception:
            pass
        return info

    # ===== Điền widget - loại bỏ các phương thức bảng cũ, sử dụng cây =====

    def _populate_hex_and_strings(self, file_path: str, max_bytes: int = 1024 * 1024) -> None:
        try:
            data = b""
            try:
                with open(file_path, "rb") as f:
                    data = f.read(max_bytes)
                self.ui.hexTextEdit.setPlainText(self._generate_hex_view(data))
            except Exception:
                self.ui.hexTextEdit.setPlainText("")
            try:
                strings = self._extract_strings_from_bytes(data)
                self.ui.stringsTextEdit.setPlainText("\n".join(strings))
            except Exception:
                self.ui.stringsTextEdit.setPlainText("")
        except Exception:
            pass

    # ===== Tìm kiếm/lọc =====
    def filter_metadata_tree(self, text: str) -> None:
        try:
            pattern = (text or "").strip().lower()
            tree = self.ui.metadataTreeWidget
            for i in range(tree.topLevelItemCount()):
                top = tree.topLevelItem(i)
                self._filter_tree_item(top, pattern, text)
        except Exception:
            pass

    def _filter_tree_item(self, item: QTreeWidgetItem, pattern: str, search_text: str = "") -> bool:
        if not pattern:
            item.setHidden(False)
            for i in range(item.childCount()):
                self._filter_tree_item(item.child(i), pattern, search_text)
            return True

        text = (item.text(0) + " " + item.text(1) + " " + item.text(2)).lower()
        matched = pattern in text
        child_match = False
        for i in range(item.childCount()):
            if self._filter_tree_item(item.child(i), pattern, search_text):
                child_match = True

        item.setHidden(not (matched or child_match))

        # Làm nổi bật văn bản khớp
        if search_text and matched:
            # Điều này sẽ yêu cầu implementation phức tạp hơn với QTextDocument
            # Hiện tại, chỉ đánh dấu item
            pass

        return matched or child_match

    def filter_text_content(self, text_edit, search_text: str) -> None:
        """Lọc và làm nổi bật nội dung văn bản trong QPlainTextEdit - tối ưu hiệu suất"""
        try:
            if not search_text:
                # Xóa highlighting khi không có search text
                self._clear_text_highlighting(text_edit)
                return

            # Sử dụng QTimer để tìm kiếm bất đồng bộ để tránh UI freeze
            if not hasattr(self, '_search_timer'):
                self._search_timer = QTimer()
                self._search_timer.setSingleShot(True)
                self._search_timer.timeout.connect(lambda: self._perform_text_search(text_edit, search_text))

            # Delay search để tránh spam khi user typing
            self._search_timer.start(100)  # 100ms delay

        except Exception as e:
            print(f"Error filtering text content: {e}")

    def filter_text_content_immediate(self, text_edit, search_text: str) -> None:
        """Tìm kiếm ngay lập tức trong visible area - cho hiệu suất cao nhất"""
        try:
            if not search_text:
                self._clear_text_highlighting(text_edit)
                return

            # Sử dụng thread riêng để tìm kiếm không đồng bộ
            if not hasattr(self, '_search_workers'):
                self._search_workers = {}

            # Tạo unique key cho text_edit
            edit_key = id(text_edit)

            # Dừng thread cũ nếu đang chạy
            if edit_key in self._search_workers:
                self._search_workers[edit_key].stop()
                self._search_workers[edit_key].wait()

            # Lưu text_edit hiện tại đang search
            self._current_search_edit = text_edit

            # Tạo thread mới
            worker = SearchWorker(text_edit, search_text)
            worker.finished.connect(lambda: self._on_search_finished(edit_key))
            worker.error.connect(lambda msg: print(f"Search error: {msg}"))
            worker.highlights_ready.connect(self._highlights_handler)
            self._search_workers[edit_key] = worker
            worker.start()

        except Exception as e:
            print(f"Error in immediate text search: {e}")

    def _on_search_finished(self, edit_key: int) -> None:
        """Callback khi tìm kiếm hoàn thành"""
        if edit_key in self._search_workers:
            del self._search_workers[edit_key]

    def _clear_text_highlighting(self, text_edit) -> None:
        """Xóa tất cả highlighting trong text edit"""
        try:
            cursor = text_edit.textCursor()
            cursor.select(cursor.Document)
            # Chỉ reset format mà không thay đổi text
            normal_format = cursor.charFormat()
            cursor.setCharFormat(normal_format)
            cursor.clearSelection()
            text_edit.setTextCursor(cursor)

            # Reset current search edit nếu là text_edit này
            if hasattr(self, '_current_search_edit') and self._current_search_edit == text_edit:
                self._current_search_edit = None
        except Exception:
            pass

    def apply_highlights_to_edit(self, text_edit, highlights, format_obj):
        """Apply highlights to specific text edit - chạy trong main thread"""
        try:
            self._clear_text_highlighting(text_edit)

            if highlights:
                cursor = text_edit.textCursor()
                for start_pos, length in highlights:
                    cursor.setPosition(start_pos)
                    cursor.setPosition(start_pos + length, cursor.KeepAnchor)
                    cursor.setCharFormat(format_obj)

        except Exception as e:
            print(f"Error applying highlights to {text_edit.objectName() if hasattr(text_edit, 'objectName') else 'text_edit'}: {e}")

    def _perform_text_search(self, text_edit, search_text: str) -> None:
        """Thực hiện tìm kiếm và highlight - tối ưu hiệu suất"""
        try:
            # Kiểm tra search text vẫn còn hợp lệ
            if not search_text or not hasattr(self, 'ui'):
                return

            content = text_edit.toPlainText()
            if not content:
                return

            # Xóa highlighting trước đó một cách hiệu quả
            self._clear_text_highlighting(text_edit)

            # Tối ưu hóa: giới hạn số lượng highlights để tránh lag
            max_highlights = 1000
            highlight_count = 0

            # Tìm và làm nổi bật văn bản tìm kiếm
            from PyQt5.QtGui import QTextCharFormat, QBrush, QColor
            from PyQt5.QtCore import Qt

            format = QTextCharFormat()
            format.setBackground(QBrush(QColor("#ffff00")))  # Làm nổi bật màu vàng
            format.setForeground(QBrush(QColor("#000000")))  # Văn bản màu đen

            # Tìm tất cả các lần xuất hiện với giới hạn
            search_lower = search_text.lower()
            content_lower = content.lower()
            index = content_lower.find(search_lower)

            cursor = text_edit.textCursor()
            while index != -1 and highlight_count < max_highlights:
                # Set format cho occurrence này
                cursor.setPosition(index)
                cursor.setPosition(index + len(search_text), cursor.KeepAnchor)
                cursor.setCharFormat(format)

                # Tìm occurrence tiếp theo
                index = content_lower.find(search_lower, index + 1)
                highlight_count += 1

            # Hiển thị thông tin về số lượng highlights
            if highlight_count >= max_highlights:
                print(f"Đã đạt giới hạn {max_highlights} highlights, có thể có thêm kết quả")

        except Exception as e:
            print(f"Error performing text search: {e}")

    # ===== Tiện ích =====
    # Hàm _new_table_item đã bị xóa - các phương thức bảng cũ không còn sử dụng trong UI dựa trên cây

    def _format_size(self, size_bytes: int) -> str:
        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(size_bytes)
        idx = 0
        while size >= 1024 and idx < len(units) - 1:
            size /= 1024.0
            idx += 1
        return f"{size:.1f} {units[idx]}"

    def _format_ts(self, ts: float) -> str:
        try:
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return "Unknown"

    def _format_dt(self, dt) -> str:
        try:
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return ""

    def _guess_file_type_from_ext(self, filename: str) -> str:
        ext = os.path.splitext(filename)[1].lower()
        mapping = {
            ".txt": "Text File", ".doc": "Word Document", ".docx": "Word Document",
            ".pdf": "PDF Document", ".rtf": "Rich Text", ".odt": "OpenDocument",
            ".xls": "Excel Spreadsheet", ".xlsx": "Excel Spreadsheet",
            ".ppt": "PowerPoint", ".pptx": "PowerPoint",
            ".jpg": "JPEG Image", ".jpeg": "JPEG Image", ".png": "PNG Image",
            ".gif": "GIF Image", ".bmp": "Bitmap Image", ".tiff": "TIFF Image",
            ".svg": "SVG Image", ".ico": "Icon File",
        }
        return mapping.get(ext, (mimetypes.guess_type(filename)[0] or "Unknown"))

    def _compose_author_device(self, meta: dict) -> str:
        creator = meta.get("Image Artist") or meta.get("EXIF Artist") or meta.get("Creator") or meta.get("Author")
        make = meta.get("Image Make") or meta.get("Make")
        model = meta.get("Image Model") or meta.get("Model")
        if creator and (make or model):
            return f"{creator} / {make or ''} {model or ''}".strip()
        if creator:
            return creator
        if make or model:
            return f"{make or ''} {model or ''}".strip()
        return "-"

    def _normalize_exif_datetime(self, value: str) -> str:
        if not value or value == "-":
            return "-"
        v = value.strip()
        try:
            if ":" in v[:10]:
                v2 = v.replace("/", ":")
                parts = v2.split()
                date = parts[0].replace(":", "-", 2)
                time = parts[1] if len(parts) > 1 else "00:00:00"
                return f"{date} {time}"
        except Exception:
            pass
        return v

    def _parse_gps_from_exifread(self, tags) -> dict:
        try:
            lat = self._convert_gps(tags.get("GPS GPSLatitude"), tags.get("GPS GPSLatitudeRef"))
            lng = self._convert_gps(tags.get("GPS GPSLongitude"), tags.get("GPS GPSLongitudeRef"))
            if lat is not None and lng is not None:
                return {"lat": lat, "lng": lng}
        except Exception:
            pass
        return None

    def _parse_gps_from_pillow(self, gps_info, GPSTAGS) -> dict:
        try:
            gps_data = {}
            for key in gps_info.keys():
                name = GPSTAGS.get(key, key)
                gps_data[name] = gps_info[key]
            lat = self._convert_gps(gps_data.get("GPSLatitude"), gps_data.get("GPSLatitudeRef"))
            lng = self._convert_gps(gps_data.get("GPSLongitude"), gps_data.get("GPSLongitudeRef"))
            if lat is not None and lng is not None:
                return {"lat": lat, "lng": lng}
        except Exception:
            pass
        return None

    def _convert_gps(self, value, ref) -> float:
        if not value or not ref:
            return None
        try:
            # exifread may return a Tag with .values; Pillow returns tuple/list
            if hasattr(value, "values"):
                parts = list(value.values)
            else:
                parts = list(value) if isinstance(value, (list, tuple)) else None
            if not parts or len(parts) < 3:
                return None

            def to_float(x):
                try:
                    # exifread Ratio
                    return float(x.num) / float(x.den)
                except Exception:
                    try:
                        return float(x)
                    except Exception:
                        return 0.0

            d, m, s = parts[0], parts[1], parts[2]
            deg = to_float(d) + to_float(m) / 60.0 + to_float(s) / 3600.0
            ref_str = str(ref)
            if ref_str in ("S", "W"):
                deg = -deg
            return deg
        except Exception:
            return None

    # ===== So sánh/ghim =====

    def _generate_hex_view(self, data: bytes, width: int = 16) -> str:
        try:
            lines = []
            for i in range(0, len(data), width):
                chunk = data[i:i + width]
                hex_bytes = " ".join(f"{b:02x}" for b in chunk)
                ascii_chars = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
                lines.append(f"{i:08x}  {hex_bytes:<{width * 3}} |{ascii_chars}|")
            return "\n".join(lines)
        except Exception:
            return ""

    def _extract_strings_from_bytes(self, data: bytes, min_len: int = 4) -> list:
        try:
            import re
            pattern = re.compile(rb"[\x20-\x7E]{" + str(min_len).encode() + rb",}")
            strings = [m.group().decode("latin1", errors="ignore") for m in pattern.finditer(data or b"")]
            return strings[:10000]
        except Exception:
            return []

    # ===== Phương thức bản đồ nhúng =====
    def _update_embedded_map(self, lat: float, lng: float) -> None:
        """Cập nhật bản đồ Google Maps nhúng để hiển thị vị trí GPS"""
        try:
            # Tạo URL Google Maps với marker và zoom tốt hơn
            maps_url = f"https://maps.google.com/maps?q={lat},{lng}&ll={lat},{lng}&z=16&t=h"
            self.ui.mapView.setUrl(QUrl(maps_url))
            print(f"Map updated with coordinates: {lat}, {lng}")
        except Exception as e:
            print(f"Error updating map: {e}")
            pass

    def _reset_embedded_map(self) -> None:
        """Đặt lại bản đồ nhúng về chế độ xem mặc định"""
        try:
            self.ui.mapView.setUrl(QUrl("https://maps.google.com"))
        except Exception:
            pass


    def refresh_map_location(self) -> None:
        """Làm mới bản đồ với dữ liệu GPS hiện tại"""
        try:
            if hasattr(self, '_last_exiftool_tags') and self._last_exiftool_tags:
                lat = self._last_exiftool_tags.get("GPS:GPSLatitude")
                lon = self._last_exiftool_tags.get("GPS:GPSLongitude")
                if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                    self._update_embedded_map(lat, lon)
                    QMessageBox.information(self, "Map", "GPS location updated on map!")
                else:
                    QMessageBox.information(self, "Map", "No GPS data found in current file.")
            else:
                QMessageBox.information(self, "Map", "Please analyze a file with GPS data first.")
        except Exception:
            QMessageBox.warning(self, "Map", "Error refreshing map.")