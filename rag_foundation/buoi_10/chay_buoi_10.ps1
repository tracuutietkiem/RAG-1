# =====================================================================
# CHẠY TOÀN BỘ BUỔI 10 — một lệnh duy nhất
# =====================================================================
#
# Cách chạy (mở PowerShell, dán đúng 1 dòng này):
#
#   powershell -ExecutionPolicy Bypass -File "D:\01_CONG_VIEC\phan_mem_tra_cuVB\RAG\rag_foundation\buoi_10\chay_buoi_10.ps1"
#
# Script này KHÔNG xoá gì, KHÔNG sửa dữ liệu Buổi 05-09.
# Mọi output được ghi đồng thời ra màn hình và file log:
#   reports\chay_<timestamp>.log
#
# Script tự DỪNG ngay khi một bước lỗi, in rõ nguyên nhân và cách xử lý,
# thay vì chạy tiếp rồi hỏng dữ liệu ở bước sau.
# =====================================================================

# QUAN TRỌNG — phải là "Continue", KHÔNG được để "Stop".
# Lý do: khi gọi python/pip, các chương trình này in tiến trình và traceback ra
# luồng stderr. Với "Stop", PowerShell coi MỌI dòng stderr là lỗi nghiêm trọng và
# ném exception — kể cả khi đó là kết quả BÌNH THƯỜNG (ví dụ: dò xem torch đã cài
# chưa thì Python báo ModuleNotFoundError, script cần đọc kết quả đó để đi cài).
# Script này kiểm soát lỗi bằng $LASTEXITCODE ở từng bước, chặt chẽ hơn và không
# bị dương tính giả.
$ErrorActionPreference = "Continue"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir

# QUAN TRỌNG — ép Python luôn dùng UTF-8 cho stdin/stdout/stderr.
# Lý do: khi output của python bị pipe qua Tee-Object (như script này làm ở
# mọi bước), Python không còn thấy một console thật nữa nên rơi về bảng mã
# mặc định của hệ thống (cp1252 trên nhiều máy Windows tiếng Việt) thay vì
# UTF-8 — in chữ có dấu ("đã điền", "Kết nối"...) sẽ crash với
# UnicodeEncodeError. Đặt PYTHONUTF8=1 buộc Python 3.7+ luôn dùng UTF-8, bất
# kể console hay pipe (PEP 540).
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

# Đồng thời đặt console PowerShell hiện tại sang UTF-8 để chữ có dấu hiển thị
# đúng trên màn hình (không chỉ tránh crash, mà còn đọc được).
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
} catch {
    # Một số host PowerShell (ISE cũ) không cho đổi OutputEncoding — bỏ qua,
    # PYTHONUTF8 ở trên đã đủ để không crash.
}

$Stamp     = Get-Date -Format "yyyyMMdd_HHmmss"
$ReportDir = Join-Path $ProjectDir "reports"
New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
$LogFile   = Join-Path $ReportDir "chay_$Stamp.log"
$ErrFile   = "D:\01_CONG_VIEC\phan_mem_tra_cuVB\loi_buoi_10_$Stamp.txt"

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
LỖI KHI CHẠY BUỔI 10 — $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

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
Ghi "  BUỔI 10 — Chunking HTML, Embedding tiếng Việt, nạp Neo4j"
Ghi "  Bắt đầu: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Ghi "  Thư mục: $ProjectDir"
Ghi "=============================================================="

# ---------------------------------------------------------------------
# BƯỚC C1 — Virtual environment
# ---------------------------------------------------------------------
Ghi ""
Ghi "[C1] Kiểm tra virtual environment..." "Cyan"

$VenvPy = Join-Path $ProjectDir ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPy)) {
    Ghi "     Chưa có .venv — đang tạo mới..."
    & python -m venv (Join-Path $ProjectDir ".venv")
}

if (-not (Test-Path $VenvPy)) {
    DungLai "Tạo virtual environment" @"
Không tạo được .venv. Nguyên nhân thường gặp: chưa cài Python hoặc Python
chưa nằm trong PATH.

Kiểm tra bằng:  python --version
Nếu báo lỗi, cài Python 3.11+ tại python.org và nhớ tích 'Add to PATH'.
"@
}

$PyVer = & $VenvPy --version 2>&1
Ghi "     OK — $PyVer"

# ---------------------------------------------------------------------
# BƯỚC C2 — torch bản CPU (BẮT BUỘC cài trước requirements)
# ---------------------------------------------------------------------
Ghi ""
Ghi "[C2] Kiểm tra torch (bắt buộc bản CPU)..." "Cyan"

# Dò xem torch đã cài chưa. Nuốt stderr (2>$null) vì nếu CHƯA cài thì Python in
# traceback ra đó — đây là kết quả mong đợi, không phải sự cố cần hiển thị.
$TorchVer = & $VenvPy -c "import torch; print(torch.__version__)" 2>$null
$CoTorch  = ($LASTEXITCODE -eq 0)

