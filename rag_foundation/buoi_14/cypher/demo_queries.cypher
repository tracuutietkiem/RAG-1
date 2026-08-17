// ============================================================================
// Demo queries - Mini Knowledge Graph Buoi 14
// Chay tung khoi trong Neo4j Browser / Query.
// Moi query deu loc lab_session = "buoi_14" -> khong dung toi du lieu buoi truoc.
// ============================================================================

// ---------------------------------------------------------------- Query A
// Xem graph Buoi 14 (gioi han 100 quan he cho de nhin)
MATCH (n {lab_session: "buoi_14"})-[r]->(m {lab_session: "buoi_14"})
RETURN n, r, m
LIMIT 100;


// ---------------------------------------------------------------- Query B
// Tu van ban toi dieu khoan
MATCH (v:VanBan {lab_session: "buoi_14"})-[:CONTAINS]->(d:DieuKhoan)
RETURN v.so_ky_hieu AS van_ban, v.title AS ten_van_ban,
       d.id AS dieu_khoan_id, d.article AS dieu, d.clause AS khoan
ORDER BY v.so_ky_hieu, toInteger(coalesce(d.article, "0"))
LIMIT 50;


// ---------------------------------------------------------------- Query C
// Chuoi dieu khoan lien tiep: DieuKhoan -NEXT-> DieuKhoan -NEXT-> DieuKhoan
MATCH path = (a:DieuKhoan {lab_session: "buoi_14"})-[:NEXT]->
             (b:DieuKhoan)-[:NEXT]->(c:DieuKhoan)
RETURN a.so_ky_hieu AS van_ban,
       a.id AS dieu_1, b.id AS dieu_2, c.id AS dieu_3
LIMIT 25;

// Bien the truc quan hon - tra ve path de Browser ve duoc do thi
MATCH path = (a:DieuKhoan {lab_session: "buoi_14"})-[:NEXT*1..4]->(b:DieuKhoan)
WHERE a.article = "1"
RETURN path
LIMIT 10;


// ---------------------------------------------------------------- Query D
// Quan he giua cac VAN BAN - CHI cac relationship_type co that trong
// relationships.csv (THAM_CHIEU, SUA_DOI_BO_SUNG, THAY_THE_BOI).
MATCH (a:VanBan {lab_session: "buoi_14"})-[r]->(b:VanBan)
RETURN a.so_ky_hieu AS tu_van_ban,
       type(r)      AS quan_he,
       b.so_ky_hieu AS toi_van_ban,
       r.method     AS nguon_suy_ra,
       r.confidence AS do_tin_cay,
       r.evidence   AS bang_chung
ORDER BY quan_he, tu_van_ban;

// Dem theo loai quan he van ban - van ban
MATCH (a:VanBan {lab_session: "buoi_14"})-[r]->(b:VanBan)
RETURN type(r) AS quan_he, count(*) AS so_luong
ORDER BY so_luong DESC;


// ---------------------------------------------------------------- Query E
// Node khong co lien ket nao (kiem tra chat luong graph)
MATCH (n {lab_session: "buoi_14"})
WHERE NOT (n)--()
RETURN labels(n)[0] AS loai, n.id AS id, count(*) AS so_luong
ORDER BY loai;

// Van ban khong co dieu khoan nao (dau hieu parse HTML that bai)
MATCH (v:VanBan {lab_session: "buoi_14"})
WHERE NOT (v)-[:CONTAINS]->(:DieuKhoan)
RETURN v.so_ky_hieu AS van_ban_khong_co_dieu_khoan, v.title AS ten;


// ---------------------------------------------------------------- Tien ich
// Dem node/quan he cua rieng Buoi 14
MATCH (n {lab_session: "buoi_14"})
RETURN labels(n)[0] AS loai, count(*) AS so_luong
ORDER BY so_luong DESC;

MATCH ({lab_session: "buoi_14"})-[r]->()
RETURN type(r) AS quan_he, count(*) AS so_luong
ORDER BY so_luong DESC;

// Graph hints cho mot chunk cu the (dung trong app.py / query_demo.py)
// :param chunkId => "166170_D136K2_215"
MATCH (d:DieuKhoan {id: $chunkId, lab_session: "buoi_14"})
OPTIONAL MATCH (v:VanBan)-[:CONTAINS]->(d)
OPTIONAL MATCH (v)-[r]->(other:VanBan)
RETURN d.id AS chunk_id, v.so_ky_hieu AS van_ban,
       collect(DISTINCT type(r) + " -> " + other.so_ky_hieu) AS quan_he_van_ban;


// ---------------------------------------------------------------- DON DEP
// CHI dung khi can lam sach RIENG du lieu Buoi 14. Phai bao truoc cho nguoi dung.
// KHONG BAO GIO chay:  MATCH (n) DETACH DELETE n
//
// MATCH (n {lab_session: "buoi_14"}) DETACH DELETE n;
