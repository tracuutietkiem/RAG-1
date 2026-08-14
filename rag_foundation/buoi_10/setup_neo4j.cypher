// =========================================================================
// SETUP NEO4J CHO BUỔI 10
// =========================================================================
//
// ĐỌC KỸ TRƯỚC KHI CHẠY — giới hạn về phiên bản:
//
// Lệnh CREATE DATABASE là tính năng CHỈ CÓ TRÊN NEO4J ENTERPRISE EDITION.
// Neo4j Community Edition chỉ cho phép đúng MỘT database chuẩn (tên mặc định
// là `neo4j`), nên `CREATE DATABASE kb-hops` sẽ báo lỗi.
//
// TIN TỐT: Neo4j Desktop đi kèm sẵn Developer License của Enterprise Edition
// (dùng cho cá nhân, trên một máy), nên nếu anh cài qua Neo4j Desktop 2.0 thì
// lệnh dưới đây chạy được bình thường.
//
// Nếu anh cài Neo4j Community server đứng riêng (không qua Desktop) và gặp lỗi
// "Unsupported administration command", hãy dùng PHƯƠNG ÁN B ở cuối file.
// =========================================================================


// -------------------------------------------------------------------------
// PHƯƠNG ÁN A — có Enterprise (Neo4j Desktop). Chạy ở database `system`.
// -------------------------------------------------------------------------

// Bước 1: tạo database kb-hops (chỉ chạy một lần).
CREATE DATABASE `kb-hops` IF NOT EXISTS;

// Bước 2: xác nhận đã online.
SHOW DATABASES;


// -------------------------------------------------------------------------
// Bước 3: RÀNG BUỘC DUY NHẤT
// PHẢI chạy khi đang ở TRONG database `kb-hops`.
// Đổi database bằng dropdown góc trên Neo4j Browser, hoặc gõ:  :use kb-hops
// -------------------------------------------------------------------------

// Hai lệnh này giúp việc nạp lại (MERGE) không sinh node trùng.
// pipeline.py cũng tự chạy chúng — chạy tay ở đây chỉ để kiểm tra trước.
CREATE CONSTRAINT document_doc_id IF NOT EXISTS
FOR (d:Document) REQUIRE d.doc_id IS UNIQUE;

CREATE CONSTRAINT chunk_chunk_id IF NOT EXISTS
FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE;

// Kiểm tra constraint đã tạo:
SHOW CONSTRAINTS;


// -------------------------------------------------------------------------
// PHƯƠNG ÁN B — chỉ có Community Edition (không tạo được database mới)
// -------------------------------------------------------------------------
//
// Bỏ qua Bước 1 và 2. Dùng luôn database mặc định `neo4j`, và sửa file .env:
//
//     NEO4J_DATABASE=neo4j
//
// rồi chạy Bước 3 ở trên trong database `neo4j`.
//
// Đánh đổi: đồ thị Buổi 10 sẽ nằm chung database với mọi dữ liệu khác trong
// instance đó. Chỉ nên làm vậy nếu instance này dành riêng cho bài thực hành.


// -------------------------------------------------------------------------
// LỆNH DỌN DẸP (chỉ dùng khi cần làm lại từ đầu)
// -------------------------------------------------------------------------
//
// CẢNH BÁO: lệnh dưới xoá sạch đồ thị, KHÔNG khôi phục được.
// Bỏ dấu // ở đầu dòng để chạy, và chắc chắn đang đứng đúng database.
//
// MATCH (n) DETACH DELETE n;
