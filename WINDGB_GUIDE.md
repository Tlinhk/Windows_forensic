# Hướng dẫn sử dụng WinDbg trong Windows Forensic

## Tổng quan
WinDbg (Windows Debugger) là công cụ mạnh mẽ để phân tích crash dump và memory dump trong Windows. Ứng dụng Windows Forensic đã tích hợp WinDbg CLI để tự động phân tích các loại crash dump khác nhau.

## Cài đặt WinDbg

### Cách 1: Windows SDK (Khuyến nghị)
1. Tải Windows SDK từ Microsoft: https://developer.microsoft.com/en-us/windows/downloads/windows-sdk/
2. Trong quá trình cài đặt, chọn "Debugging Tools for Windows"
3. WinDbg sẽ được cài đặt tại:
   - `C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\windbg.exe`
   - `C:\Program Files (x86)\Windows Kits\10\Debuggers\x86\windbg.exe`

### Cách 2: Standalone WinDbg
1. Tải WinDbg từ Microsoft Store hoặc từ trang web chính thức
2. Cài đặt và ghi nhớ đường dẫn

## Sử dụng trong ứng dụng

### 1. Chọn Crash Dump File
- Mở tab "Crash Dump Analysis"
- Click "Browse" để chọn file crash dump (.dmp)
- Ứng dụng sẽ tự động detect loại file

### 2. Cấu hình WinDbg
- **WinDbg Path**: Đường dẫn đến windbg.exe
  - Nếu để trống, ứng dụng sẽ tự động tìm
  - Click "Browse" để chọn thủ công nếu cần

### 3. Chọn loại phân tích

#### Basic Analysis (!analyze -v)
- Phân tích cơ bản với lệnh `!analyze -v`
- Phù hợp cho crash dump đơn giản
- Thời gian chạy nhanh

#### Detailed Analysis (Full)
- Phân tích chi tiết với nhiều lệnh:
  - `!analyze -v`: Phân tích crash
  - `lm`: Liệt kê modules
  - `!process 0 0`: Thông tin process
  - `!thread`: Thông tin thread
  - `!stack`: Stack trace
  - `!irp`: IRP information
  - `!drvobj`: Driver objects
  - `!devobj`: Device objects
  - `!pool`: Memory pool
  - `!vm`: Virtual memory
  - `!memusage`: Memory usage

#### Custom Commands
- Nhập lệnh WinDbg tùy chỉnh
- Phân cách các lệnh bằng dấu chấm phẩy (;)
- Ví dụ: `!analyze -v; lm; !process 0 0`

### 4. Chạy phân tích
- Click "Run WinDbg Analysis"
- Quá trình có thể mất vài phút
- Kết quả sẽ hiển thị trong text area

## Các loại Crash Dump được hỗ trợ

### 1. Complete Memory Dump
- Chứa toàn bộ RAM
- Kích thước lớn
- Thông tin chi tiết nhất

### 2. Kernel Memory Dump
- Chỉ chứa kernel memory
- Kích thước vừa phải
- Phù hợp cho hầu hết crash

### 3. Small Memory Dump (Minidump)
- Chỉ thông tin cơ bản
- Kích thước nhỏ
- Phù hợp cho crash đơn giản

### 4. Automatic Memory Dump
- Tự động tạo khi crash
- Kích thước tùy theo cấu hình

## Kết quả phân tích

### Thông tin cơ bản
- **Crash Reason**: Nguyên nhân crash
- **Bug Check Code**: Mã lỗi (0x...)
- **Faulting Driver**: Driver gây lỗi

### Kết quả chi tiết
- Stack trace
- Memory dump
- Process/Thread information
- Driver information
- IRP details

## Lưu ý quan trọng

### 1. Symbol Files
- WinDbg cần symbol files để hiển thị thông tin chi tiết
- Tự động download từ Microsoft Symbol Server
- Có thể mất thời gian lần đầu

### 2. Timeout
- Phân tích có timeout 5 phút
- Với file lớn có thể cần thời gian hơn
- Có thể tăng timeout trong code nếu cần

### 3. Error Handling
- Nếu WinDbg không tìm thấy, kiểm tra đường dẫn
- Một số crash dump có thể không phân tích được
- Kiểm tra log để debug

## Ví dụ sử dụng

### Phân tích crash dump cơ bản
1. Chọn file crash.dmp
2. Chọn "Basic Analysis"
3. Click "Run WinDbg Analysis"
4. Xem kết quả trong tab "WinDbg Analysis"

### Phân tích chi tiết
1. Chọn file crash.dmp
2. Chọn "Detailed Analysis"
3. Click "Run WinDbg Analysis"
4. Chờ kết quả (có thể mất vài phút)

### Lệnh tùy chỉnh
1. Chọn file crash.dmp
2. Chọn "Custom Commands"
3. Nhập: `!analyze -v; lm; !process 0 0; !thread`
4. Click "Run WinDbg Analysis"

## Troubleshooting

### WinDbg không tìm thấy
- Kiểm tra cài đặt Windows SDK
- Chỉ định đường dẫn thủ công
- Kiểm tra PATH environment variable

### Phân tích thất bại
- Kiểm tra file crash dump có hợp lệ không
- Thử với "Basic Analysis" trước
- Kiểm tra log để xem lỗi chi tiết

### Kết quả trống
- Một số crash dump có thể không có thông tin chi tiết
- Thử với lệnh khác
- Kiểm tra symbol files

## Tài liệu tham khảo
- [WinDbg Documentation](https://docs.microsoft.com/en-us/windows-hardware/drivers/debugger/)
- [Crash Dump Analysis](https://docs.microsoft.com/en-us/windows-hardware/drivers/debugger/analyzing-a-crash-dump)
- [WinDbg Commands](https://docs.microsoft.com/en-us/windows-hardware/drivers/debugger/command-reference) 