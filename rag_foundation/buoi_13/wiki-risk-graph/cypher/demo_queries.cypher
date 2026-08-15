// ============================================================
// Demo query cho Wiki Risk Graph
// Chay lan luot tung khoi trong Neo4j Browser / cypher-shell.
// Cac cho co $param la query tham so hoa, thay gia tri thuc te truoc khi chay
// (trong Neo4j Browser dung :param riskId => 'RR-001' truoc khi chay).
// ============================================================

// A. Xem toan bo graph (gioi han 200 node de tranh qua tai giao dien)
MATCH (n)-[r]->(m)
RETURN n, r, m
LIMIT 200;


// B. Tim kiem soat giam thieu mot rui ro cu the
// :param riskId => 'RR-001'
MATCH (ks:KiemSoat)-[m:MITIGATES]->(rr:RuiRo {id: $riskId})
RETURN ks.id AS kiemsoat_id, ks.name AS kiemsoat_name,
       m.verification_status AS quan_he_verification_status,
       m.evidence_quote AS bang_chung
ORDER BY ks.id;


// C. Tim su kien da ghi nhan cua mot rui ro cu the
// :param riskId => 'RR-001'
MATCH (rr:RuiRo {id: $riskId})-[o:OBSERVED_AS]->(sk:SuKienRuiRo)
RETURN sk.id AS su_kien_id, sk.description AS mo_ta,
       sk.severity AS muc_do, sk.loss_amount_vnd AS ton_that_vnd,
       o.verification_status AS quan_he_verification_status
ORDER BY sk.occurred_at;


// D. Tim duong day du: KiemSoat -> RuiRo -> SuKienRuiRo
MATCH path = (ks:KiemSoat)-[:MITIGATES]->(rr:RuiRo)-[:OBSERVED_AS]->(sk:SuKienRuiRo)
RETURN ks.id AS kiemsoat_id, ks.name AS kiemsoat_name,
       rr.id AS ruiro_id, rr.name AS ruiro_name,
       sk.id AS sukien_id, sk.description AS sukien_mota
ORDER BY rr.id
LIMIT 50;


// E. Tim rui ro chua co kiem soat nao (KHONG duoc dung de bia them quan he,
//    chi de phat hien khoang trong du lieu can bo sung)
MATCH (rr:RuiRo)
WHERE NOT ( ()-[:MITIGATES]->(rr) )
RETURN rr.id AS ruiro_id, rr.name AS ruiro_name, rr.category AS category
ORDER BY rr.id;


// F. Tim relation (MITIGATES hoac OBSERVED_AS) chua o trang thai VERIFIED
MATCH (a)-[r]->(b)
WHERE type(r) IN ['MITIGATES', 'OBSERVED_AS'] AND r.verification_status <> 'VERIFIED'
RETURN a.id AS nguon, type(r) AS quan_he, b.id AS dich,
       r.verification_status AS trang_thai, r.confidence AS do_tin_cay
ORDER BY r.verification_status, a.id;
