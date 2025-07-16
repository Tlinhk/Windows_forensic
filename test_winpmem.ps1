# Test WinPmem with admin privileges
Write-Host "=== WinPmem Test Script (PowerShell) ===" -ForegroundColor Green

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")

if (-not $isAdmin) {
    Write-Host "Script khong chay voi quyen Administrator" -ForegroundColor Red
    Write-Host "Vui long chay PowerShell voi quyen Administrator" -ForegroundColor Yellow
    exit 1
} else {
    Write-Host "Script dang chay voi quyen Administrator" -ForegroundColor Green
}

# Check WinPmem path
$winpmemPath = Join-Path (Get-Location) "tools\winpmem_mini_x64_rc2.exe"
if (-not (Test-Path $winpmemPath)) {
    Write-Host "Khong tim thay WinPmem tai: $winpmemPath" -ForegroundColor Red
    exit 1
} else {
    Write-Host "Tim thay WinPmem tai: $winpmemPath" -ForegroundColor Green
}

# Create test directory
$testDir = Join-Path (Get-Location) "test_ram_dump"
if (-not (Test-Path $testDir)) {
    New-Item -ItemType Directory -Path $testDir | Out-Null
}
Write-Host "Thu muc test: $testDir" -ForegroundColor Cyan

# Test output file
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outputFile = Join-Path $testDir "test_memory_$timestamp.raw"
Write-Host "File output se la: $outputFile" -ForegroundColor Cyan

# Test direct command
Write-Host "`nThu chay WinPmem truc tiep..." -ForegroundColor Yellow
$directCmd = @($winpmemPath, "--format", "raw", "--output", $outputFile)
Write-Host "Command: $($directCmd -join ' ')" -ForegroundColor Gray

try {
    Set-Location $testDir
    $result = & $winpmemPath --format raw --output $outputFile 2>&1
    $exitCode = $LASTEXITCODE
    
    Write-Host "Return code: $exitCode" -ForegroundColor Cyan
    if ($result) {
        Write-Host "Output: $result" -ForegroundColor Gray
    }
    
    if ($exitCode -eq 0) {
        Write-Host "WinPmem chay thanh cong truc tiep" -ForegroundColor Green
    } else {
        Write-Host "WinPmem truc tiep that bai" -ForegroundColor Red
    }
    
} catch {
    Write-Host "Exception: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# Wait for file
Write-Host "`nDang cho file xuat hien..." -ForegroundColor Yellow
$elapsed = 0
$maxWait = 60

while ($elapsed -lt $maxWait -and -not (Test-Path $outputFile)) {
    Start-Sleep -Seconds 5
    $elapsed += 5
    Write-Host "Cho $elapsed/$maxWait s..." -ForegroundColor Gray
}

if (Test-Path $outputFile) {
    $fileSize = (Get-Item $outputFile).Length
    $fileSizeMB = [math]::Round($fileSize / 1MB, 2)
    Write-Host "File da tao: $outputFile" -ForegroundColor Green
    Write-Host "Kich thuoc: $fileSizeMB MB" -ForegroundColor Green
    Write-Host "`nTest thanh cong!" -ForegroundColor Green
} else {
    Write-Host "File khong xuat hien sau $maxWait giay" -ForegroundColor Red
    Write-Host "`nTest that bai!" -ForegroundColor Red
} 