// ============================================================================
// Mini Knowledge Graph - Buoi 14
// Ontology MVP:  (:VanBan)-[:CONTAINS]->(:DieuKhoan)-[:NEXT]->(:DieuKhoan)
// Quan he van ban - van ban lay THAT tu relationships.csv.
//
// MOI node/relationship cua bai nay deu co  lab_session = "buoi_14"
// -> tach hoan toan voi du lieu cac buoi truoc trong cung database.
//
// TUYET DOI KHONG chay:  MATCH (n) DETACH DELETE n
// ============================================================================

// ---- Rang buoc duy nhat theo id ----
CREATE CONSTRAINT vanban_id_unique IF NOT EXISTS
FOR (n:VanBan) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT dieukhoan_id_unique IF NOT EXISTS
FOR (n:DieuKhoan) REQUIRE n.id IS UNIQUE;

// ---- Index ho tro loc theo buoi hoc va tra cuu ----
CREATE INDEX vanban_lab_session IF NOT EXISTS
FOR (n:VanBan) ON (n.lab_session);

CREATE INDEX dieukhoan_lab_session IF NOT EXISTS
FOR (n:DieuKhoan) ON (n.lab_session);

CREATE INDEX dieukhoan_document_id IF NOT EXISTS
FOR (n:DieuKhoan) ON (n.document_id);

CREATE INDEX vanban_so_ky_hieu IF NOT EXISTS
FOR (n:VanBan) ON (n.so_ky_hieu);

// ---- Rang buoc cho cac node thuc the phu (chi tao khi chay voi --with-entities) ----
CREATE CONSTRAINT nguoiky_id_unique IF NOT EXISTS
FOR (n:NguoiKy) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT coquan_id_unique IF NOT EXISTS
FOR (n:CoQuan) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT linhvuc_id_unique IF NOT EXISTS
FOR (n:LinhVuc) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT doituong_id_unique IF NOT EXISTS
FOR (n:DoiTuongApDung) REQUIRE n.id IS UNIQUE;
