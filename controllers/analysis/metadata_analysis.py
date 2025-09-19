from PyQt5.QtWidgets import QWidget, QFileDialog, QMessageBox, QTreeWidgetItem, QTableWidgetItem, QAbstractItemView, QListView, QTreeView, QListWidgetItem
from PyQt5 import QtWidgets
from PyQt5.QtCore import Qt, QLoggingCategory, QUrl, QTimer
from PyQt5.QtGui import QPixmap

import os
import mimetypes
import subprocess
import json
import shlex
from datetime import datetime

from views.pages.analysis_ui.metadata_analysis_ui import Ui_Form


class MetadataAnalysis(QWidget):
    """Single-page workbench for file/folder metadata analysis."""

    def __init__(self, main_window=None):
        super(MetadataAnalysis, self).__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        
        # Database integration for reporting
        self.main_window = main_window
        self.current_case_id = None
        self.db_manager = None
        try:
            # Suppress noisy ICC profile warnings from Qt image loader
            QLoggingCategory.setFilterRules("qt.gui.icc=false")
        except Exception:
            pass

        # Wire interactions
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

        # State
        self.current_file_path = None
        self.exiftool_path = self._find_exiftool()
        self._last_exiftool_tags = None


        # Splitter sizing
        try:
            self.ui.workbenchSplitter.setSizes([260, 520, 520])
        except Exception:
            pass

        self._clear_all()
        
        # Load case data if available
        if main_window and hasattr(main_window, 'current_case_id'):
            self.load_case_data(main_window.current_case_id)
    
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
                tool_used="Metadata Analysis",
                details=f"Started metadata analysis for {file_name}"
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
            
            # Add risk analysis
            try:
                risk_score = self.ui.riskScoreBadgeLabel.text() if hasattr(self.ui, 'riskScoreBadgeLabel') else "0"
                summary += f"Risk Score: {risk_score}\n"
                
                # Add alerts
                alerts = []
                try:
                    for i in range(self.ui.alertsListWidget.count()):
                        alerts.append(self.ui.alertsListWidget.item(i).text())
                except:
                    pass
                
                if alerts:
                    summary += f"Alerts: {'; '.join(alerts[:3])}...\n"  # First 3 alerts
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
            
            # Save analysis result
            result_id = self.db_manager.add_analysis_result(
                artifact_id=artifact_id,  # Link to artifact if available
                tool_used="Metadata Analysis",
                summary=summary,
                result_path=None
            )
            
            if result_id:
                # Log the activity
                self.db_manager.log_activity(
                    case_id=self.current_case_id,
                    action=f"METADATA_ANALYSIS: {file_name}",
                    tool_used="Metadata Analysis",
                    details=f"Analyzed metadata for {file_name}, Risk Score: {risk_score if 'risk_score' in locals() else '0'}"
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

        # File-system timestamps (store for internal use but don't display as they're not in new UI)
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

        # All tabs are always enabled in new UI - no conditional enabling needed

        # Collect metadata per type (prefer ExifTool if available)
        embedded_times = {"create": "-", "modify": "-", "original": "-"}
        author_text = "-"
        raw_dump_text = None

        used_exiftool = False
        if self.exiftool_path:
            try:
                author_text, embedded_times = self._populate_from_exiftool(file_path)
                # Raw: full exiftool textual dump
                raw_dump_text = self._run_exiftool_raw_text(file_path)
                used_exiftool = True
            except Exception:
                used_exiftool = False

        if not used_exiftool:
            try:
                if is_image:
                    meta, gps, embedded_times = self._extract_image_metadata(file_path)
                    author_text = self._compose_author_device(meta)
                    self._populate_metadata_tree(meta)
                    self._update_gps(gps)
                elif is_pdf:
                    props = self._extract_pdf_properties(file_path)
                    author_text = props.get("Author") or props.get("Creator") or "-"
                    self._populate_metadata_tree_from_dict(props, "PDF Properties")
                    self._update_gps(None)
                elif is_office:
                    props = self._extract_office_properties(file_path)
                    author_text = props.get("author") or props.get("last_modified_by") or "-"
                    self._populate_metadata_tree_from_dict(props, "Office Properties")
                    self._update_gps(None)
                elif is_exe:
                    pe_info = self._extract_pe_info(file_path)
                    author_text = pe_info.get("Signature", "-")
                    # Convert PE info to tree format
                    pe_tree_data = {k: v for k, v in pe_info.items() if k != "Imports"}
                    self._populate_metadata_tree_from_dict(pe_tree_data, "PE Header")
                    self._update_gps(None)
                else:
                    self._update_gps(None)
            except Exception as e:
                QMessageBox.warning(self, "Metadata", f"Lỗi phân tích: {str(e)}")

        # Author/device
        self.ui.authorDeviceValueLabel.setText(author_text if author_text else "-")

        # Update current file label
        self.ui.currentFileLabel.setText(f"Analyzing: {os.path.basename(file_path)}")

        # Investigator insights + Raw text
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
            # GPS handling is now done via embedded map
        except Exception:
            if raw_dump_text is not None:
                self.ui.rawTextEdit.setPlainText(raw_dump_text)
            else:
                if not self.ui.rawTextEdit.toPlainText():
                    self.ui.rawTextEdit.setPlainText("")

        # Hex and strings
        self._populate_hex_and_strings(file_path)

        
        # Save analysis results to database if case is selected
        if self.current_case_id:
            # Get artifact_id from the current selected item
            try:
                current_item = self.ui.evidenceListWidget.currentItem()
                if current_item:
                    artifact_data = current_item.data(Qt.UserRole)
                    artifact_id = artifact_data.get('id')
                    # Save metadata analysis results with the existing artifact ID
                    self.save_metadata_analysis_to_database(file_path, author_text, embedded_times, artifact_id)
            except Exception as e:
                print(f"Error saving metadata analysis: {e}")

    # ===== ExifTool integration =====
    def _find_exiftool(self) -> str:
        try:
            # 1) Environment override
            env_path = os.environ.get("EXIFTOOL_PATH")
            if env_path and os.path.exists(env_path):
                return env_path
            # 2) Look under Windows_forensic/tools/exiftool (two-level up)
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
            # 3) Fallback: DoAn/tools/exiftool (three-level up)
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
        # Default deep but silent config
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
        # Remove explicit tool name hints to keep engine transparent
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
        gps_lat = self._first_present(tags, ["GPS:GPSLatitude", "Composite:GPSLatitude"])  # numeric with -n
        gps_lon = self._first_present(tags, ["GPS:GPSLongitude", "Composite:GPSLongitude"])  # numeric with -n
        gps = None
        try:
            if gps_lat is not None and gps_lon is not None:
                lat = float(gps_lat)
                lon = float(gps_lon)
                gps = {"lat": lat, "lng": lon}
        except Exception:
            gps = None
        self._update_gps(gps)

        # Embedded times (prefer EXIF, else QuickTime, else XMP/PDF)
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
        # Embedded times are now handled within the metadata tree structure

        # Author/Device
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

        # Metadata tree grouped by families
        self._populate_metadata_tree_exiftool(tags)

        # Document props are now included in the main metadata tree

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
                # Skip some very noisy groups if desired
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
        """Populate metadata tree from a dictionary of properties"""
        try:
            tree = self.ui.metadataTreeWidget
            
            # Create or find the group node
            group_node = None
            for i in range(tree.topLevelItemCount()):
                item = tree.topLevelItem(i)
                if item.text(0) == group_name:
                    group_node = item
                    break
            
            if group_node is None:
                group_node = QTreeWidgetItem([group_name, "", ""])
                tree.addTopLevelItem(group_node)
            
            # Add properties to the group
            for key, value in data.items():
                if value not in (None, "", "-"):
                    child = QTreeWidgetItem(["", str(key), str(value)])
                    group_node.addChild(child)
            
            tree.expandAll()
        except Exception:
            pass
    
    def _populate_metadata_tree(self, meta: dict) -> None:
        """Populate metadata tree from image metadata"""
        try:
            tree = self.ui.metadataTreeWidget
            tree.clear()
            
            # Group metadata by categories
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

            # Add remaining metadata to "Others" group
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

    # ===== Investigator insights =====
    def _generate_investigator_insights(self, file_path: str, fs_created: str, embedded_original: str, author_text: str, tags: dict | None) -> str:
        hints = []
        score = 0

        # Hashes
        try:
            md5, sha1, sha256 = self._compute_hashes(file_path)
            hints.append(f"Hashes: MD5={md5} | SHA1={sha1} | SHA256={sha256}")
        except Exception:
            pass

        # Time discrepancy (already flagged visually)
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

        # Editing software indicator
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

        # Missing metadata in images (possible stripping)
        try:
            ext = os.path.splitext(file_path.lower())[1]
            if ext in (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp") and tags is not None:
                # Count EXIF groups
                exif_keys = [k for k in tags.keys() if k.startswith("EXIF:") or k.startswith("IFD0:")]
                if len(exif_keys) < 3:
                    score += 1
                    hints.append("Indicator: Very few EXIF tags detected (possible metadata stripping)")
        except Exception:
            pass

        # Author/Device context
        if author_text and author_text != "-":
            hints.append(f"Author/Device: {author_text}")

        # GPS context + map link
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

        # Risk analysis is simplified in new UI - just include in raw text

        # Summary score in text
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

    # ===== Build ExifTool flags from UI toggles =====
    def _build_exiftool_flags(self, base_flags: list) -> list:
        # Simplified: always deep and inclusive, no UI toggles
        return list(base_flags) + ["-a", "-u", "-U", "-ee3", "-api", "RequestAll=3"]

    # ===== UI helpers - simplified for new interface =====

    # ===== Reset UI =====
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

    # ===== Quick summary helpers =====
    def _populate_thumbnail(self, file_path: str) -> None:
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
        try:
            if gps and isinstance(gps, dict) and 'lat' in gps and 'lng' in gps:
                lat, lng = gps['lat'], gps['lng']
                # Update embedded map
                self._update_embedded_map(lat, lng)
                # Update location label
                self.ui.currentLocationLabel.setText(f"{lat:.6f}, {lng:.6f}")
                self.ui.currentLocationLabel.setStyleSheet("QLabel { color: #28a745; font-weight: bold; }")
                # GPS data available - enable refresh map functionality
            else:
                # No GPS data
                self.ui.currentLocationLabel.setText("No GPS data available")
                self.ui.currentLocationLabel.setStyleSheet("QLabel { color: #6c757d; font-style: italic; }")
                # Reset map to default
                self._reset_embedded_map()
        except Exception:
            pass

    # Discrepancy warning is no longer in new UI - handled in insights text

    # ===== Data extraction =====
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

        # Pillow fallback
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

    def _extract_office_properties(self, file_path: str) -> dict:
        props = {}
        try:
            from docx import Document  # type: ignore

            doc = Document(file_path)
            core = doc.core_properties
            props.update({
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
                "description": core.description,
                "company": getattr(core, "company", ""),
            })
        except Exception:
            pass
        return {k: v for k, v in props.items() if v not in (None, "")}

    def _extract_pe_info(self, file_path: str) -> dict:
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

    # ===== Populate widgets - removed old table methods, using tree now =====

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

    # ===== Search/filter =====
    def filter_metadata_tree(self, text: str) -> None:
        try:
            pattern = (text or "").strip().lower()
            tree = self.ui.metadataTreeWidget
            for i in range(tree.topLevelItemCount()):
                top = tree.topLevelItem(i)
                self._filter_tree_item(top, pattern)
        except Exception:
            pass

    def _filter_tree_item(self, item: QTreeWidgetItem, pattern: str) -> bool:
        if not pattern:
            item.setHidden(False)
            for i in range(item.childCount()):
                self._filter_tree_item(item.child(i), pattern)
            return True
        text = (item.text(0) + " " + item.text(1) + " " + item.text(2)).lower()
        matched = pattern in text
        child_match = False
        for i in range(item.childCount()):
            if self._filter_tree_item(item.child(i), pattern):
                child_match = True
        item.setHidden(not (matched or child_match))
        return matched or child_match

    # ===== Utilities =====
    def _new_table_item(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() ^ Qt.ItemIsEditable)
        return item

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

    # ===== Compare/pin =====

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

    # ===== Embedded Map Methods =====
    def _update_embedded_map(self, lat: float, lng: float) -> None:
        """Update embedded Google Maps to show GPS location"""
        try:
            # Create Google Maps URL with marker and better zoom
            maps_url = f"https://maps.google.com/maps?q={lat},{lng}&ll={lat},{lng}&z=16&t=h"
            self.ui.mapView.setUrl(QUrl(maps_url))
            print(f"Map updated with coordinates: {lat}, {lng}")
        except Exception as e:
            print(f"Error updating map: {e}")
            pass

    def _reset_embedded_map(self) -> None:
        """Reset embedded map to default view"""
        try:
            self.ui.mapView.setUrl(QUrl("https://maps.google.com"))
        except Exception:
            pass


    def refresh_map_location(self) -> None:
        """Refresh map with current GPS data"""
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


