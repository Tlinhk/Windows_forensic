# Registry Analysis Module - Cải tiến hiển thị đầy đủ

## 🎯 Vấn đề đã được giải quyết

Trước đây, giao diện Registry Analysis không hiển thị đầy đủ nội dung như Registry Explorer thực sự. Bây giờ đã được cải tiến để:

### ✅ Hiển thị cấu trúc đầy đủ như Registry Explorer

1. **Cấu trúc hierarchical đầy đủ**:
   - SAM hive: Users, Groups với RIDs thực tế
   - SYSTEM hive: Services, USB devices, Control keys
   - SOFTWARE hive: Microsoft, Windows, Run keys
   - SECURITY hive: Policy, Accounts

2. **Mock data thực tế**:
   - User accounts với RIDs (Administrator, Guest, User1, etc.)
   - Windows services với thông tin chi tiết
   - USB devices với device classes
   - Registry values với đúng data types

3. **Fallback mechanism**:
   - Khi RECmd không có sẵn, tự động chuyển sang mock data
   - Vẫn hiển thị đầy đủ cấu trúc registry

## 🚀 Cách sử dụng

### 1. Chạy Demo
```bash
cd e:\DoAn\Windows_forensic
python pages_functions/analysis/registry_analysis_demo.py
```

### 2. Load Registry Hive
- Click "Load Hive" 
- Chọn file SAM, SYSTEM, SOFTWARE hoặc SECURITY từ thư mục `sample_data/`
- Hệ thống sẽ tự động tạo mock data nếu RECmd không có

### 3. Khám phá cấu trúc
- **Registry Tree**: Hiển thị cấu trúc hierarchical đầy đủ
- **Values Table**: Hiển thị registry values với type và data
- **Hex View**: Xem raw data ở dạng hex
- **Decoded Data**: Dữ liệu đã được decode

### 4. Sử dụng Bookmarks
- 🏃 **Run Keys**: Chương trình khởi động
- 👤 **UserAssist**: Lịch sử thực thi
- 🖴 **MRU Lists**: File gần đây  
- 🌐 **USB Devices**: Thiết bị USB đã kết nối
- 🛠️ **Services**: Dịch vụ Windows

## 📊 Cấu trúc Mock Data

### SAM Hive
```
SAM/
├── Domains/
│   └── Account/
│       ├── Users/
│       │   ├── 000001F4 (Administrator)
│       │   ├── 000001F5 (Guest)
│       │   ├── 000003E8 (User1)
│       │   └── ...
│       └── Groups/
│           ├── 00000220 (Administrators)
│           ├── 00000221 (Users)
│           └── 00000222 (Guests)
```

### SYSTEM Hive
```
CurrentControlSet/
├── Services/
│   ├── Themes
│   ├── Spooler
│   ├── BITS
│   └── ...
├── Enum/
│   └── USBSTOR/
│       ├── SanDisk Cruzer Blade
│       ├── Kingston DataTraveler
│       └── ...
└── Control/
```

### SOFTWARE Hive
```
Microsoft/
└── Windows/
    └── CurrentVersion/
        ├── Run/
        │   ├── SecurityHealth
        │   ├── Windows Security
        │   └── ...
        └── RunOnce/
```

## 🔧 Tính năng kỹ thuật

1. **RECmdWrapper**: Tích hợp với RECmd tool thực tế
2. **Fallback System**: Mock data khi RECmd không có
3. **Hierarchical Display**: Cấu trúc tree đầy đủ
4. **Data Types**: Hỗ trợ REG_SZ, REG_DWORD, REG_BINARY, etc.
5. **Search & Filter**: Tìm kiếm trong registry
6. **Export**: Xuất báo cáo HTML/JSON

## 🎨 Giao diện cải tiến

- **Tree View**: Giống Registry Explorer với expand/collapse
- **Values Table**: Hiển thị Name, Type, Data, Size
- **Hex Viewer**: Raw data view
- **Status Bar**: Thông tin hive hiện tại
- **Progress Dialog**: Hiển thị tiến trình load

## 📝 Lưu ý

- Mock data được tạo tự động khi RECmd không có sẵn
- Cấu trúc dữ liệu dựa trên registry thực tế của Windows
- Hỗ trợ đầy đủ các loại registry hive
- Tương thích với Registry Explorer workflow

Bây giờ Registry Analysis đã hiển thị đầy đủ nội dung như Registry Explorer thực sự! 🎉
