// =========================================================================
// SETUP VECTOR INDEX CHO BUỔI 11
// =========================================================================
//
// Chạy trong Neo4j Browser, ĐÃ CHUYỂN sang database kb-hops trước
// (dropdown góc trên, hoặc gõ :use kb-hops).
//
// Chỉ cần chạy MỘT LẦN. `python -m src.pipeline setup-index` cũng chạy đúng
// lệnh này — dùng cách nào cũng được, không cần làm cả hai.
// =========================================================================

:use kb-hops

CREATE VECTOR INDEX chunk_embedding_index IF NOT EXISTS
FOR (c:Chunk) ON c.embedding
OPTIONS {indexConfig: {
  `vector.dimensions`: 384,
  `vector.similarity_function`: 'cosine'
}};

// Kiểm tra đã tạo và ONLINE:
SHOW INDEXES YIELD name, state, type WHERE name = 'chunk_embedding_index';
