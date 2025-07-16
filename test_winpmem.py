#!/usr/bin/env python3
"""
Test script for WinPmem RAM collection
"""
import os
import subprocess
import time
import ctypes
from datetime import datetime

def is_admin():
    """Check if the current process has admin privileges"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def test_winpmem():
    """Test WinPmem functionality"""
    print("=== WinPmem Test Script ===")
    
    # Check admin privileges
    if not is_admin():
        print("❌ Script không chạy với quyền Administrator")
        print("💡 Vui lòng chạy script này với quyền Administrator")
        return False
    else:
        print("✅ Script đang chạy với quyền Administrator")
    
    # Check WinPmem path
    winpmem_path = os.path.abspath(os.path.join('tools', 'winpmem_mini_x64_rc2.exe'))
    if not os.path.exists(winpmem_path):
        print(f"❌ Không tìm thấy WinPmem tại: {winpmem_path}")
        return False
    else:
        print(f"✅ Tìm thấy WinPmem tại: {winpmem_path}")
    
    # Create test directory
    test_dir = os.path.join(os.getcwd(), "test_ram_dump")
    os.makedirs(test_dir, exist_ok=True)
    print(f"📁 Thư mục test: {test_dir}")
    
    # Test output file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = os.path.join(test_dir, f"test_memory_{timestamp}.raw")
    print(f"📄 File output sẽ là: {output_file}")
    
    # Test direct command
    print("\n🔄 Thử chạy WinPmem trực tiếp...")
    direct_cmd = [winpmem_path, "--format", "raw", "--output", output_file]
    print(f"Command: {' '.join(direct_cmd)}")
    
    try:
        result = subprocess.run(direct_cmd, capture_output=True, text=True, timeout=300, cwd=test_dir)
        
        print(f"Return code: {result.returncode}")
        if result.stdout:
            print(f"STDOUT: {result.stdout}")
        if result.stderr:
            print(f"STDERR: {result.stderr}")
        
        if result.returncode == 0:
            print("✅ WinPmem chạy thành công trực tiếp")
        else:
            print("❌ WinPmem trực tiếp thất bại")
            
            # Try PowerShell
            print("\n🔄 Thử với PowerShell...")
            ps_cmd = [
                "powershell",
                "-Command",
                f"Start-Process '{winpmem_path}' -ArgumentList '--format','raw','--output','{output_file}' -WorkingDirectory '{test_dir}' -Verb RunAs -Wait"
            ]
            print(f"PowerShell Command: {' '.join(ps_cmd)}")
            
            result = subprocess.run(ps_cmd, capture_output=True, text=True, timeout=300)
            print(f"PowerShell return code: {result.returncode}")
            if result.stdout:
                print(f"PowerShell STDOUT: {result.stdout}")
            if result.stderr:
                print(f"PowerShell STDERR: {result.stderr}")
    
    except subprocess.TimeoutExpired:
        print("❌ Timeout sau 5 phút")
        return False
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False
    
    # Wait for file
    print("\n⏳ Đang chờ file xuất hiện...")
    elapsed = 0
    while elapsed < 60 and not os.path.exists(output_file):
        time.sleep(5)
        elapsed += 5
        print(f"Chờ {elapsed}/60s...")
    
    if os.path.exists(output_file):
        file_size = os.path.getsize(output_file)
        file_size_mb = file_size / (1024 * 1024)
        print(f"✅ File đã tạo: {output_file}")
        print(f"📊 Kích thước: {file_size_mb:.2f} MB")
        return True
    else:
        print("❌ File không xuất hiện sau 60 giây")
        return False

if __name__ == "__main__":
    success = test_winpmem()
    if success:
        print("\n🎉 Test thành công!")
    else:
        print("\n�� Test thất bại!") 