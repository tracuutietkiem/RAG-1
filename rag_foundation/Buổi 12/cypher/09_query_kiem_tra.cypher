// ============================================================
// BƯỚC 9 — Query kiểm tra & trực quan hóa Knowledge Graph
// Chạy từng query một trong Neo4j Browser (Query tab)
// ============================================================

// 9.1 — Đếm node theo label  (kỳ vọng: DoiTuongApDung 98, Document 30, NguoiKy 14, LinhVuc 13, CoQuan 4)
MATCH (n)
RETURN labels(n) AS labels, count(*) AS total
ORDER BY total DESC;

// 9.2 — Đếm relationship theo type  (kỳ vọng: AP_DUNG_CHO 113, BAN_HANH_BOI 30, KY_BOI 30,
//        THUOC_LINH_VUC 30, THAM_CHIEU 15, SUA_DOI_BO_SUNG 7, THAY_THE_BOI 1)
MATCH ()-[r]->()
RETURN type(r) AS relationship_type, count(*) AS total
ORDER BY total DESC;

// 9.3 — Xem graph mẫu
MATCH (n)-[r]->(m)
RETURN n, r, m
LIMIT 100;

// 9.4 — Văn bản và người ký
MATCH (d:Document)-[:KY_BOI]->(p:NguoiKy)
RETURN d.so_ky_hieu AS van_ban, p.canonical_name AS nguoi_ky
ORDER BY nguoi_ky;

// 9.5 — Đối tượng áp dụng
MATCH (d:Document)-[:AP_DUNG_CHO]->(o:DoiTuongApDung)
RETURN d.so_ky_hieu AS van_ban, count(o) AS so_doi_tuong
ORDER BY so_doi_tuong DESC;

// 9.6 — Quan hệ Document -> Document (xem dạng graph)
MATCH path=(a:Document)-[:THAM_CHIEU|SUA_DOI_BO_SUNG|THAY_THE_BOI]->(b:Document)
RETURN path
LIMIT 50;

// 9.7 — Chuỗi tham chiếu nhiều bước
MATCH path=(d1:Document)-[:THAM_CHIEU*1..3]->(d2:Document)
RETURN path
LIMIT 20;

// 9.8 — Kiểm tra chiều THAY_THE_BOI (văn bản cũ -> văn bản mới)
MATCH (old:Document)-[r:THAY_THE_BOI]->(new:Document)
RETURN old.so_ky_hieu AS van_ban_cu, new.so_ky_hieu AS van_ban_moi, r.evidence AS evidence;

// 9.9 — Truy vết evidence: mọi quan hệ do LLM tạo ra đều phải có evidence
MATCH ()-[r]->()
WHERE r.method = 'claude_llm'
RETURN type(r) AS loai, count(*) AS so_luong, min(r.confidence) AS conf_thap_nhat, max(r.confidence) AS conf_cao_nhat
ORDER BY so_luong DESC;

// 9.10 — Văn bản nào được nhiều văn bản khác viện dẫn nhất
MATCH (a:Document)-[:THAM_CHIEU]->(b:Document)
RETURN b.so_ky_hieu AS van_ban_duoc_vien_dan, b.title AS ten, count(a) AS so_lan_duoc_vien_dan
ORDER BY so_lan_duoc_vien_dan DESC;

// 9.11 — Toàn cảnh 1 văn bản (thay số hiệu tùy ý)
MATCH (d:Document {so_ky_hieu: '62/2025/TT-NHNN'})-[r]-(n)
RETURN d, r, n;

// ============================================================
// Query dọn dẹp (CHỈ dùng khi cần import lại từ đầu — CẨN THẬN)
// MATCH (n) DETACH DELETE n;
// ============================================================

// ============================================================
// BỔ SUNG — Query nâng cao đã chạy & kiểm chứng trên Neo4j Browser
// ============================================================

// A. Văn bản nào được viện dẫn nhiều nhất (đo tầm quan trọng của văn bản gốc)
//    Kết quả: 46/2010/QH12 (7 lần), 32/2024/QH15 (3), 05/2019/NĐ-CP (2), ...
MATCH (a:Document)-[:THAM_CHIEU]->(b:Document)
RETURN b.so_ky_hieu AS van_ban_duoc_vien_dan, b.title AS ten_van_ban,
       count(a) AS so_lan_duoc_vien_dan
ORDER BY so_lan_duoc_vien_dan DESC;

// B. Toàn cảnh một văn bản (đổi số hiệu tùy nhu cầu tra cứu)
//    Trả về đồ thị hình sao: văn bản + cơ quan ban hành + người ký + lĩnh vực + các văn bản liên quan
MATCH (d:Document {so_ky_hieu: '46/2010/QH12'})-[r]-(n)
RETURN d, r, n;

// C. Chuỗi tham chiếu/sửa đổi nhiều bước (multi-hop) — giá trị cốt lõi của Knowledge Graph
//    Ví dụ kết quả: 44/2011/TT-NHNN -[THAY_THE_BOI]-> 62/2025/TT-NHNN -[THAM_CHIEU]-> 32/2024/QH15
MATCH path = (a:Document)-[:SUA_DOI_BO_SUNG|THAY_THE_BOI|THAM_CHIEU*2..3]->(b:Document)
RETURN [n IN nodes(path) | n.so_ky_hieu] AS chuoi_van_ban,
       [r IN relationships(path) | type(r)] AS loai_quan_he,
       length(path) AS so_buoc
ORDER BY so_buoc DESC
LIMIT 15;

// D. NGHIỆP VỤ — Tra cứu văn bản áp dụng cho TCTD / NHTM kèm tình trạng hiệu lực
MATCH (d:Document)-[:AP_DUNG_CHO]->(o:DoiTuongApDung)
WHERE o.canonical_name IN ['Ngân hàng thương mại','Tổ chức tín dụng',
      'Chi nhánh ngân hàng nước ngoài','Tổ chức tín dụng, chi nhánh ngân hàng nước ngoài']
OPTIONAL MATCH (d)-[:THUOC_LINH_VUC]->(lv:LinhVuc)
RETURN d.so_ky_hieu AS van_ban, d.loai_van_ban AS loai, lv.canonical_name AS linh_vuc,
       d.tinh_trang_hieu_luc AS hieu_luc, collect(DISTINCT o.canonical_name) AS doi_tuong
ORDER BY van_ban;

// E. NGHIỆP VỤ — Cảnh báo văn bản đã bị thay thế nhưng vẫn có thể đang được trích dẫn
MATCH (cu:Document)-[:THAY_THE_BOI]->(moi:Document)
OPTIONAL MATCH (x:Document)-[:THAM_CHIEU]->(cu)
RETURN cu.so_ky_hieu AS van_ban_da_bi_thay_the,
       moi.so_ky_hieu AS van_ban_thay_the,
       collect(x.so_ky_hieu) AS cac_van_ban_con_vien_dan_ban_cu;

// F. Người ký nhiều văn bản nhất
MATCH (d:Document)-[:KY_BOI]->(p:NguoiKy)
RETURN p.canonical_name AS nguoi_ky, count(d) AS so_van_ban,
       collect(d.so_ky_hieu) AS danh_sach
ORDER BY so_van_ban DESC;
