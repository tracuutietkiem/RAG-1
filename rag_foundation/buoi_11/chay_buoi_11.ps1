# =====================================================================
# CHẠY TOÀN BỘ BUỔI 11 — một lệnh duy nhất
# =====================================================================
#
# Cách chạy (mở PowerShell, dán đúng 1 dòng này):
#
#   powershell -ExecutionPolicy Bypass -File "D:\01_CONG_VIEC\phan_mem_tra_cuVB\RAG\rag_foundation\buoi_11\chay_buoi_11.ps1"
#
# Rút kinh nghiệm từ Buổi 10:
#   - $ErrorActionPreference PHẢI là "Continue", không phải "Stop" — vì output
#     của python/pip khi bị pipe qua Tee-Object đi qua stderr, PowerShell với
#     "Stop" sẽ coi mọi dòng đó là lỗi nghiêm trọng và thoát ngay dù không có
#     gì sai.
#   - PYTHONUTF8=1 bắt buộc đặt trước khi gọi python — nếu không, in tiếng
#     Việt có dấu qua pipe sẽ crash UnicodeEncodeError trên console cp1252.
# =====================================================================

$ErrorActionPreference = "Continue"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch {}

$Stamp     = Get-Date -Format "yyyyMMdd_HHmmss"
$ReportDir = Join-Path $ProjectDir "reports"
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
$LogFile   = Join-Path $ReportDir "chay_$Stamp.log"
$ErrFile   = "D:\01_CONG_VIEC\phan_mem_tra_cuVB\loi_buoi_11_$Stamp.txt"

function Ghi([string]$msg, [string]$mau = "White") {
    Write-Host $msg -ForegroundColor $mau
    Add-Content -Path $LogFile -Value $msg -Encoding UTF8
}

function DungLai([string]$buoc, [string]$cachXuLy) {
    Ghi ""
    Ghi "==============================================================" "Red"
    Ghi "  DỪNG tại: $buoc" "Red"
    Ghi "==============================================================" "Red"
    Ghi ""
    Ghi "CÁCH XỬ LÝ:" "Yellow"
    Ghi $cachXuLy "Yellow"
    Ghi ""
    Ghi "Log đầy đủ: $LogFile"

    $noiDung = @"
LỖI KHI CHẠY BUỔI 11 — $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

Bước lỗi: $buoc

Cách xử lý đề xuất:
$cachXuLy

Log đầy đủ: $LogFile
"@
    Set-Content -Path $ErrFile -Value $noiDung -Encoding UTF8
    Ghi "Đã ghi nhật ký lỗi: $ErrFile" "Yellow"
    exit 1
}

Ghi "=============================================================="
Ghi "  BUỔI 11 — Multi-hop Graph RAG + Hỏi đáp bằng Gemini API"
Ghi "  Bắt đầu: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Ghi "  Thư mục: $ProjectDir"
Ghi "=============================================================="

# ---------------------------------------------------------------------
# BƯỚC A1 — Virtual environment
# ---------------------------------------------------------------------
Ghi ""
Ghi "[A1] Kiểm tra virtual environment..." "Cyan"

$VenvPy = Join-Path $ProjectDir ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPy)) {
    Ghi "     Chưa có .venv — đang tạo mới..."
    & python -m venv (Join-Path $ProjectDir ".venv")
}

if (-not (Test-Path $VenvPy)) {
    DungLai "Tạo virtual environment" @"
Không tạo được .venv. Kiểm tra: python --version
Nếu báo lỗi, cài Python 3.11+ tại python.org, tích 'Add to PATH'.
"@
}
$PyVer = & $VenvPy --version 2>&1
Ghi "     OK — $PyVer"

# ---------------------------------------------------------------------
# BƯỚC A2 — torch bản CPU
# ---------------------------------------------------------------------
Ghi ""
Ghi "[A2] Kiểm tra torch (bắt buộc bản CPU)..." "Cyan"

$TorchVer = & $VenvPy -c "import torch; print(torch.__version__)" 2>$null
if ($LASTEXITCODE -ne 0) {
    Ghi "     (chưa thấy torch trong .venv — bình thường ở lần chạy đầu)"
    Ghi "     Đang cài BẢN CPU (tránh tải ~3GB thư viện CUDA)..."
    & $VenvPy -m pip install torch --index-url https://download.pytorch.org/whl/cpu 2>&1 |
        Tee-Object -FilePath $LogFile -Append
    if ($LASTEXITCODE -ne 0) {
        DungLai "Cài torch bản CPU" "pip báo lỗi. Kiểm tra kết nối mạng / proxy."
    }
    $TorchVer = & $VenvPy -c "import torch; print(torch.__version__)" 2>$null
    if ($LASTEXITCODE -ne 0) {
        DungLai "Kiểm tra torch sau khi cài" "Đã cài nhưng vẫn không import được. Chạy tay: .venv\Scripts\python.exe -c ""import torch"""
    }
}
Ghi "     torch = $TorchVer"
if ($TorchVer -notmatch "\+cpu") {
    DungLai "Kiểm tra torch bản CPU" @"
torch hiện tại là '$TorchVer' — không phải bản CPU. Gỡ và cài lại:
  .venv\Scripts\python.exe -m pip uninstall -y torch
  .venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
"@
}
Ghi "     OK — đúng bản CPU."

# ---------------------------------------------------------------------
# BƯỚC A3 — requirements.txt
# ---------------------------------------------------------------------
Ghi ""
Ghi "[A3] Cài các package trong requirements.txt..." "Cyan"
& $VenvPy -m pip install -r (Join-Path $ProjectDir "requirements.txt") 2>&1 |
    Tee-Object -FilePath $LogFile -Append
