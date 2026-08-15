// ============================================================
// Schema cho Wiki Risk Graph trong Neo4j
// Node toi thieu: RuiRo, KiemSoat, SuKienRuiRo
// Edge: (KiemSoat)-[MITIGATES]->(RuiRo), (RuiRo)-[OBSERVED_AS]->(SuKienRuiRo)
// Dung id lam khoa duy nhat cho tung loai node.
// ============================================================

// --- Rang buoc duy nhat theo id (dam bao MERGE khong tao duplicate) ---
CREATE CONSTRAINT ruiro_id_unique IF NOT EXISTS
FOR (n:RuiRo) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT kiemsoat_id_unique IF NOT EXISTS
FOR (n:KiemSoat) REQUIRE n.id IS UNIQUE;

CREATE CONSTRAINT sukien_id_unique IF NOT EXISTS
FOR (n:SuKienRuiRo) REQUIRE n.id IS UNIQUE;

// --- Index ho tro tra cuu theo verification_status (dung cho demo query F) ---
CREATE INDEX ruiro_verification_status IF NOT EXISTS
FOR (n:RuiRo) ON (n.verification_status);

CREATE INDEX kiemsoat_verification_status IF NOT EXISTS
FOR (n:KiemSoat) ON (n.verification_status);
