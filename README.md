# Windows Forensic System

🔍 **Hệ thống điều tra số dành cho Windows** - Công cụ toàn diện để thu thập, phân tích và báo cáo bằng chứng số.

## 📋 Tính năng chính

### 🏠 Quản lý hệ thống
- **Dashboard**: Tổng quan hệ thống và số liệu thống kê
- **Quản lý vụ án**: Tạo, theo dõi và phân công vụ án
- **Quản lý người dùng**: Hệ thống phân quyền và xác thực

### 📊 Thu thập dữ liệu
- **Dữ liệu khả biến (Volatile)**: RAM, process, network connections, clipboard, command history
- **Dữ liệu bất biến (Non-volatile)**: Disk images, file systems, registry, browser data, event logs

### 🔬 Phân tích dữ liệu
- **Phân tích bộ nhớ**: Memory dump analysis với Volatility 3
- **Phân tích Registry**: Windows Registry forensics
- **Phân tích trình duyệt**: Browser history, cache, cookies
- **Phân tích file**: File metadata, deleted files
- **Phân tích metadata**: EXIF, document metadata
- **Phân tích Event Logs**: Windows event logs
- **Phân tích Crash Dump**: Windows crash dump analysis

### 📝 Báo cáo
- **Tạo báo cáo**: Export kết quả phân tích
- **Định dạng**: JSON, Text, XML
- **Chain of Custody**: Nhật ký theo dõi toàn vẹn bằng chứng

## 🛠️ Công nghệ sử dụng

- **Frontend**: PyQt5 (GUI Framework)
- **Backend**: Python 3.12+
- **Database**: SQLite3
- **Architecture**: MVC Pattern
- **Forensic Tools**: Volatility 3, WinPmem, CDB, YARA, PEfile, Pytsk3

## 📁 Cấu trúc project

```
Windows_forensic/
├── main.py                          # Entry point của ứng dụng
├── models/                          # Database layer (Models)
│   ├── db_manager.py               # Database operations & business logic
│   ├── schema.sql                  # Database schema
│   ├── init_db.py                  # Database initialization
│   ├── hash_types.py              # Hash utilities
│   └── integrity_workflow.py      # Integrity checking
├── controllers/                    # Controllers (Business Logic)
│   ├── main_window_controller.py   # Main application controller
│   ├── login_window.py            # Authentication controller
│   ├── case_management.py         # Case management controller
│   ├── user_management.py         # User management controller
│   ├── dashboard.py               # Dashboard controller
│   ├── collect/                   # Data collection controllers
│   │   ├── volatile/
│   │   │   └── volatile.py        # Volatile data collection
│   │   └── nonvolatile/
│   │       └── nonvolatile.py     # Non-volatile data collection
│   ├── analysis/                  # Analysis controllers
│   │   ├── memory_analysis.py     # Memory analysis (Volatility 3)
│   │   ├── registry_analysis.py   # Registry analysis
│   │   ├── browser_analysis.py    # Browser analysis
│   │   ├── file_analysis.py       # File analysis
│   │   ├── metadata_analysis.py   # Metadata analysis
│   │   └── eventlog_analysis.py   # Event log analysis
│   └── report/
│       └── report.py              # Report generation
├── views/                         # User Interface (Views)
│   ├── login_ui.py                # Login UI
│   ├── login.ui                   # Login UI design
│   ├── main_window_ui.py          # Main window UI
│   ├── main_window.ui             # Main window UI design
│   └── pages/                     # Individual page UIs
├── static/                        # Static assets
│   └── icons/                     # Application icons
├── tools/                         # Forensic tools & utilities
├── utils/                         # Utility functions
│   └── path_utils.py              # Path utilities
├── requirements.txt               # Python dependencies
└── README.md                      # Documentation
```

## 🚀 Cài đặt và chạy

### Yêu cầu hệ thống
- **Python**: 3.8+ (Khuyến nghị: 3.12+)
- **OS**: Windows 10/11 (64-bit)
- **RAM**: Tối thiểu 4GB, khuyến nghị 8GB+
- **Disk**: Tối thiểu 2GB dung lượng trống
- **Quyền**: Administrator (để thu thập RAM và một số evidence)

### 1. Clone repository
```bash
git clone https://github.com/YOUR_USERNAME/Windows_forensic.git
cd Windows_forensic
```

### 2. Tạo môi trường ảo
```bash
python -m venv venv
venv\Scripts\activate  # Windows
```

### 3. Cài đặt dependencies
```bash
pip install -r requirements.txt
```

### 4. Khởi tạo database
```bash
python models/init_db.py
```

### 5. Chạy ứng dụng
```bash
python main.py
```

### 6. Đăng nhập
Sử dụng tài khoản mặc định:
- **Username**: `admin`
- **Password**: `admin123`
- **Role**: Administrator

## 👥 Tài khoản mặc định

| Username | Password | Role | Mô tả |
|----------|----------|------|-------|
| admin | admin123 | ADMIN | Quản trị viên hệ thống |

## 🗄️ Database Schema