if ($LASTEXITCODE -ne 0) {
    DungLai "Cài requirements.txt" "pip báo lỗi. Xem chi tiết trong log: $LogFile"
}
Ghi "     OK."

# ---------------------------------------------------------------------
# BƯỚC A4 — .env: mật khẩu Neo4j + GEMINI_API_KEY
# ---------------------------------------------------------------------
Ghi ""
Ghi "[A4] Kiểm tra file .env..." "Cyan"

$EnvFile = Join-Path $ProjectDir ".env"
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $ProjectDir ".env.example") $EnvFile
    Ghi "     Đã tạo .env từ .env.example."
}

function DocGiaTri([string]$tenBien, [string]$duongDanFile) {
    $dong = Select-String -Path $duongDanFile -Pattern "^$tenBien=(.*)$"
    if ($dong) { return $dong.Matches[0].Groups[1].Value.Trim() }
    return ""
}

$matKhau = DocGiaTri "NEO4J_PASSWORD" $EnvFile
$geminiKey = DocGiaTri "GEMINI_API_KEY" $EnvFile

if ([string]::IsNullOrWhiteSpace($matKhau) -or [string]::IsNullOrWhiteSpace($geminiKey)) {
    Ghi "     NEO4J_PASSWORD hoặc GEMINI_API_KEY đang trống." "Yellow"
    Ghi "     Đang mở .env để anh điền (mật khẩu Neo4j giống Buổi 10; API key lấy" "Yellow"
    Ghi "     tại https://aistudio.google.com/apikey)..." "Yellow"
    Start-Process notepad.exe $EnvFile -Wait
    Ghi "     (đã đóng Notepad, đọc lại .env)"

    $matKhau = DocGiaTri "NEO4J_PASSWORD" $EnvFile
    $geminiKey = DocGiaTri "GEMINI_API_KEY" $EnvFile

    if ([string]::IsNullOrWhiteSpace($matKhau)) {
        DungLai "Điền NEO4J_PASSWORD" "Mở $EnvFile, điền NEO4J_PASSWORD, lưu lại, chạy lại script."
    }
    if ([string]::IsNullOrWhiteSpace($geminiKey)) {
        DungLai "Điền GEMINI_API_KEY" "Mở $EnvFile, điền GEMINI_API_KEY (lấy tại Google AI Studio), lưu lại, chạy lại script."
    }
}
Ghi "     OK — cả hai giá trị đã điền (script không in giá trị thật)."

# ---------------------------------------------------------------------
# BƯỚC B — Kiểm tra kết nối Neo4j
# ---------------------------------------------------------------------
Ghi ""
Ghi "[B] Kiểm tra kết nối Neo4j..." "Cyan"
& $VenvPy (Join-Path $ProjectDir "check_connection.py") 2>&1 |
    Tee-Object -FilePath $LogFile -Append
if ($LASTEXITCODE -ne 0) {
    DungLai "Kết nối Neo4j" @"
Không kết nối được Neo4j. Kiểm tra:
  1. Neo4j Desktop đã Start DBMS chưa? (trạng thái Active)
  2. Database 'kb-hops' đã tạo và nạp dữ liệu ở Buổi 10 chưa?
  3. Mật khẩu trong .env đúng chưa?
"@
}
Ghi "     OK — kết nối thành công."

# ---------------------------------------------------------------------
# BƯỚC C — Tạo vector index
# ---------------------------------------------------------------------
Ghi ""
Ghi "[C] Tạo/kiểm tra vector index..." "Cyan"
& $VenvPy -m src.pipeline setup-index 2>&1 | Tee-Object -FilePath $LogFile -Append
if ($LASTEXITCODE -ne 0) {
    DungLai "Tạo vector index" "Xem lỗi ở trên. Có thể Neo4j chưa hỗ trợ vector index (cần bản 5.13+)."
}

# ---------------------------------------------------------------------
# BƯỚC D — Chạy so sánh 5 câu hỏi x 3 mức hops
# ---------------------------------------------------------------------
Ghi ""
Ghi "[D] Chạy compare (5 câu hỏi x hops=0,1,2 — gọi Gemini API thật)..." "Cyan"
Ghi "     Có thể mất vài phút tuỳ tốc độ mạng và độ trễ Gemini API."
& $VenvPy -m src.pipeline compare 2>&1 | Tee-Object -FilePath $LogFile -Append
if ($LASTEXITCODE -ne 0) {
    DungLai "Chạy compare" @"
Lỗi khi gọi Gemini API hoặc truy vấn Neo4j. Nguyên nhân thường gặp:
  - GEMINI_API_KEY sai hoặc hết quota.
  - Mất kết nối mạng.
Xem chi tiết trong log: $LogFile
"@
}

Ghi ""
Ghi "=============================================================="  "Green"
Ghi "  HOÀN TẤT — $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"           "Green"
Ghi "=============================================================="  "Green"
Ghi ""
Ghi "Log đầy đủ        : $LogFile"
Ghi "Báo cáo so sánh    : reports\qa_comparison.md"
Ghi ""
Ghi "LƯU Ý: với dữ liệu hiện có (4 Document, 3 quan hệ CAN_CU), chỉ Câu hỏi 4"
Ghi "trong 5 câu mẫu có đủ ngữ cảnh để trả lời — 4 câu còn lại trả lời 'không"
Ghi "có đủ thông tin' là ĐÚNG, không phải lỗi. Xem SPEC_buoi_11.md mục 6."