if (-not $CoTorch) {
    Ghi "     (chưa thấy torch trong .venv — bình thường ở lần chạy đầu)"
    Ghi "     Chưa có torch — đang cài BẢN CPU (tránh tải ~3GB thư viện CUDA)..."
    Ghi "     Lệnh: pip install torch --index-url https://download.pytorch.org/whl/cpu"
    Ghi "     (bước này tải vài trăm MB, có thể mất 5-15 phút)"
    & $VenvPy -m pip install torch --index-url https://download.pytorch.org/whl/cpu 2>&1 |
        Tee-Object -FilePath $LogFile -Append
    if ($LASTEXITCODE -ne 0) {
        DungLai "Cài torch bản CPU" @"
pip báo lỗi khi cài torch. Kiểm tra kết nối mạng / proxy cơ quan.
Nếu mạng cơ quan chặn, thử lại ở mạng khác rồi chạy lại script này.
"@
    }
    $TorchVer = & $VenvPy -c "import torch; print(torch.__version__)" 2>$null
    if ($LASTEXITCODE -ne 0) {
        DungLai "Kiểm tra torch sau khi cài" @"
Đã chạy lệnh cài torch nhưng vẫn không import được. Chạy tay lệnh sau để xem
lỗi đầy đủ:

  .venv\Scripts\python.exe -c "import torch"
"@
    }
}

Ghi "     torch = $TorchVer"
if ($TorchVer -notmatch "\+cpu") {
    DungLai "Kiểm tra torch bản CPU" @"
torch hiện tại là '$TorchVer' — KHÔNG có hậu tố '+cpu', tức là bản GPU.
Đề bài Buổi 10 yêu cầu rõ chỉ dùng bản CPU.

Gỡ và cài lại bằng:
  .venv\Scripts\python.exe -m pip uninstall -y torch
  .venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu

Rồi chạy lại script này.
"@
}
Ghi "     OK — đúng bản CPU."

# ---------------------------------------------------------------------
# BƯỚC C3 — Các package còn lại
# ---------------------------------------------------------------------
Ghi ""
Ghi "[C3] Cài các package trong requirements.txt..." "Cyan"
& $VenvPy -m pip install -r (Join-Path $ProjectDir "requirements.txt") 2>&1 |
    Tee-Object -FilePath $LogFile -Append
if ($LASTEXITCODE -ne 0) {
    DungLai "Cài requirements.txt" "pip báo lỗi. Xem chi tiết trong log: $LogFile"
}
Ghi "     OK."

# ---------------------------------------------------------------------
# BƯỚC C4 — File .env và mật khẩu Neo4j
# ---------------------------------------------------------------------
Ghi ""
Ghi "[C4] Kiểm tra file .env..." "Cyan"

$EnvFile = Join-Path $ProjectDir ".env"
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $ProjectDir ".env.example") $EnvFile
    Ghi "     Đã tạo .env từ .env.example."
}

$MatKhauDong = Select-String -Path $EnvFile -Pattern "^NEO4J_PASSWORD=(.*)$"
$MatKhau = ""
if ($MatKhauDong) { $MatKhau = $MatKhauDong.Matches[0].Groups[1].Value.Trim() }

if ([string]::IsNullOrWhiteSpace($MatKhau)) {
    Ghi "     NEO4J_PASSWORD đang TRỐNG." "Yellow"
    Ghi ""
    Ghi "     Đây là việc duy nhất script không tự làm được: mật khẩu Neo4j" "Yellow"
    Ghi "     chỉ có anh biết (đặt khi tạo DBMS trong Neo4j Desktop)." "Yellow"
    Ghi ""
    Ghi "     Đang mở file .env để anh điền..." "Yellow"
    Start-Process notepad.exe $EnvFile -Wait
    Ghi "     (đã đóng Notepad, đọc lại .env)"

    $MatKhauDong = Select-String -Path $EnvFile -Pattern "^NEO4J_PASSWORD=(.*)$"
    $MatKhau = ""
    if ($MatKhauDong) { $MatKhau = $MatKhauDong.Matches[0].Groups[1].Value.Trim() }

    if ([string]::IsNullOrWhiteSpace($MatKhau)) {
        DungLai "Điền mật khẩu Neo4j" @"
NEO4J_PASSWORD vẫn trống trong file:
  $EnvFile

Mở file đó, sửa dòng:
  NEO4J_PASSWORD=
thành:
  NEO4J_PASSWORD=<mật khẩu anh đặt khi tạo DBMS trong Neo4j Desktop>

Lưu lại rồi chạy lại script này.
"@
    }
}
Ghi "     OK — mật khẩu đã điền (script không in giá trị mật khẩu)."

