from PyQt5.QtWidgets import QWidget, QFileDialog, QMessageBox, QTreeWidgetItem, QTableWidgetItem, QAbstractItemView, QListView, QTreeView
from PyQt5.QtCore import Qt, QLoggingCategory
from PyQt5.QtGui import QPixmap, QColor

import os
import mimetypes
import subprocess
import json
import shlex
from datetime import datetime

from views.pages.analysis_ui.metadata_analysis_ui import Ui_Form


class MetadataAnalysis(QWidget):
    """Single-page workbench for file/folder metadata analysis."""

    def __init__(self):
        super(MetadataAnalysis, self).__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        try:
            # Suppress noisy ICC profile warnings from Qt image loader
            QLoggingCategory.setFilterRules("qt.gui.icc=false")
        except Exception:
            pass

        # Wire interactions
        try:
            self.ui.searchExifLineEdit.textChanged.connect(self.filter_exif_tree)
        except Exception:
            pass

        try:
            self.ui.btnLoadSources.clicked.connect(self.handle_load_sources)
        except Exception:
            pass

        try:
            self.ui.sourcesTree.itemClicked.connect(self.on_source_item_clicked)
        except Exception:
            pass

        try:
            self.ui.btnPin.toggled.connect(self.on_pin_toggled)
        except Exception:
            pass

        # Toolbar actions
        try:
            self.ui.btnExportCSV.clicked.connect(self.export_csv)
        except Exception:
            pass
        try:
            self.ui.btnExportXML.clicked.connect(self.export_xml)
        except Exception:
            pass
        try:
            self.ui.btnExtractPreviews.clicked.connect(self.extract_previews)
        except Exception:
            pass
        try:
            # Export quick HTML report for investigator in Vietnamese
            self.ui.btnExportReport.clicked.connect(self.export_quick_report)
        except Exception:
            pass
        try:
            self.ui.btnCopyHashes.clicked.connect(self.copy_hashes_to_clipboard)
        except Exception:
            pass
        try:
            self.ui.btnOpenFileLocation.clicked.connect(self.open_file_location)
        except Exception:
            pass
        try:
            self.ui.btnOpenMap.clicked.connect(self.open_gps_in_maps)
        except Exception:
            pass
        # No custom args/run button in simplified UI

        # State
        self.current_file_path = None
        self.current_metadata_map = {}
        self.pinned_metadata_map = None
        self.pinned_file_path = None
        self.exiftool_path = self._find_exiftool()
        self._last_exiftool_tags = None

        # Disable Compare tab initially
        try:
            idx_compare = self.ui.tabWidget.indexOf(self.ui.tabCompare)
            if idx_compare != -1:
                self.ui.tabWidget.setTabEnabled(idx_compare, False)
        except Exception:
            pass

        # Splitter sizing
        try:
            self.ui.workbenchSplitter.setSizes([260, 520, 520])
        except Exception:
            pass

        self._clear_all()

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

        # File-system timestamps
        try:
            stat = os.stat(file_path)
            created = self._format_ts(stat.st_ctime)
            modified = self._format_ts(stat.st_mtime)
            accessed = self._format_ts(stat.st_atime)
            changed = modified  # Fallback; true MFT changed requires NTFS APIs
        except Exception:
            created = modified = accessed = changed = "Unknown"

        self.ui.fileCreateTimeValueLabel.setText(created)
        self.ui.fileModifyTimeValueLabel.setText(modified)
        self.ui.fileAccessTimeValueLabel.setText(accessed)
        self.ui.fileChangeTimeValueLabel.setText(changed)

        # Determine type
        ext = os.path.splitext(file_name.lower())[1]
        is_image = ext in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".gif", ".webp", ".heic"}
        is_pdf = ext == ".pdf"
        is_office = ext in {".docx", ".pptx", ".xlsx"}
        is_exe = ext in {".exe", ".dll", ".sys", ".msi"}

        # Tabs availability
        self._enable_tabs(exif_tab=is_image, doc_tab=(is_pdf or is_office), pe_tab=is_exe)

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
                    self._populate_exif_tree(meta)
                    self._update_gps(gps)
                elif is_pdf:
                    props = self._extract_pdf_properties(file_path)
                    author_text = props.get("Author") or props.get("Creator") or "-"
                    self._populate_document_table(props)
                    self._update_gps(None)
                elif is_office:
                    props = self._extract_office_properties(file_path)
                    author_text = props.get("author") or props.get("last_modified_by") or "-"
                    self._populate_document_table(props)
                    self._update_gps(None)
                elif is_exe:
                    pe_info = self._extract_pe_info(file_path)
                    author_text = pe_info.get("Signature", "-")
                    self._populate_pe_tables(pe_info)
                    self._update_gps(None)
                else:
                    self._update_gps(None)
            except Exception as e:
                QMessageBox.warning(self, "Metadata", f"Lỗi phân tích: {str(e)}")

        # Author/device
        self.ui.authorDeviceValueLabel.setText(author_text if author_text else "-")

        # Embedded timeline
        self.ui.embeddedCreateTimeValueLabel.setText(embedded_times.get("create", "-"))
        self.ui.embeddedModifyTimeValueLabel.setText(embedded_times.get("modify", "-"))
        self.ui.embeddedTimeValueLabel.setText(embedded_times.get("original", "-"))

        # Discrepancy warning
        self._update_discrepancy_warning(created, embedded_times.get("original", "-"))

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
            # Enable/disable Open Map helper based on GPS presence
            try:
                has_gps = False
                if self._last_exiftool_tags:
                    lat = self._last_exiftool_tags.get("GPS:GPSLatitude")
                    lon = self._last_exiftool_tags.get("GPS:GPSLongitude")
                    has_gps = isinstance(lat, (int, float)) and isinstance(lon, (int, float))
                self.ui.btnOpenMap.setEnabled(bool(has_gps))
            except Exception:
                pass
        except Exception:
            if raw_dump_text is not None:
                self.ui.rawTextEdit.setPlainText(raw_dump_text)
            else:
                if not self.ui.rawTextEdit.toPlainText():
                    self.ui.rawTextEdit.setPlainText("")

        # Hex and strings
        self._populate_hex_and_strings(file_path)

        # Compare
        try:
            self.current_metadata_map = self._build_current_metadata_map(file_path, author_text, embedded_times)
            if self.pinned_metadata_map is not None:
                self._update_compare_table()
        except Exception:
            pass

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
        self.ui.embeddedTimeValueLabel.setText(embedded_times["original"])
        self.ui.embeddedCreateTimeValueLabel.setText(embedded_times["create"])
        self.ui.embeddedModifyTimeValueLabel.setText(embedded_times["modify"])

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

        # EXIF tree grouped by families
        self._populate_exif_tree_exiftool(tags)

        # Document props
        doc_groups = ("PDF:", "XMP:", "XMP-", "DOC:", "DOCX:")
        doc_props = {k: v for k, v in tags.items() if any(k.startswith(g) for g in doc_groups)}
        if doc_props:
            items = []
            for k, v in doc_props.items():
                items.append((k, v))
            table = self.ui.documentPropsTable
            table.setRowCount(0)
            table.setRowCount(len(items))
            for row, (k, v) in enumerate(items):
                table.setItem(row, 0, self._new_table_item(str(k)))
                table.setItem(row, 1, self._new_table_item(str(v)))
            table.resizeColumnsToContents()

        return author_text, embedded_times

    def _populate_exif_tree_exiftool(self, tags: dict) -> None:
        try:
            tree = self.ui.exifTreeWidget
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
                    node = QTreeWidgetItem([group])
                    group_to_node[group] = node
                    tree.addTopLevelItem(node)
                else:
                    node = group_to_node[group]
                child = QTreeWidgetItem([tag, self._stringify_exiftool_value(v)])
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

        # Update insights panel (badge + list)
        try:
            # Badge color by score
            color = "#28a745"  # green
            if score >= 3:
                color = "#dc3545"  # red
            elif score == 2:
                color = "#ffc107"  # amber
            self.ui.riskScoreBadgeLabel.setText(str(score))
            self.ui.riskScoreBadgeLabel.setStyleSheet(
                f"QLabel {{ padding: 3px 10px; border-radius: 10px; color: white; background-color: {color}; font-weight: bold; }}"
            )
            # Fill alerts list
            try:
                self.ui.alertsListWidget.clear()
                for h in hints:
                    self.ui.alertsListWidget.addItem(h)
            except Exception:
                pass
        except Exception:
            pass

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

    # ===== Toolbar actions =====
    def export_csv(self) -> None:
        try:
            if not self.exiftool_path:
                QMessageBox.warning(self, "Xuất CSV", "Thiếu thành phần cần thiết để xuất")
                return
            if not self.current_file_path:
                QMessageBox.information(self, "Export CSV", "Vui lòng chọn tệp trước")
                return
            save_path, _ = QFileDialog.getSaveFileName(self, "Lưu CSV", os.path.splitext(self.current_file_path)[0] + ".csv", "CSV (*.csv)")
            if not save_path:
                return
            base = ["-G1", "-n", f"-csv={save_path}"]
            args = self._build_exiftool_flags(base)
            cmd = [self.exiftool_path] + args + [self.current_file_path]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip() or "Xuất CSV thất bại")
            QMessageBox.information(self, "Export CSV", f"Đã lưu:\n{save_path}")
        except Exception as e:
            QMessageBox.warning(self, "Export CSV", str(e))

    def export_xml(self) -> None:
        try:
            if not self.exiftool_path:
                QMessageBox.warning(self, "Xuất XML", "Thiếu thành phần cần thiết để xuất")
                return
            if not self.current_file_path:
                QMessageBox.information(self, "Export XML", "Vui lòng chọn tệp trước")
                return
            save_path, _ = QFileDialog.getSaveFileName(self, "Lưu XML", os.path.splitext(self.current_file_path)[0] + ".xml", "XML (*.xml)")
            if not save_path:
                return
            base = ["-X", "-struct", "-G1", "-n"]
            args = self._build_exiftool_flags(base)
            cmd = [self.exiftool_path] + args + [self.current_file_path]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip() or "Xuất XML thất bại")
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(proc.stdout)
            QMessageBox.information(self, "Export XML", f"Đã lưu:\n{save_path}")
        except Exception as e:
            QMessageBox.warning(self, "Export XML", str(e))

    def extract_previews(self) -> None:
        try:
            if not self.exiftool_path:
                QMessageBox.warning(self, "Trích xuất", "Thiếu thành phần cần thiết để trích xuất")
                return
            if not self.current_file_path:
                QMessageBox.information(self, "Extract Previews", "Vui lòng chọn tệp trước")
                return
            out_dir = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu previews")
            if not out_dir:
                return
            fmt = os.path.join(out_dir, "%f_%t%-c.%s")
            base = ["-b", "-W", fmt]
            args = self._build_exiftool_flags(base)
            tags = ["-PreviewImage", "-JpgFromRaw", "-ThumbnailImage", "-ICC_Profile"]
            cmd = [self.exiftool_path] + args + tags + [self.current_file_path]
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            if proc.returncode != 0:
                raise RuntimeError(proc.stderr.strip() or "Trích xuất thất bại")
            QMessageBox.information(self, "Trích xuất", f"Đã lưu vào:\n{out_dir}")
        except Exception as e:
            QMessageBox.warning(self, "Extract Previews", str(e))

    def export_quick_report(self) -> None:
        try:
            if not self.current_file_path:
                QMessageBox.information(self, "Xuất báo cáo", "Vui lòng chọn tệp trước")
                return
            save_path, _ = QFileDialog.getSaveFileName(
                self,
                "Lưu báo cáo",
                os.path.splitext(self.current_file_path)[0] + "_report.html",
                "HTML (*.html)"
            )
            if not save_path:
                return
            # Thu thập dữ liệu đang hiển thị
            fields = {
                "Tên tệp": os.path.basename(self.current_file_path),
                "Loại tệp": self.ui.fileTypeValueLabel.text(),
                "Kích thước": self.ui.fileSizeValueLabel.text(),
                "Tác giả/Thiết bị": self.ui.authorDeviceValueLabel.text(),
                "Embedded Original": self.ui.embeddedTimeValueLabel.text(),
                "Embedded Created": self.ui.embeddedCreateTimeValueLabel.text(),
                "Embedded Modified": self.ui.embeddedModifyTimeValueLabel.text(),
                "FS Created": self.ui.fileCreateTimeValueLabel.text(),
                "FS Modified": self.ui.fileModifyTimeValueLabel.text(),
                "FS Accessed": self.ui.fileAccessTimeValueLabel.text(),
                "FS Changed": self.ui.fileChangeTimeValueLabel.text(),
                "Điểm rủi ro": getattr(self.ui, 'riskScoreBadgeLabel', None).text() if getattr(self.ui, 'riskScoreBadgeLabel', None) else "-",
            }
            alerts = []
            try:
                for i in range(self.ui.alertsListWidget.count()):
                    alerts.append(self.ui.alertsListWidget.item(i).text())
            except Exception:
                pass
            # Tạo HTML đơn giản, tiếng Việt
            html = [
                "<html><head><meta charset='utf-8'><title>Báo cáo Metadata</title>",
                "<style>body{font-family:Arial,Helvetica,sans-serif;font-size:14px} table{border-collapse:collapse;width:100%} td,th{border:1px solid #ddd;padding:8px} th{background:#f5f5f5;text-align:left}</style>",
                "</head><body>",
                f"<h2>Báo cáo Metadata - {fields['Tên tệp']}</h2>",
                "<h3>Tóm tắt</h3>",
                "<table>",
            ]
            for k, v in fields.items():
                html.append(f"<tr><th>{k}</th><td>{v}</td></tr>")
            html.extend(["</table>", "<h3>Cảnh báo &amp; Gợi ý</h3>", "<ul>"])
            for a in alerts:
                html.append(f"<li>{a}</li>")
            html.extend(["</ul>", "<h3>Dữ liệu thô</h3>", "<pre>",
                         self.ui.rawTextEdit.toPlainText().replace("<", "&lt;").replace(">", "&gt;"),
                         "</pre>", "</body></html>"])
            with open(save_path, "w", encoding="utf-8") as f:
                f.write("\n".join(html))
            QMessageBox.information(self, "Xuất báo cáo", f"Đã lưu:\n{save_path}")
        except Exception as e:
            QMessageBox.warning(self, "Xuất báo cáo", str(e))

    # ===== Investigator helpers =====
    def copy_hashes_to_clipboard(self) -> None:
        try:
            if not self.current_file_path:
                QMessageBox.information(self, "Sao chép băm", "Vui lòng chọn tệp trước")
                return
            md5, sha1, sha256 = self._compute_hashes(self.current_file_path)
            text = f"MD5: {md5}\nSHA1: {sha1}\nSHA256: {sha256}"
            from PyQt5.QtWidgets import QApplication
            QApplication.clipboard().setText(text)
            QMessageBox.information(self, "Sao chép băm", "Đã sao chép vào clipboard")
        except Exception as e:
            QMessageBox.warning(self, "Sao chép băm", str(e))

    def open_file_location(self) -> None:
        try:
            if not self.current_file_path:
                QMessageBox.information(self, "Mở thư mục tệp", "Vui lòng chọn tệp trước")
                return
            path = os.path.abspath(self.current_file_path)
            folder = os.path.dirname(path)
            # Open Explorer and select file if possible
            try:
                subprocess.run(["explorer", "/select,", path])
            except Exception:
                os.startfile(folder)
        except Exception as e:
            QMessageBox.warning(self, "Mở thư mục tệp", str(e))

    def open_gps_in_maps(self) -> None:
        try:
            if not self._last_exiftool_tags:
                return
            lat = self._last_exiftool_tags.get("GPS:GPSLatitude")
            lon = self._last_exiftool_tags.get("GPS:GPSLongitude")
            if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
                url = f"https://maps.google.com/?q={lat},{lon}"
                os.startfile(url)
        except Exception:
            pass

    # No run_custom_args in simplified UI

    def open_file_dialog_and_analyze(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, "Chọn tệp cần phân tích", "", "All Files (*.*)")
        if file_path:
            self.analyze_file(file_path)

    # ===== UI helpers =====
    def _enable_tabs(self, exif_tab: bool, doc_tab: bool, pe_tab: bool) -> None:
        try:
            idx_key = self.ui.tabWidget.indexOf(self.ui.tabKeyProperties)
            idx_exif = self.ui.tabWidget.indexOf(self.ui.tabAllExif)
            idx_doc = self.ui.tabWidget.indexOf(self.ui.tabDocumentProps)
            idx_pe = self.ui.tabWidget.indexOf(self.ui.tabPEHeader)
            idx_raw = self.ui.tabWidget.indexOf(self.ui.tabRawData)
            if idx_key != -1:
                self.ui.tabWidget.setTabEnabled(idx_key, True)
            if idx_raw != -1:
                self.ui.tabWidget.setTabEnabled(idx_raw, True)
            if idx_exif != -1:
                self.ui.tabWidget.setTabEnabled(idx_exif, exif_tab)
            if idx_doc != -1:
                self.ui.tabWidget.setTabEnabled(idx_doc, doc_tab)
            if idx_pe != -1:
                self.ui.tabWidget.setTabEnabled(idx_pe, pe_tab)
        except Exception:
            pass

    # ===== Sources loading (left panel) =====
    def handle_load_sources(self) -> None:
        """Open a single dialog that allows selecting files and/or folders together."""
        paths = self._select_files_and_folders()
        if not paths:
            return

        # Reset tree, then add all selected sources
        try:
            tree = self.ui.sourcesTree
            tree.clear()
        except Exception:
            pass

        first_file_for_analysis = None
        for p in paths:
            try:
                if os.path.isdir(p):
                    self._add_folder_to_tree(p)
                elif os.path.isfile(p):
                    self._add_file_to_tree(p)
                    if first_file_for_analysis is None:
                        first_file_for_analysis = p
            except Exception:
                continue

        if first_file_for_analysis:
            self.analyze_file(first_file_for_analysis)

    def _select_files_and_folders(self) -> list:
        """Return a list of selected file and folder paths using a non-native dialog.

        Note: Using DontUseNativeDialog to allow multi-select of both files and directories.
        """
        try:
            dialog = QFileDialog(self, "Chọn nguồn (có thể chọn nhiều tệp và thư mục)")
            dialog.setOption(QFileDialog.DontUseNativeDialog, True)
            dialog.setOption(QFileDialog.ShowDirsOnly, False)
            dialog.setFileMode(QFileDialog.ExistingFiles)
            dialog.setNameFilter("All Files (*.*)")

            # Ensure multiple selection in internal views
            try:
                for view in dialog.findChildren(QListView) + dialog.findChildren(QTreeView):
                    view.setSelectionMode(QAbstractItemView.ExtendedSelection)
            except Exception:
                pass

            if dialog.exec_() == QFileDialog.Accepted:
                return dialog.selectedFiles() or []
        except Exception:
            pass
        return []

    def _add_file_to_tree(self, file_path: str) -> None:
        """Add a single file as a top-level item without clearing the tree."""
        try:
            tree = self.ui.sourcesTree
            item = QTreeWidgetItem([os.path.basename(file_path)])
            item.setData(0, Qt.UserRole, {"path": file_path, "is_file": True})
            item.setToolTip(0, file_path)
            tree.addTopLevelItem(item)
            tree.setCurrentItem(item)
        except Exception:
            pass

    def _add_folder_to_tree(self, folder_path: str) -> None:
        """Add a folder and populate its descendants without clearing the tree."""
        try:
            tree = self.ui.sourcesTree
            root = QTreeWidgetItem([os.path.basename(folder_path.rstrip(os.sep)) or folder_path])
            root.setData(0, Qt.UserRole, {"path": folder_path, "is_file": False})
            tree.addTopLevelItem(root)
            self._populate_folder_tree(root, folder_path, depth=0, max_depth=10, max_entries=2000)
            root.setExpanded(True)
        except Exception:
            pass

    def load_sources_file(self, file_path: str) -> None:
        try:
            tree = self.ui.sourcesTree
            tree.clear()
            item = QTreeWidgetItem([os.path.basename(file_path)])
            item.setData(0, Qt.UserRole, {"path": file_path, "is_file": True})
            item.setToolTip(0, file_path)
            tree.addTopLevelItem(item)
            tree.setCurrentItem(item)
            self.analyze_file(file_path)
        except Exception:
            pass

    def load_sources_folder(self, folder_path: str) -> None:
        try:
            tree = self.ui.sourcesTree
            tree.clear()
            root = QTreeWidgetItem([os.path.basename(folder_path.rstrip(os.sep)) or folder_path])
            root.setData(0, Qt.UserRole, {"path": folder_path, "is_file": False})
            tree.addTopLevelItem(root)
            self._populate_folder_tree(root, folder_path, depth=0, max_depth=10, max_entries=2000)
            root.setExpanded(True)
        except Exception:
            pass

    def _populate_folder_tree(self, parent_item: QTreeWidgetItem, dir_path: str, depth: int, max_depth: int, max_entries: int, counter: list = None) -> None:
        try:
            if counter is None:
                counter = [0]
            if depth > max_depth or counter[0] > max_entries:
                return
            try:
                entries = sorted(os.listdir(dir_path))
            except Exception:
                return
            for name in entries:
                if counter[0] > max_entries:
                    break
                path = os.path.join(dir_path, name)
                if os.path.isdir(path):
                    dir_item = QTreeWidgetItem([name])
                    dir_item.setData(0, Qt.UserRole, {"path": path, "is_file": False})
                    parent_item.addChild(dir_item)
                    counter[0] += 1
                    self._populate_folder_tree(dir_item, path, depth + 1, max_depth, max_entries, counter)
                else:
                    file_item = QTreeWidgetItem([name])
                    file_item.setData(0, Qt.UserRole, {"path": path, "is_file": True})
                    file_item.setToolTip(0, path)
                    parent_item.addChild(file_item)
                    counter[0] += 1
        except Exception:
            pass

    def on_source_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        try:
            data = item.data(0, Qt.UserRole) or {}
            if data.get("is_file") and data.get("path"):
                self.analyze_file(data.get("path"))
        except Exception:
            pass

    # ===== Reset UI =====
    def _clear_all(self) -> None:
        try:
            self.ui.thumbnailLabel.setPixmap(QPixmap())
            self.ui.thumbnailLabel.setText("Thumbnail / Biểu tượng")
            self.ui.fileNameValueLabel.setText("-")
            self.ui.fileTypeValueLabel.setText("-")
            self.ui.fileSizeValueLabel.setText("-")
            self.ui.authorDeviceValueLabel.setText("-")
            # Location UI removed in .ui; ignore gracefully
            self.ui.embeddedTimeValueLabel.setText("-")
            self.ui.fileCreateTimeValueLabel.setText("-")
            self.ui.fileModifyTimeValueLabel.setText("-")
            self.ui.fileAccessTimeValueLabel.setText("-")
            self.ui.fileChangeTimeValueLabel.setText("-")
            self.ui.embeddedCreateTimeValueLabel.setText("-")
            self.ui.embeddedModifyTimeValueLabel.setText("-")
            self.ui.discrepancyWarningLabel.setVisible(False)
            # Hide the large empty timeline canvas to save space
            try:
                # Collapse unused timeline canvas
                self.ui.timelineView.setVisible(False)
                self.ui.timelineView.setMinimumHeight(0)
                self.ui.timelineView.setMaximumHeight(0)
            except Exception:
                pass
            try:
                self.ui.exifTreeWidget.clear()
            except Exception:
                pass
            try:
                self.ui.documentPropsTable.setRowCount(0)
            except Exception:
                pass
            try:
                self.ui.peHeaderTable.setRowCount(0)
                self.ui.peImportsTree.clear()
            except Exception:
                pass
            try:
                self.ui.rawTextEdit.clear()
                self.ui.hexTextEdit.clear()
                self.ui.stringsTextEdit.clear()
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
                self.ui.thumbnailLabel.setText("Thumbnail / Biểu tượng")
        except Exception:
            self.ui.thumbnailLabel.setText("Thumbnail / Biểu tượng")

    def _update_gps(self, gps: dict) -> None:
        try:
            # Location section removed; just no-op
            return
        except Exception:
            pass

    def _update_discrepancy_warning(self, fs_created: str, embedded_original: str) -> None:
        try:
            if not fs_created or not embedded_original:
                self.ui.discrepancyWarningLabel.setVisible(False)
                return

            def parse(dt_str: str):
                try:
                    return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    return None

            t_fs = parse(fs_created)
            t_emb = parse(embedded_original)
            if t_fs and t_emb:
                delta = (t_fs - t_emb).total_seconds()
                self.ui.discrepancyWarningLabel.setVisible(abs(delta) > 86400)
            else:
                self.ui.discrepancyWarningLabel.setVisible(False)
        except Exception:
            self.ui.discrepancyWarningLabel.setVisible(False)

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

    # ===== Populate widgets =====
    def _populate_exif_tree(self, meta: dict) -> None:
        try:
            self.ui.exifTreeWidget.clear()
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
            group_nodes = {name: QTreeWidgetItem([name]) for name in groups.keys()}
            for node in group_nodes.values():
                self.ui.exifTreeWidget.addTopLevelItem(node)

            added_keys = set()
            for group_name, keys in groups.items():
                group_item = group_nodes[group_name]
                for key in keys:
                    if key in meta:
                        value = str(meta.get(key, ""))
                        group_item.addChild(QTreeWidgetItem([key, value]))
                        added_keys.add(key)

            others = QTreeWidgetItem(["Others"])
            for k, v in meta.items():
                if k not in added_keys:
                    others.addChild(QTreeWidgetItem([k, str(v)]))
            if others.childCount() > 0:
                self.ui.exifTreeWidget.addTopLevelItem(others)

            self.ui.exifTreeWidget.expandAll()
        except Exception:
            pass

    def _populate_document_table(self, props: dict) -> None:
        try:
            table = self.ui.documentPropsTable
            table.setRowCount(0)
            items = list(props.items())
            table.setRowCount(len(items))
            for row, (k, v) in enumerate(items):
                table.setItem(row, 0, self._new_table_item(str(k)))
                table.setItem(row, 1, self._new_table_item(str(v)))
            table.resizeColumnsToContents()
        except Exception:
            pass

    def _populate_pe_tables(self, pe_info: dict) -> None:
        try:
            table = self.ui.peHeaderTable
            table.setRowCount(0)
            header_pairs = [(k, v) for k, v in pe_info.items() if k != "Imports"]
            table.setRowCount(len(header_pairs))
            for row, (k, v) in enumerate(header_pairs):
                table.setItem(row, 0, self._new_table_item(str(k)))
                table.setItem(row, 1, self._new_table_item(str(v)))
            table.resizeColumnsToContents()

            self.ui.peImportsTree.clear()
            dll_to_funcs = {}
            for dll, func in pe_info.get("Imports", []):
                dll_to_funcs.setdefault(dll, []).append(func)
            for dll, funcs in dll_to_funcs.items():
                parent = QTreeWidgetItem([dll, str(len(funcs))])
                for f in funcs:
                    parent.addChild(QTreeWidgetItem(["", f]))
                self.ui.peImportsTree.addTopLevelItem(parent)
            self.ui.peImportsTree.expandAll()
        except Exception:
            pass

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
    def filter_exif_tree(self, text: str) -> None:
        try:
            pattern = (text or "").strip().lower()
            tree = self.ui.exifTreeWidget
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
        text = (item.text(0) + " " + item.text(1)).lower()
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
    def on_pin_toggled(self, checked: bool) -> None:
        try:
            if checked:
                self.pinned_metadata_map = dict(self.current_metadata_map) if self.current_metadata_map else None
                self.pinned_file_path = self.current_file_path
            else:
                self.pinned_metadata_map = None
                self.pinned_file_path = None
            self._update_compare_table()
        except Exception:
            pass

    def _build_current_metadata_map(self, file_path: str, author_text: str, embedded_times: dict) -> dict:
        return {
            "File Name": os.path.basename(file_path) if file_path else "",
            "File Type": self.ui.fileTypeValueLabel.text(),
            "File Size": self.ui.fileSizeValueLabel.text(),
            "Author/Device": author_text or "-",
            "FS Created": self.ui.fileCreateTimeValueLabel.text(),
            "FS Modified": self.ui.fileModifyTimeValueLabel.text(),
            "FS Accessed": self.ui.fileAccessTimeValueLabel.text(),
            "FS Changed": self.ui.fileChangeTimeValueLabel.text(),
            "Embedded Original": embedded_times.get("original", "-"),
            "Embedded Created": embedded_times.get("create", "-"),
            "Embedded Modified": embedded_times.get("modify", "-"),
        }

    def _update_compare_table(self) -> None:
        try:
            idx_compare = self.ui.tabWidget.indexOf(self.ui.tabCompare)
            if idx_compare == -1:
                return
            has_pin = self.pinned_metadata_map is not None
            self.ui.tabWidget.setTabEnabled(idx_compare, has_pin)
            if not has_pin:
                return

            table = self.ui.compareTable
            table.setRowCount(0)
            keys = set(self.pinned_metadata_map.keys()) | set(self.current_metadata_map.keys())
            keys = sorted(keys)
            table.setRowCount(len(keys))
            for row, key in enumerate(keys):
                pinned_val = self.pinned_metadata_map.get(key, "")
                current_val = self.current_metadata_map.get(key, "")
                table.setItem(row, 0, self._new_table_item(key))
                item_pin = self._new_table_item(str(pinned_val))
                item_cur = self._new_table_item(str(current_val))
                table.setItem(row, 1, item_pin)
                table.setItem(row, 2, item_cur)
                if str(pinned_val) != str(current_val):
                    diff_color = QColor(255, 240, 200)
                    item_pin.setBackground(diff_color)
                    item_cur.setBackground(diff_color)
            table.resizeColumnsToContents()
        except Exception:
            pass

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


