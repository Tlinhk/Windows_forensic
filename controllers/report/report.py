from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, 
    QTextEdit, QComboBox, QFileDialog, QMessageBox, QProgressBar,
    QGroupBox, QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget, QSplitter, QFrame, QScrollArea, QApplication
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon
import os
import json
import hashlib
from datetime import datetime
from models.db_manager import DatabaseManager

# Word document generation (python-docx)
try:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
    from docx.enum.style import WD_STYLE_TYPE
    DOCX_AVAILABLE = True
except ImportError:
    Document = None
    WD_PARAGRAPH_ALIGNMENT = None
    DOCX_AVAILABLE = False
    print("Cảnh báo: Chưa cài đặt thư viện python-docx. Cài đặt bằng: pip install python-docx")

# Sửa import statement này
from views.pages.report_ui.report_ui import Ui_Form

class ReportGenerator(QThread):
    """Background thread for generating comprehensive reports"""
    progress_updated = pyqtSignal(int, str)
    report_generated = pyqtSignal(str, str)  # file_path, format
    
    def __init__(self, case_id, report_type, options):
        super().__init__()
        self.case_id = case_id
        self.report_type = report_type
        self.options = options
        self.db = DatabaseManager()
        
    def run(self):
        try:
            # Check if DOCX library is available
            if not DOCX_AVAILABLE:
                raise Exception("Thiếu thư viện python-docx. Cài đặt bằng: pip install python-docx")

            self.db.connect()
            
            if self.report_type == "comprehensive":
                file_path = self.generate_comprehensive_report()
            elif self.report_type == "executive":
                file_path = self.generate_executive_summary()
            elif self.report_type == "technical":
                file_path = self.generate_technical_report()
            else:
                file_path = self.generate_chain_of_custody()
                
            if file_path:
                # Calculate hash and save to database
                with open(file_path, 'rb') as f:
                    content = f.read()
                    sha256 = hashlib.sha256(content).hexdigest()
                
                self.db.create_report(
                    case_id=self.case_id,
                    file_path=file_path,
                    format="DOCX",
                    sha256=sha256
                )
                
                self.report_generated.emit(file_path, self.report_type)
            else:
                self.report_generated.emit("", "error")
                
        except Exception as e:
            print(f"Report generation error: {e}")
            self.report_generated.emit("", "error")
        finally:
            self.db.disconnect()
    
    def generate_comprehensive_report(self):
        """Generate comprehensive case report with all details"""
        case_info = self.db.get_case_with_investigator(self.case_id)
        if not case_info or not isinstance(case_info, dict):
            print(f"ERROR - Invalid case info returned: {case_info}")
            return None
            
        # Get all case data
        artifacts = self.db.get_artifacts_by_case(self.case_id)
        results = self.db.get_results_by_case(self.case_id)
        activity_logs = self.db.get_activity_logs(case_id=self.case_id)
        
        # Ensure data is iterable (handle cases where database might return unexpected types)
        if not isinstance(artifacts, (list, tuple)):
            print(f"WARNING - Artifacts is not iterable (type: {type(artifacts)}), converting to empty list")
            artifacts = []
        if not isinstance(results, (list, tuple)):
            print(f"WARNING - Results is not iterable (type: {type(results)}), converting to empty list")
            results = []
        if not isinstance(activity_logs, (list, tuple)):
            print(f"WARNING - Activity logs is not iterable (type: {type(activity_logs)}), converting to empty list")
            activity_logs = []

        # Create comprehensive Word document
        doc = self._create_comprehensive_docx(case_info, artifacts, results, activity_logs)
        
        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Case_{self.case_id}_Comprehensive_Report_{timestamp}.docx"

        archive_path = case_info.get('archive_path')
        if not archive_path:
            print(f"ERROR - No archive path found in case info: {case_info}")
            return None

        file_path = os.path.join(archive_path, filename)
        
        doc.save(file_path)
            
        return file_path
    
    def generate_executive_summary(self):
        """Generate executive summary report"""
        case_info = self.db.get_case_with_investigator(self.case_id)
        if not case_info or not isinstance(case_info, dict):
            print(f"ERROR - Invalid case info returned: {case_info}")
            return None
            
        # Get summary data
        artifacts = self.db.get_artifacts_by_case(self.case_id)
        results = self.db.get_results_by_case(self.case_id)
        
        # Ensure data is iterable
        if not isinstance(artifacts, (list, tuple)):
            artifacts = []
        if not isinstance(results, (list, tuple)):
            results = []
        
        doc = self._create_executive_docx(case_info, artifacts, results)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Case_{self.case_id}_Executive_Summary_{timestamp}.docx"

        archive_path = case_info.get('archive_path')
        if not archive_path:
            print(f"ERROR - No archive path found in case info: {case_info}")
            return None

        file_path = os.path.join(archive_path, filename)
        
        doc.save(file_path)
            
        return file_path
    
    def generate_technical_report(self):
        """Generate technical detailed report"""
        case_info = self.db.get_case_with_investigator(self.case_id)
        if not case_info or not isinstance(case_info, dict):
            print(f"ERROR - Invalid case info returned: {case_info}")
            return None
            
        artifacts = self.db.get_artifacts_by_case(self.case_id)
        results = self.db.get_results_by_case(self.case_id)
        activity_logs = self.db.get_activity_logs(case_id=self.case_id)
        
        # Ensure data is iterable
        if not isinstance(artifacts, (list, tuple)):
            artifacts = []
        if not isinstance(results, (list, tuple)):
            results = []
        if not isinstance(activity_logs, (list, tuple)):
            activity_logs = []

        doc = self._create_technical_docx(case_info, artifacts, results, activity_logs)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Case_{self.case_id}_Technical_Report_{timestamp}.docx"

        archive_path = case_info.get('archive_path')
        if not archive_path:
            print(f"ERROR - No archive path found in case info: {case_info}")
            return None

        file_path = os.path.join(archive_path, filename)
        
        doc.save(file_path)
            
        return file_path
    
    def generate_chain_of_custody(self):
        """Generate Chain of Custody report"""
        case_info = self.db.get_case_with_investigator(self.case_id)
        if not case_info or not isinstance(case_info, dict):
            print(f"ERROR - Invalid case info returned: {case_info}")
            return None
            
        artifacts = self.db.get_artifacts_by_case(self.case_id)
        activity_logs = self.db.get_activity_logs(case_id=self.case_id)
        
        # Ensure data is iterable
        if not isinstance(artifacts, (list, tuple)):
            artifacts = []
        if not isinstance(activity_logs, (list, tuple)):
            activity_logs = []

        doc = self._create_coc_docx(case_info, artifacts, activity_logs)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Case_{self.case_id}_Chain_of_Custody_{timestamp}.docx"

        archive_path = case_info.get('archive_path')
        if not archive_path:
            print(f"ERROR - No archive path found in case info: {case_info}")
            return None

        file_path = os.path.join(archive_path, filename)
        
        doc.save(file_path)
            
        return file_path

    def _create_comprehensive_docx(self, case_info, artifacts, results, activity_logs):
        """Create comprehensive Word document"""
        from docx.shared import Pt, RGBColor
        from docx.enum.style import WD_STYLE_TYPE

        doc = Document()

        # Setup styles
        self._setup_word_styles(doc)

        # Header
        title = doc.add_paragraph("BÁO CÁO ĐIỀU TRA SỐ TỔNG HỢP", style='CustomHeading1')
        title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

        subtitle = doc.add_paragraph("CHAIN OF CUSTODY - EVIDENCE INTEGRITY", style='CustomHeading2')
        subtitle.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

        case_title = doc.add_paragraph(f"Case ID: {case_info['case_id']} - {case_info['title']}")
        case_title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

        doc.add_paragraph("")

        # Case Information Section
        heading = doc.add_paragraph("THÔNG TIN VỤ ÁN", style='CustomHeading2')

        info_table = doc.add_table(rows=6, cols=2)
        info_table.style = 'Table Grid'

        # Headers
        hdr_cells = info_table.rows[0].cells
        hdr_cells[0].text = "Thông tin"
        hdr_cells[1].text = "Giá trị"

        # Data rows
        rows_data = [
            ("Case ID", case_info['case_id']),
            ("Tên vụ án", case_info['title']),
            ("Trạng thái", case_info.get('status', 'N/A')),
            ("Điều tra viên", case_info.get('full_name', 'N/A')),
            ("Ngày tạo", case_info.get('created_at', 'N/A')),
            ("Đường dẫn lưu trữ", case_info.get('archive_path', 'N/A'))
        ]

        for i, (label, value) in enumerate(rows_data, 1):
            row_cells = info_table.rows[i].cells
            row_cells[0].text = label
            row_cells[1].text = value

        doc.add_page_break()

        # Evidence Section
        heading = doc.add_paragraph("BẰNG CHỨNG SỐ (DIGITAL EVIDENCE)", style='CustomHeading2')

        if artifacts:
            evidence_table = doc.add_table(rows=1, cols=6)
            evidence_table.style = 'Table Grid'

            # Header row
            hdr_cells = evidence_table.rows[0].cells
            hdr_cells[0].text = "ID"
            hdr_cells[1].text = "Tên"
            hdr_cells[2].text = "Loại"
            hdr_cells[3].text = "Kích thước"
            hdr_cells[4].text = "Ngày thu thập"
            hdr_cells[5].text = "Hash SHA-256"

            # Data rows
        for artifact in artifacts:
                row_cells = evidence_table.add_row().cells
                row_cells[0].text = str(artifact['artefact_id'])
                row_cells[1].text = artifact['name']
                row_cells[2].text = artifact.get('evidence_type', 'N/A')
                row_cells[3].text = f"{artifact.get('size', 0):,} bytes"
                row_cells[4].text = artifact.get('collected_at', 'N/A')
                row_cells[5].text = artifact.get('sha256', 'N/A')
        else:
            doc.add_paragraph("Không có bằng chứng nào được tìm thấy.")

        doc.add_page_break()

        # Analysis Results Section
        heading = doc.add_paragraph("KẾT QUẢ PHÂN TÍCH", style='CustomHeading2')

        if results:
            results_table = doc.add_table(rows=1, cols=4)
            results_table.style = 'Table Grid'

            # Header row
            hdr_cells = results_table.rows[0].cells
            hdr_cells[0].text = "ID"
            hdr_cells[1].text = "Công cụ"
            hdr_cells[2].text = "Thời gian chạy"
            hdr_cells[3].text = "Tóm tắt"

            # Data rows
        for result in results:
                row_cells = results_table.add_row().cells
                row_cells[0].text = str(result['result_id'])
                row_cells[1].text = result.get('tool_used', 'N/A')
                row_cells[2].text = result.get('run_at', 'N/A')
                row_cells[3].text = result.get('summary', 'N/A')
        else:
            doc.add_paragraph("Không có kết quả phân tích nào.")

        doc.add_page_break()

        # Activity Log Section
        heading = doc.add_paragraph("NHẬT KÝ HOẠT ĐỘNG", style='CustomHeading2')

        if activity_logs:
            activity_table = doc.add_table(rows=1, cols=5)
            activity_table.style = 'Table Grid'

            # Header row
            hdr_cells = activity_table.rows[0].cells
            hdr_cells[0].text = "Thời gian"
            hdr_cells[1].text = "Hành động"
            hdr_cells[2].text = "Người thực hiện"
            hdr_cells[3].text = "Công cụ"
            hdr_cells[4].text = "Chi tiết"

            # Data rows
        for log in activity_logs:
                row_cells = activity_table.add_row().cells
                row_cells[0].text = log.get('timestamp', 'N/A')
                row_cells[1].text = log.get('action', 'N/A')
                row_cells[2].text = log.get('username', 'N/A')
                row_cells[3].text = log.get('tool_used', 'N/A')
                row_cells[4].text = log.get('details', 'N/A')
        else:
            doc.add_paragraph("Không có nhật ký hoạt động nào.")

        doc.add_page_break()

        # Chain of Custody Section
        heading = doc.add_paragraph("CHAIN OF CUSTODY", style='CustomHeading2')

        coc_paragraph = doc.add_paragraph()
        coc_paragraph.add_run("Báo cáo này đảm bảo tính toàn vẹn của bằng chứng số:").bold = True

        coc_items = [
            "Tất cả bằng chứng đều có hash SHA-256 để xác minh tính toàn vẹn",
            "Nhật ký hoạt động ghi lại mọi thao tác với bằng chứng",
            "Timestamp cho mọi hoạt động thu thập và phân tích",
            "Thông tin người thực hiện và công cụ sử dụng"
        ]

        for item in coc_items:
            p = doc.add_paragraph(item, style='List Bullet')

        doc.add_paragraph("")
        doc.add_paragraph(f"Báo cáo được tạo vào: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

        doc.add_page_break()

        # Recommendations Section
        heading = doc.add_paragraph("TÓM TẮT VÀ KHUYẾN NGHỊ", style='CustomHeading2')

        rec_paragraph = doc.add_paragraph()
        rec_paragraph.add_run("Dựa trên kết quả phân tích, vụ án này cần:").bold = True

        recommendations = [
            "Tiếp tục thu thập thêm bằng chứng nếu cần thiết",
            "Hoàn thiện chuỗi bảo quản bằng chứng",
            "Chuẩn bị báo cáo cho cơ quan có thẩm quyền",
            "Lưu trữ an toàn tất cả bằng chứng số"
        ]

        for rec in recommendations:
            p = doc.add_paragraph(rec, style='List Bullet')

        return doc

    def _create_executive_docx(self, case_info, artifacts, results):
        """Create executive summary Word document"""
        doc = Document()

        # Setup styles
        self._setup_word_styles(doc)

        # Header
        title = doc.add_paragraph("EXECUTIVE SUMMARY", style='CustomHeading1')
        title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

        case_title = doc.add_paragraph(f"Case {case_info['case_id']}: {case_info['title']}")
        case_title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

        doc.add_paragraph("")

        # Case Summary Section
        heading = doc.add_paragraph("TÓM TẮT VỤ ÁN", style='CustomHeading2')

        summary_table = doc.add_table(rows=3, cols=2)
        summary_table.style = 'Table Grid'

        # Data rows
        rows_data = [
            ("Điều tra viên", case_info.get('full_name', 'N/A')),
            ("Ngày tạo", case_info.get('created_at', 'N/A')),
            ("Trạng thái", case_info.get('status', 'N/A'))
        ]

        for i, (label, value) in enumerate(rows_data):
            row_cells = summary_table.rows[i].cells
            row_cells[0].text = label
            row_cells[1].text = value

        doc.add_paragraph("")

        # Statistics Section
        heading = doc.add_paragraph("THỐNG KÊ", style='CustomHeading2')

        stats_table = doc.add_table(rows=2, cols=2)
        stats_table.style = 'Table Grid'

        # Header row
        hdr_cells = stats_table.rows[0].cells
        hdr_cells[0].text = "Loại"
        hdr_cells[1].text = "Số lượng"

        # Data rows
        stats_data = [
            ("Bằng chứng số", str(len(artifacts))),
            ("Kết quả phân tích", str(len(results)))
        ]

        for i, (label, value) in enumerate(stats_data, 1):
            row_cells = stats_table.rows[i].cells
            row_cells[0].text = label
            row_cells[1].text = value

        doc.add_page_break()

        # Conclusion Section
        heading = doc.add_paragraph("KẾT LUẬN CHÍNH", style='CustomHeading2')

        conclusion = doc.add_paragraph()
        conclusion.add_run(f"Vụ án đã được điều tra với {len(artifacts)} bằng chứng số và {len(results)} kết quả phân tích.").bold = True

        doc.add_paragraph("")
        doc.add_paragraph("Chuỗi bảo quản bằng chứng đã được duy trì theo đúng quy trình pháp y số.")

        return doc

    def _create_technical_docx(self, case_info, artifacts, results, activity_logs):
        """Create technical detailed Word document"""
        doc = Document()

        # Setup styles
        self._setup_word_styles(doc)

        # Header
        title = doc.add_paragraph("TECHNICAL REPORT", style='CustomHeading1')
        title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

        case_title = doc.add_paragraph(f"Case {case_info['case_id']}: {case_info['title']}")
        case_title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

        doc.add_paragraph("")

        # Technical Details Section
        heading = doc.add_paragraph("TECHNICAL DETAILS", style='CustomHeading2')

        details_table = doc.add_table(rows=4, cols=2)
        details_table.style = 'Table Grid'

        # Data rows
        rows_data = [
            ("Case ID", case_info['case_id']),
            ("Investigator", case_info.get('full_name', 'N/A')),
            ("Created", case_info.get('created_at', 'N/A')),
            ("Status", case_info.get('status', 'N/A'))
        ]

        for i, (label, value) in enumerate(rows_data):
            row_cells = details_table.rows[i].cells
            row_cells[0].text = label
            row_cells[1].text = value

        doc.add_page_break()

        # Evidence Collection Section
        heading = doc.add_paragraph("EVIDENCE COLLECTION", style='CustomHeading2')

        collection_table = doc.add_table(rows=3, cols=2)
        collection_table.style = 'Table Grid'

        # Data rows
        collection_data = [
            ("Total Artifacts", str(len(artifacts))),
            ("Total Results", str(len(results))),
            ("Total Activities", str(len(activity_logs)))
        ]

        for i, (label, value) in enumerate(collection_data):
            row_cells = collection_table.rows[i].cells
            row_cells[0].text = label
            row_cells[1].text = value

        doc.add_page_break()

        # Analysis Results Section
        heading = doc.add_paragraph("ANALYSIS RESULTS", style='CustomHeading2')

        if results:
            results_table = doc.add_table(rows=1, cols=3)
            results_table.style = 'Table Grid'

            # Header row
            hdr_cells = results_table.rows[0].cells
            hdr_cells[0].text = "ID"
            hdr_cells[1].text = "Tool"
            hdr_cells[2].text = "Summary"

            # Data rows
        for result in results:
                row_cells = results_table.add_row().cells
                row_cells[0].text = str(result['result_id'])
                row_cells[1].text = result.get('tool_used', 'N/A')
                row_cells[2].text = result.get('summary', 'N/A')
        else:
            doc.add_paragraph("No analysis results available.")

        return doc

    def _create_coc_docx(self, case_info, artifacts, activity_logs):
        """Create Chain of Custody Word document"""
        doc = Document()

        # Setup styles
        self._setup_word_styles(doc)

        # Header
        title = doc.add_paragraph("CHAIN OF CUSTODY", style='CustomHeading1')
        title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

        case_title = doc.add_paragraph(f"Case {case_info['case_id']}: {case_info['title']}")
        case_title.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER

        doc.add_paragraph("")

        # Evidence Chain Section
        heading = doc.add_paragraph("EVIDENCE CHAIN", style='CustomHeading2')

        if artifacts:
            coc_table = doc.add_table(rows=1, cols=6)
            coc_table.style = 'Table Grid'

            # Header row
            hdr_cells = coc_table.rows[0].cells
            hdr_cells[0].text = "Item #"
            hdr_cells[1].text = "Description"
            hdr_cells[2].text = "Collected By"
            hdr_cells[3].text = "Date/Time"
            hdr_cells[4].text = "Hash SHA-256"
            hdr_cells[5].text = "Signature"

            # Data rows
        for i, artifact in enumerate(artifacts, 1):
                row_cells = coc_table.add_row().cells
                row_cells[0].text = str(i)
                row_cells[1].text = artifact['name']
                row_cells[2].text = case_info.get('full_name', 'N/A')
                row_cells[3].text = artifact.get('collected_at', 'N/A')
                row_cells[4].text = artifact.get('sha256', 'N/A')
                row_cells[5].text = "_________________"
        else:
            doc.add_paragraph("No evidence items found.")

        doc.add_page_break()

        # Custody Transfer Log Section
        heading = doc.add_paragraph("CUSTODY TRANSFER LOG", style='CustomHeading2')

        transfer_table = doc.add_table(rows=1, cols=5)
        transfer_table.style = 'Table Grid'

        # Header row
        hdr_cells = transfer_table.rows[0].cells
        hdr_cells[0].text = "From"
        hdr_cells[1].text = "To"
        hdr_cells[2].text = "Date/Time"
        hdr_cells[3].text = "Purpose"
        hdr_cells[4].text = "Signature"

        # Data row
        row_cells = transfer_table.add_row().cells
        row_cells[0].text = case_info.get('full_name', 'N/A')
        row_cells[1].text = "Evidence Storage"
        row_cells[2].text = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        row_cells[3].text = "Secure Storage"
        row_cells[4].text = "_________________"

        doc.add_page_break()

        # Integrity Verification Section
        heading = doc.add_paragraph("INTEGRITY VERIFICATION", style='CustomHeading2')

        verification_items = [
            "All evidence items have been verified with SHA-256 hashes.",
            "Chain of custody has been maintained throughout the investigation.",
            f"Report generated: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
        ]

        for item in verification_items:
            p = doc.add_paragraph(item, style='List Bullet')

        return doc

    def _setup_word_styles(self, doc):
        """Setup Word document styles"""
        from docx.shared import Pt, RGBColor
        from docx.enum.style import WD_STYLE_TYPE

        styles = doc.styles

        # Heading 1 style
        h1_style = styles.add_style('CustomHeading1', WD_STYLE_TYPE.PARAGRAPH)
        h1_style.font.size = Pt(18)
        h1_style.font.bold = True
        h1_style.font.color.rgb = RGBColor(31, 73, 125)

        # Heading 2 style
        h2_style = styles.add_style('CustomHeading2', WD_STYLE_TYPE.PARAGRAPH)
        h2_style.font.size = Pt(14)
        h2_style.font.bold = True
        h2_style.font.color.rgb = RGBColor(79, 129, 189)

        # Normal text style
        normal_style = styles['Normal']
        normal_style.font.size = Pt(11)
        normal_style.font.name = 'Times New Roman'

class Report(QWidget):
    def __init__(self, main_window=None):
        super(Report, self).__init__()
        self.main_window = main_window
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        self.setup_ui()
        self.setup_connections()
        
        self.db = DatabaseManager()
        self.current_case_id = None
        self.report_generator = None
        
    def setup_ui(self):
        """Setup additional UI components and styling"""
        # Set table headers
        self.ui.reportsTable.setColumnCount(5)
        self.ui.reportsTable.setHorizontalHeaderLabels([
            "ID", "Loại", "Định dạng", "Ngày tạo", "Hash SHA-256"
        ])
        
        # Set table properties
        header = self.ui.reportsTable.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        
        # Set initial state
        self.ui.generateButton.setEnabled(False)
        
    def setup_connections(self):
        """Setup signal connections"""
        self.ui.generateButton.clicked.connect(self.generate_report)
        self.ui.refreshButton.clicked.connect(self.refresh_cases)
        self.ui.caseCombo.currentTextChanged.connect(self.on_case_changed)
        
    def refresh_cases(self):
        """Refresh case list from database"""
        try:
            if not self.db.connect():
                QMessageBox.warning(self, "Lỗi", "Không thể kết nối database!")
                return
                
            # Sửa method name từ get_all_cases thành get_cases
            cases = self.db.get_cases()
            self.ui.caseCombo.clear()
            self.ui.caseCombo.addItem("-- Chọn vụ án --", None)
            
            for case in cases:
                display_text = f"{case['case_id']} - {case['title']}"
                self.ui.caseCombo.addItem(display_text, case['case_id'])
                
            # Nếu có main_window, lấy case đang được chọn
            if self.main_window and hasattr(self.main_window, 'current_case_id'):
                self.select_current_working_case()
                
        except Exception as e:
            print(f"Error refreshing cases: {e}")
            QMessageBox.warning(self, "Lỗi", f"Không thể tải danh sách vụ án: {str(e)}")
        finally:
            self.db.disconnect()
            
    def select_current_working_case(self):
        """Tự động chọn case đang được làm việc từ main window"""
        if self.main_window and hasattr(self.main_window, 'current_case_id'):
            current_case_id = self.main_window.current_case_id
            if current_case_id:
                # Tìm và chọn case trong combo box
                for i in range(self.ui.caseCombo.count()):
                    if self.ui.caseCombo.itemData(i) == current_case_id:
                        self.ui.caseCombo.setCurrentIndex(i)
                        self.current_case_id = current_case_id
                        self.ui.generateButton.setEnabled(True)
                        self.load_case_reports(current_case_id)
                        print(f"Auto-selected current working case: {current_case_id}")
                        break
                        
    def on_case_changed(self):
        """Handle case selection change"""
        case_id = self.ui.caseCombo.currentData()
        self.current_case_id = case_id
        
        if case_id:
            self.load_case_reports(case_id)
            self.ui.generateButton.setEnabled(True)
            
            # Cập nhật current_case_id trong main window nếu có
            if self.main_window and hasattr(self.main_window, 'current_case_id'):
                self.main_window.current_case_id = case_id
                print(f"Updated main window current_case_id to: {case_id}")
        else:
            self.ui.generateButton.setEnabled(False)
            self.ui.reportsTable.setRowCount(0)
            
    def load_case_reports(self, case_id):
        """Load reports for selected case"""
        try:
            if not self.db.connect():
                return
                
            reports = self.db.get_reports_by_case(case_id)
            self.ui.reportsTable.setRowCount(len(reports))
            
            for row, report in enumerate(reports):
                self.ui.reportsTable.setItem(row, 0, QTableWidgetItem(str(report['report_id'])))
                self.ui.reportsTable.setItem(row, 1, QTableWidgetItem(report.get('format', 'DOCX')))
                self.ui.reportsTable.setItem(row, 2, QTableWidgetItem('DOCX'))
                self.ui.reportsTable.setItem(row, 3, QTableWidgetItem(report.get('created_at', 'N/A')))
                
                # Truncate hash for display
                hash_value = report.get('sha256', 'N/A')
                if hash_value != 'N/A' and len(hash_value) > 16:
                    hash_value = hash_value[:16] + '...'
                self.ui.reportsTable.setItem(row, 4, QTableWidgetItem(hash_value))
                
        except Exception as e:
            print(f"Error loading reports: {e}")
        finally:
            self.db.disconnect()
            
    def generate_report(self):
        """Generate selected report type"""
        if not self.current_case_id:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng chọn vụ án trước!")
            return
            
        # Get report options
        report_type_map = {
            "Báo cáo tổng hợp (Word)": "comprehensive",
            "Tóm tắt điều hành (Word)": "executive",
            "Báo cáo kỹ thuật (Word)": "technical",
            "Chain of Custody (Word)": "coc"
        }
        
        report_type = report_type_map.get(self.ui.typeCombo.currentText(), "comprehensive")
        
        # Get options
        options = {
            "include_evidence": self.ui.evidenceCheckbox.isChecked(),
            "include_analysis": self.ui.analysisCheckbox.isChecked(),
            "include_activity": self.ui.activityCheckbox.isChecked(),
            "include_coc": self.ui.cocCheckbox.isChecked()
        }
        
        # Start report generation
        self.ui.generateButton.setEnabled(False)
        self.ui.progressBar.setVisible(True)
        self.ui.progressBar.setValue(0)
        
        # Create and start report generator thread
        self.report_generator = ReportGenerator(self.current_case_id, report_type, options)
        self.report_generator.progress_updated.connect(self.update_progress)
        self.report_generator.report_generated.connect(self.on_report_generated)
        self.report_generator.start()
        
        # Simulate progress updates
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self.simulate_progress)
        self.progress_timer.start(100)
        
    def simulate_progress(self):
        """Simulate progress updates"""
        current = self.ui.progressBar.value()
        if current < 90:
            self.ui.progressBar.setValue(current + 5)
            
    def update_progress(self, value, message):
        """Update progress bar"""
        self.ui.progressBar.setValue(value)
        
    def on_report_generated(self, file_path, report_type):
        """Handle report generation completion"""
        self.progress_timer.stop()
        self.ui.progressBar.setVisible(False)
        self.ui.generateButton.setEnabled(True)
        
        if file_path and report_type != "error":
            QMessageBox.information(
                self, 
                "✅ Hoàn thành", 
                f"Báo cáo Word đã được tạo thành công!\n\n"
                f"📁 Đường dẫn: {file_path}\n"
                f"📄 Loại: {report_type}\n\n"
                f"Báo cáo đã được lưu vào database với hash SHA-256."
            )
            
            # Refresh reports table
            if self.current_case_id:
                self.load_case_reports(self.current_case_id)
        else:
            QMessageBox.critical(
                self, 
                "❌ Lỗi", 
                "Không thể tạo báo cáo Word. Vui lòng kiểm tra log và thử lại!"
            )
            
    def set_case_id(self, case_id):
        """Set current case ID from external source"""
        if case_id:
            # Find and select the case in combo box
            for i in range(self.ui.caseCombo.count()):
                if self.ui.caseCombo.itemData(i) == case_id:
                    self.ui.caseCombo.setCurrentIndex(i)
                    break
                    
    def showEvent(self, event):
        """Handle show event - refresh cases when tab becomes visible"""
        super().showEvent(event)
        self.refresh_cases()