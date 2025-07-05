# Windows Forensic System

🔍 **Hệ thống điều tra số dành cho Windows** - Công cụ toàn diện để thu thập, phân tích và báo cáo bằng chứng số.

## 📋 Tính năng chính

### 🏠 Quản lý hệ thống
- **Dashboard**: Tổng quan hệ thống và số liệu thống kê
- **Quản lý vụ án**: Tạo, theo dõi và phân công vụ án
- **Quản lý người dùng**: Hệ thống phân quyền và xác thực

### 📊 Thu thập dữ liệu
- **Dữ liệu khả biến**: RAM, process, network connections
- **Dữ liệu bất biến**: Disk images, file systems, registry

### 🔬 Phân tích dữ liệu  
- **Phân tích bộ nhớ**: Memory dump analysis
- **Phân tích sổ đăng ký**: Windows Registry forensics
- **Phân tích trình duyệt**: Browser history, cache, cookies
- **Phân tích hệ thống tệp**: File metadata, deleted files
- **Phân tích siêu dữ liệu**: EXIF, document metadata
- **Phân tích nhật ký**: Windows event logs

### 📝 Báo cáo
- **Tạo báo cáo**: Export kết quả phân tích
- **Định dạng**: PDF, HTML, JSON

## 🛠️ Công nghệ sử dụng

- **Frontend**: PyQt5
- **Backend**: Python 3.12+
- **Database**: SQLite3
- **Architecture**: MVC Pattern

## 📁 Cấu trúc project

```
Windows_forensic/
├── main.py                 # Entry point
├── login_window.py         # Login interface
├── database/               # Database layer
│   ├── schema.sql         # Database schema
│   ├── db_manager.py      # Database operations
│   └── init_db.py         # Database initialization
├── ui/                     # User Interface
│   ├── main_window.ui     # Main window design
│   ├── main_window_ui.py  # Generated UI code
│   └── pages/             # Individual page UIs
├── pages_functions/        # Business logic
│   ├── dashboard.py
│   ├── case_management.py
│   ├── user_management.py
│   ├── collect/           # Data collection modules
│   ├── analysis/          # Analysis modules
│   └── report/            # Reporting modules
├── static/                 # Static assets
│   └── icons/             # Application icons
└── venv/                  # Virtual environment
```

## 🚀 Cài đặt và chạy

### 1. Clone repository
```bash
git clone https://github.com/YOUR_USERNAME/Windows_forensic.git
cd Windows_forensic
```

### 2. Tạo môi trường ảo
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
```

### 3. Cài đặt dependencies
```bash
pip install -r requirements.txt
```

### 4. Khởi tạo database
```bash
cd database
python init_db.py
cd ..
```

### 5. Chạy ứng dụng
```bash
python main.py
```

## 👥 Tài khoản mặc định

| Username | Password | Role | Mô tả |
|----------|----------|------|-------|
| admin | admin123 | ADMIN | Quản trị viên hệ thống |
| investigator1 | invest123 | INVESTIGATOR | Điều tra viên |

## 🗄️ Database Schema
- **Users**: Thông tin người dùng
- **Cases**: Thông tin vụ án
- **Case_Assignees**: Phân công vụ án (n-n relationship)
- **Artefacts**: Bằng chứng số
- **Results**: Kết quả phân tích
- **Reports**: Báo cáo
- **Activity_logs**: Nhật ký hoạt động

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

Xem file `requirements.txt` để biết danh sách đầy đủ. Các package chính:

- `PyQt5` - GUI framework
- `sqlite3` - Database (built-in)
- `hashlib` - Password hashing (built-in)

## 🧪 Testing

```bash
# Chạy tests (khi có)
python -m pytest tests/

# Test database
cd database
python init_db.py
```

## 📝 Đóng góp

1. Fork repository
2. Tạo branch cho feature: `git checkout -b feature/amazing-feature`
3. Commit thay đổi: `git commit -m 'feat: thêm amazing feature'`
4. Push branch: `git push origin feature/amazing-feature`
5. Tạo Pull Request

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

## 📞 Liên hệ

- **Email**: halinh9716@gmail.com
- **Phone**: 0357857581
- **Project Link**: [https://github.com/YOUR_USERNAME/Windows_forensic](https://github.com/Tlink/Windows_forensic)

## 🙏 Acknowledgments

- PyQt5 Documentation
- SQLite Documentation
- Digital Forensics community 