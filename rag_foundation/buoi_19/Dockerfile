# Buoi 19 - Dockerfile cho container "agribank-ai-app" (Streamlit + RAG Engines).
#
# Build context la CHINH thu muc buoi_19/ (khong can COPY cheo sang cac buoi
# khac trong image). Code/du lieu TAI SU DUNG cua buoi_14/17/18 duoc gan qua
# BIND MOUNT read-only trong docker-compose.yml (../buoi_14, ../buoi_17,
# ../buoi_18 -> /buoi_14, /buoi_17, /buoi_18), dung CHINH XAC cach cac script
# Python trong scripts/ da resolve duong dan tuong doi ("../buoi_14" tinh tu
# BASE_DIR=/app). Nho vay: (1) KHONG bao gio bake .env/API key cua cac buoi
# khac vao Docker image, (2) KHONG nhan ban du lieu lon vao image, (3) sua
# code o buoi_14/17/18 tren host se phan anh ngay khi container restart,
# dung tinh than "tai su dung, khong sao chep" xuyen suot du an.
FROM python:3.10-slim

# UTF-8 (bat buoc vi toan bo du lieu/prompt la tieng Viet co dau) + khong
# buffer stdout/stderr (log Docker hien thi ngay lap tuc).
ENV LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8

WORKDIR /app

# Cai dependency truoc (tan dung Docker layer cache).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy toan bo ma nguon Buoi 19. .dockerignore dam bao .env/outputs/__pycache__
# KHONG lot vao image.
COPY . .

EXPOSE 8501

# Healthcheck: Streamlit co endpoint /_stcore/health mac dinh.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=3)" || exit 1

CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501"]
