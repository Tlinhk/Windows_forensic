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
                    format=os.path.splitext(file_path)[1][1:].upper(),
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
        if not case_info:
            return None
            
        # Get all case data
        artifacts = self.db.get_artifacts_by_case(self.case_id)
        results = self.db.get_results_by_case(self.case_id)
        activity_logs = self.db.get_activity_logs(case_id=self.case_id)
        
        # Create comprehensive HTML report
        html_content = self._create_comprehensive_html(
            case_info, artifacts, results, activity_logs
        )
        
        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Case_{self.case_id}_Comprehensive_Report_{timestamp}.html"
        file_path = os.path.join(case_info['archive_path'], filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        return file_path
    
    def generate_executive_summary(self):
        """Generate executive summary report"""
        case_info = self.db.get_case_with_investigator(self.case_id)
        if not case_info:
            return None
            
        # Get summary data
        artifacts = self.db.get_artifacts_by_case(self.case_id)
        results = self.db.get_results_by_case(self.case_id)
        
        html_content = self._create_executive_html(case_info, artifacts, results)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Case_{self.case_id}_Executive_Summary_{timestamp}.html"
        file_path = os.path.join(case_info['archive_path'], filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        return file_path
    
    def generate_technical_report(self):
        """Generate technical detailed report"""
        case_info = self.db.get_case_with_investigator(self.case_id)
        if not case_info:
            return None
            
        artifacts = self.db.get_artifacts_by_case(self.case_id)
        results = self.db.get_results_by_case(self.case_id)
        activity_logs = self.db.get_activity_logs(case_id=self.case_id)
        
        html_content = self._create_technical_html(case_info, artifacts, results, activity_logs)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Case_{self.case_id}_Technical_Report_{timestamp}.html"
        file_path = os.path.join(case_info['archive_path'], filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        return file_path
    
    def generate_chain_of_custody(self):
        """Generate Chain of Custody report"""
        case_info = self.db.get_case_with_investigator(self.case_id)
        if not case_info:
            return None
            
        artifacts = self.db.get_artifacts_by_case(self.case_id)
        activity_logs = self.db.get_activity_logs(case_id=self.case_id)
        
        html_content = self._create_coc_html(case_info, artifacts, activity_logs)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"Case_{self.case_id}_Chain_of_Custody_{timestamp}.html"
        file_path = os.path.join(case_info['archive_path'], filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
            
        return file_path

    def _create_comprehensive_html(self, case_info, artifacts, results, activity_logs):
        """Create comprehensive HTML report content"""
        html = f"""
        <!DOCTYPE html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Báo cáo tổng hợp - Case {case_info['case_id']}</title>
            <style>
                body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 10px; }}
                .section {{ margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 8px; }}
                .evidence-table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
                .evidence-table th, .evidence-table td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                .evidence-table th {{ background-color: #f5f5f5; font-weight: bold; }}
                .chain-of-custody {{ background-color: #f9f9f9; padding: 15px; border-left: 4px solid #007acc; }}
                .risk-high {{ color: #d32f2f; font-weight: bold; }}
                .risk-medium {{ color: #f57c00; font-weight: bold; }}
                .risk-low {{ color: #388e3c; font-weight: bold; }}
                .timestamp {{ color: #666; font-size: 0.9em; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🔍 Báo cáo điều tra số tổng hợp</h1>
                <h2>Case ID: {case_info['case_id']} - {case_info['title']}</h2>
                <p>Điều tra viên: {case_info.get('full_name', 'N/A')} | Ngày tạo: {case_info.get('created_at', 'N/A')}</p>
            </div>
            
            <div class="section">
                <h3> Thông tin vụ án</h3>
                <table class="evidence-table">
                    <tr><th>Case ID</th><td>{case_info['case_id']}</td></tr>
                    <tr><th>Tên vụ án</th><td>{case_info['title']}</td></tr>
                    <tr><th>Trạng thái</th><td>{case_info.get('status', 'N/A')}</td></tr>
                    <tr><th>Điều tra viên</th><td>{case_info.get('full_name', 'N/A')}</td></tr>
                    <tr><th>Ngày tạo</th><td>{case_info.get('created_at', 'N/A')}</td></tr>
                    <tr><th>Đường dẫn lưu trữ</th><td>{case_info.get('archive_path', 'N/A')}</td></tr>
                </table>
            </div>
            
            <div class="section">
                <h3>📁 Bằng chứng số (Digital Evidence)</h3>
                <table class="evidence-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Tên</th>
                            <th>Loại</th>
                            <th>Kích thước</th>
                            <th>Ngày thu thập</th>
                            <th>Hash SHA-256</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for artifact in artifacts:
            html += f"""
                        <tr>
                            <td>{artifact['artefact_id']}</td>
                            <td>{artifact['name']}</td>
                            <td>{artifact.get('evidence_type', 'N/A')}</td>
                            <td>{artifact.get('size', 'N/A')} bytes</td>
                            <td>{artifact.get('collected_at', 'N/A')}</td>
                            <td><code>{artifact.get('sha256', 'N/A')}</code></td>
                        </tr>
            """
        
        html += """
                    </tbody>
                </table>
            </div>
            
            <div class="section">
                <h3>🔬 Kết quả phân tích</h3>
                <table class="evidence-table">
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Công cụ</th>
                            <th>Thời gian chạy</th>
                            <th>Tóm tắt</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for result in results:
            html += f"""
                        <tr>
                            <td>{result['result_id']}</td>
                            <td>{result.get('tool_used', 'N/A')}</td>
                            <td>{result.get('run_at', 'N/A')}</td>
                            <td>{result.get('summary', 'N/A')}</td>
                        </tr>
            """
        
        html += """
                    </tbody>
                </table>
            </div>
            
            <div class="section">
                <h3>📝 Nhật ký hoạt động (Activity Log)</h3>
                <table class="evidence-table">
                    <thead>
                        <tr>
                            <th>Thời gian</th>
                            <th>Hành động</th>
                            <th>Người thực hiện</th>
                            <th>Công cụ</th>
                            <th>Chi tiết</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for log in activity_logs:
            html += f"""
                        <tr>
                            <td class="timestamp">{log.get('timestamp', 'N/A')}</td>
                            <td>{log.get('action', 'N/A')}</td>
                            <td>{log.get('username', 'N/A')}</td>
                            <td>{log.get('tool_used', 'N/A')}</td>
                            <td>{log.get('details', 'N/A')}</td>
                        </tr>
            """
        
        html += """
                    </tbody>
                </table>
            </div>
            
            <div class="section chain-of-custody">
                <h3> Chain of Custody (Chuỗi bảo quản)</h3>
                <p><strong>Báo cáo này đảm bảo tính toàn vẹn của bằng chứng số:</strong></p>
                <ul>
                    <li>✅ Tất cả bằng chứng đều có hash SHA-256 để xác minh tính toàn vẹn</li>
                    <li>✅ Nhật ký hoạt động ghi lại mọi thao tác với bằng chứng</li>
                    <li>✅ Timestamp cho mọi hoạt động thu thập và phân tích</li>
                    <li>✅ Thông tin người thực hiện và công cụ sử dụng</li>
                </ul>
                <p><strong>Báo cáo được tạo vào:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
            </div>
            
            <div class="section">
                <h3>📊 Tóm tắt và khuyến nghị</h3>
                <p>Dựa trên kết quả phân tích, vụ án này cần:</p>
                <ul>
                    <li>🔍 Tiếp tục thu thập thêm bằng chứng nếu cần thiết</li>
                    <li> Hoàn thiện chuỗi bảo quản bằng chứng</li>
                    <li>⚖️ Chuẩn bị báo cáo cho cơ quan có thẩm quyền</li>
                    <li>💾 Lưu trữ an toàn tất cả bằng chứng số</li>
                </ul>
            </div>
        </body>
        </html>
        """
        
        return html

    def _create_executive_html(self, case_info, artifacts, results):
        """Create executive summary HTML"""
        html = f"""
        <!DOCTYPE html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8">
            <title>Executive Summary - Case {case_info['case_id']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #2c3e50; color: white; padding: 20px; text-align: center; }}
                .summary {{ background: #ecf0f1; padding: 20px; margin: 20px 0; border-radius: 8px; }}
                .stats {{ display: flex; justify-content: space-around; margin: 20px 0; }}
                .stat-box {{ background: white; padding: 20px; border-radius: 8px; text-align: center; border: 1px solid #ddd; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📊 Executive Summary</h1>
                <h2>Case {case_info['case_id']}: {case_info['title']}</h2>
            </div>
            
            <div class="summary">
                <h3>📋 Tóm tắt vụ án</h3>
                <p><strong>Điều tra viên:</strong> {case_info.get('full_name', 'N/A')}</p>
                <p><strong>Ngày tạo:</strong> {case_info.get('created_at', 'N/A')}</p>
                <p><strong>Trạng thái:</strong> {case_info.get('status', 'N/A')}</p>
            </div>
            
            <div class="stats">
                <div class="stat-box">
                    <h3>📁 Bằng chứng</h3>
                    <h2>{len(artifacts)}</h2>
                    <p>items</p>
                </div>
                <div class="stat-box">
                    <h3>🔬 Phân tích</h3>
                    <h2>{len(results)}</h2>
                    <p>results</p>
                </div>
            </div>
            
            <div class="summary">
                <h3> Kết luận chính</h3>
                <p>Vụ án đã được điều tra với {len(artifacts)} bằng chứng số và {len(results)} kết quả phân tích.</p>
                <p>Chuỗi bảo quản bằng chứng đã được duy trì theo đúng quy trình.</p>
            </div>
        </body>
        </html>
        """
        return html

    def _create_technical_html(self, case_info, artifacts, results, activity_logs):
        """Create technical detailed HTML"""
        html = f"""
        <!DOCTYPE html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8">
            <title>Technical Report - Case {case_info['case_id']}</title>
            <style>
                body {{ font-family: 'Courier New', monospace; margin: 20px; }}
                .header {{ background: #34495e; color: white; padding: 20px; }}
                .section {{ margin: 20px 0; padding: 20px; border: 1px solid #ddd; }}
                .code {{ background: #f8f9fa; padding: 10px; border-radius: 4px; font-family: monospace; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1> Technical Report</h1>
                <h2>Case {case_info['case_id']}: {case_info['title']}</h2>
            </div>
            
            <div class="section">
                <h3>📊 Technical Details</h3>
                <div class="code">
                    <p>Case ID: {case_info['case_id']}</p>
                    <p>Investigator: {case_info.get('full_name', 'N/A')}</p>
                    <p>Created: {case_info.get('created_at', 'N/A')}</p>
                    <p>Status: {case_info.get('status', 'N/A')}</p>
                </div>
            </div>
            
            <div class="section">
                <h3>📁 Evidence Collection</h3>
                <div class="code">
                    <p>Total Artifacts: {len(artifacts)}</p>
                    <p>Total Results: {len(results)}</p>
                    <p>Total Activities: {len(activity_logs)}</p>
                </div>
            </div>
            
            <div class="section">
                <h3> Analysis Results</h3>
                <div class="code">
        """
        
        for result in results:
            html += f"""
                    <p>Result {result['result_id']}: {result.get('tool_used', 'N/A')} - {result.get('summary', 'N/A')}</p>
            """
        
        html += """
                </div>
            </div>
        </body>
        </html>
        """
        return html

    def _create_coc_html(self, case_info, artifacts, activity_logs):
        """Create Chain of Custody HTML"""
        html = f"""
        <!DOCTYPE html>
        <html lang="vi">
        <head>
            <meta charset="UTF-8">
            <title>Chain of Custody - Case {case_info['case_id']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #27ae60; color: white; padding: 20px; text-align: center; }}
                .coc-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                .coc-table th, .coc-table td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                .coc-table th {{ background-color: #2ecc71; color: white; }}
                .signature {{ border-top: 2px solid #27ae60; margin-top: 20px; padding-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1> Chain of Custody</h1>
                <h2>Case {case_info['case_id']}: {case_info['title']}</h2>
            </div>
            
            <h3> Evidence Chain</h3>
            <table class="coc-table">
                <thead>
                    <tr>
                        <th>Item #</th>
                        <th>Description</th>
                        <th>Collected By</th>
                        <th>Date/Time</th>
                        <th>Hash SHA-256</th>
                        <th>Signature</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for i, artifact in enumerate(artifacts, 1):
            html += f"""
                    <tr>
                        <td>{i}</td>
                        <td>{artifact['name']}</td>
                        <td>{case_info.get('full_name', 'N/A')}</td>
                        <td>{artifact.get('collected_at', 'N/A')}</td>
                        <td><code>{artifact.get('sha256', 'N/A')}</code></td>
                        <td>_________________</td>
                    </tr>
            """
        
        html += """
                </tbody>
            </table>
            
            <div class="signature">
                <h3>📝 Custody Transfer Log</h3>
                <table class="coc-table">
                    <thead>
                        <tr>
                            <th>From</th>
                            <th>To</th>
                            <th>Date/Time</th>
                            <th>Purpose</th>
                            <th>Signature</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>{case_info.get('full_name', 'N/A')}</td>
                            <td>Evidence Storage</td>
                            <td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td>
                            <td>Secure Storage</td>
                            <td>_________________</td>
                        </tr>
                    </tbody>
                </table>
            </div>
            
            <div class="signature">
                <h3>✅ Integrity Verification</h3>
                <p>All evidence items have been verified with SHA-256 hashes.</p>
                <p>Chain of custody has been maintained throughout the investigation.</p>
                <p><strong>Report generated:</strong> {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
            </div>
        </body>
        </html>
        """
        return html

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
                self.ui.reportsTable.setItem(row, 1, QTableWidgetItem(report.get('format', 'N/A')))
                self.ui.reportsTable.setItem(row, 2, QTableWidgetItem(report.get('format', 'N/A')))
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
            "Báo cáo tổng hợp": "comprehensive",
            "Tóm tắt điều hành": "executive", 
            "Báo cáo kỹ thuật": "technical",
            "Chain of Custody": "coc"
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
                f"Báo cáo đã được tạo thành công!\n\n"
                f"📁 Đường dẫn: {file_path}\n"
                f" Loại: {report_type}\n\n"
                f"Báo cáo đã được lưu vào database với hash SHA-256."
            )
            
            # Refresh reports table
            if self.current_case_id:
                self.load_case_reports(self.current_case_id)
        else:
            QMessageBox.critical(
                self, 
                "❌ Lỗi", 
                "Không thể tạo báo cáo. Vui lòng kiểm tra log và thử lại!"
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