### Bảng chính:
- **Users**: Thông tin người dùng (username, password_hash, role, email, phone, is_active)
- **Cases**: Thông tin vụ án (title, status, user_id, archive_path, created_at, finished_at)
- **Artefacts**: Bằng chứng số (case_id, name, source_path, evidence_type, size, mime_type, is_deleted)
- **Hashes**: Hash values (artefact_id, hash_type, sha256, generated_at, generated_by)
- **Results**: Kết quả phân tích (artefact_id, tool_used, summary, result_path)
- **Reports**: Báo cáo (case_id, file_path, format, generated_by, sha256)
- **Activity_logs**: Nhật ký hoạt động (case_id, artefact_id, user_id, action, details, timestamp)

### Tính năng đặc biệt:
- **Foreign Key Constraints**: Đảm bảo tính toàn vẹn dữ liệu
- **Soft Delete**: Bảo toàn dữ liệu cho audit trail
- **SHA-256 Hashing**: Kiểm tra tính toàn vẹn evidence
- **Activity Logging**: Theo dõi toàn bộ hoạt động của user

## 🤝 Làm việc nhóm với Git

### Workflow cơ bản:
```bash
# 1. Tạo branch mới cho feature
git checkout -b feature/ten-feature

# 2. Commit thay đổi
git add .
git commit -m "feat: thêm tính năng XYZ"

# 3. Push branch
git push origin feature/ten-feature

# 4. Tạo Pull Request trên GitHub
# 5. Merge sau khi review
```

### Quy tắc commit:
- `feat:` - Tính năng mới
- `fix:` - Sửa lỗi
- `docs:` - Cập nhật tài liệu
- `style:` - Format code
- `refactor:` - Refactor code
- `test:` - Thêm test

## 📦 Dependencies

### Core Dependencies:
```txt
# GUI Framework
PyQt5==5.15.9
PyQt5-Qt5==5.15.2
PyQt5-sip==12.12.1

# Windows Integration
psutil==5.9.5
wmi==1.5.1
pywin32>=305

# Forensic Analysis Libraries
volatility3>=2.4.1
yara-python>=4.2.0
pefile==2023.2.7
pytsk3==20230918
python-registry==1.3.1
exifread==3.0.0
Pillow==10.3.0
pypdf==4.2.0
python-docx>=0.8.11
```

### Built-in Python Modules:
- `sqlite3` - Database operations
- `hashlib` - SHA-256 hashing
- `json`, `os`, `sys` - System utilities
- `threading`, `subprocess` - Process management
- `datetime`, `time` - Time utilities

## 🧪 Testing & Development

### Chạy Tests
```bash
# Test database initialization
python models/init_db.py

# Test basic functionality
python -c "from models.db_manager import DatabaseManager; db = DatabaseManager(); print('Database connection:', db.connect())"
```

### Development Setup
```bash
# Install in development mode
pip install -e .

# Run with debug mode
python main.py --debug
```

## 🔧 Sử dụng hệ thống

### Quy trình làm việc cơ bản:

1. **Đăng nhập**: Sử dụng tài khoản admin mặc định
2. **Tạo Case**: Tạo vụ án mới hoặc chọn case hiện có
3. **Thu thập Evidence**:
   - Chọn tab "Volatile" để thu thập RAM, processes, network
   - Chọn tab "Non-Volatile" để thu thập disk, registry, files
4. **Phân tích**: Sử dụng các tab phân tích tương ứng
5. **Tạo báo cáo**: Export kết quả phân tích

### Lưu ý quan trọng:
- **Quyền Administrator**: Cần để thu thập RAM và một số evidence
- **Dung lượng ổ cứng**: RAM dump có thể lớn (4-16GB)
- **Thời gian**: Quá trình thu thập có thể mất vài phút
- **Chain of Custody**: Hệ thống tự động log toàn bộ hoạt động

## 📝 Đóng góp

### Quy trình đóng góp:
1. Fork repository
2. Tạo branch cho feature: `git checkout -b feature/ten-feature`
3. Thực hiện thay đổi và test
4. Commit với message rõ ràng: `git commit -m "feat: thêm tính năng XYZ"`
5. Push và tạo Pull Request

### Coding Standards:
- Sử dụng type hints cho functions
- Comment code bằng tiếng Việt
- Follow PEP 8 style guidelines
- Test functionality trước khi commit

## 📄 License

Distributed under the MIT License. See `LICENSE` file for more information.

## 📞 Liên hệ & Hỗ trợ

- **Email**: halinh9716@gmail.com
- **Phone**: 0357857581
- **Project Link**: [https://github.com/Tlink/Windows_forensic](https://github.com/Tlink/Windows_forensic)

### Hỗ trợ kỹ thuật:
- Thời gian: 8:00 - 17:00 (Thứ 2 - Thứ 6)
- Phạm vi: Cấu hình, troubleshooting, feature requests
- Không hỗ trợ: Phát triển custom features

## 🙏 Acknowledgments

- **PyQt5 Community**: GUI framework documentation và support
- **SQLite Documentation**: Database design và optimization
- **Volatility Foundation**: Memory analysis framework
- **Digital Forensics Community**: Best practices và methodologies
- **Microsoft**: Windows internals documentation

---

## 🔐 Bảo mật & Pháp lý

### Lưu ý pháp lý:
- Chỉ sử dụng công cụ này cho mục đích điều tra hợp pháp
- Đảm bảo có ủy quyền trước khi thu thập evidence
- Tuân thủ quy định về bảo mật dữ liệu
- Bảo toàn chain of custody trong quá trình điều tra

### Tính năng bảo mật:
- SHA-256 hashing cho tất cả evidence
- Activity logging đầy đủ
- Role-based access control
- Data integrity verification 