# ---------------------------------------------------------------------
# BƯỚC D — Kiểm tra kết nối Neo4j
# ---------------------------------------------------------------------
Ghi ""
Ghi "[D] Kiểm tra kết nối Neo4j..." "Cyan"
& $VenvPy (Join-Path $ProjectDir "check_connection.py") 2>&1 |
    Tee-Object -FilePath $LogFile -Append
if ($LASTEXITCODE -ne 0) {
    DungLai "Kết nối Neo4j" @"
Không kết nối được Neo4j. check_connection.py đã in chẩn đoán cụ thể ở trên.

Kiểm tra theo thứ tự:
  1. Mở Neo4j Desktop, bấm Start, chờ trạng thái Active (chấm xanh).
  2. Đã tạo database 'kb-hops' chưa? Mở Neo4j Browser, chạy nội dung
     file setup_neo4j.cypher.
     - Nếu báo 'Unsupported administration command' (Community Edition):
       sửa .env thành NEO4J_DATABASE=neo4j rồi chạy lại.
  3. Mật khẩu trong .env có đúng không?
"@
}
Ghi "     OK — kết nối thành công."

# ---------------------------------------------------------------------
# BƯỚC E1 — Parse (Bước 1 đề bài)
# ---------------------------------------------------------------------
Ghi ""
Ghi "[E1] Bước 1 — Chunking phân cấp + in mẫu ra console..." "Cyan"
& $VenvPy -m src.pipeline parse --input data\raw_html --sample 25 2>&1 |
    Tee-Object -FilePath $LogFile -Append
if ($LASTEXITCODE -ne 0) {
    DungLai "Bước 1 (parse)" "Xem lỗi ở trên và trong log: $LogFile"
}

# ---------------------------------------------------------------------
# BƯỚC E2 — Embed (Bước 2 đề bài)
# ---------------------------------------------------------------------
Ghi ""
Ghi "[E2] Bước 2 — Tạo vector nhúng (CPU)..." "Cyan"
Ghi "     Lần đầu sẽ tải model từ HuggingFace (vài trăm MB), hãy kiên nhẫn."
& $VenvPy -m src.pipeline embed --input data\raw_html 2>&1 |
    Tee-Object -FilePath $LogFile -Append
if ($LASTEXITCODE -ne 0) {
    DungLai "Bước 2 (embed)" @"
Lỗi khi nhúng vector. Nguyên nhân thường gặp:
  - Mạng chặn huggingface.co (không tải được model).
  - Thiếu RAM khi nạp model.
Xem chi tiết trong log: $LogFile
"@
}

# ---------------------------------------------------------------------
# BƯỚC E3 — Load vào Neo4j (Bước 3+4 đề bài)
# ---------------------------------------------------------------------
Ghi ""
Ghi "[E3] Bước 3+4 — Nạp đồ thị vào Neo4j..." "Cyan"
& $VenvPy -m src.pipeline load --input data\raw_html 2>&1 |
    Tee-Object -FilePath $LogFile -Append
if ($LASTEXITCODE -ne 0) {
    DungLai "Bước 3+4 (load)" @"
Lỗi khi nạp Neo4j. Lưu ý: việc nạp dùng MERGE nên chạy lại KHÔNG tạo
node trùng — anh có thể sửa lỗi rồi chạy lại script an toàn.
Xem chi tiết trong log: $LogFile
"@
}

# ---------------------------------------------------------------------
# BƯỚC E4 — Xác minh (Bước 5 đề bài)
# ---------------------------------------------------------------------
Ghi ""
Ghi "[E4] Bước 5 — Xác minh sau khi nạp..." "Cyan"
& $VenvPy -m src.pipeline verify-load 2>&1 |
    Tee-Object -FilePath $LogFile -Append

Ghi ""
Ghi "=============================================================="  "Green"
Ghi "  HOÀN TẤT — $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"           "Green"
Ghi "=============================================================="  "Green"
Ghi ""
Ghi "Log đầy đủ    : $LogFile"
Ghi "Báo cáo verify: $ReportDir\verify_*.json"
Ghi ""
Ghi "LƯU Ý VỀ SỐ LIỆU NGHIỆM THU:" "Yellow"
Ghi "  Đề bài giả định 15 Document / 8 quan hệ. Dữ liệu hiện có trong repo"
Ghi "  chỉ có 1 văn bản nguồn nên ra 4 Document / 3 quan hệ CAN_CU."
Ghi "  verify-load in [LỆCH] là ĐÚNG HÀNH VI — không tự bịa node cho khớp."
Ghi "  Muốn đạt 15/8: bổ sung đủ file HTML vào data\raw_html\ và khai báo"
Ghi "  quan hệ trong data\doc_relationships.json. Code không cần sửa."
Ghi ""
Ghi "Kiểm tra trực quan: mở Neo4j Browser, chọn database kb-hops, chạy:"
Ghi "  MATCH (d:Document) RETURN d.doc_id, d.doc_type, d.title;"
Ghi "  MATCH (a:Document)-[r]->(b:Document) RETURN a.doc_id, type(r), b.doc_id;"
