# Review Buổi 11 — Đối chiếu code với buoi_11.md và SPEC_buoi_11.md

## 1. Đã chạy thật (2026-08-12, 22:22)

`chay_buoi_11.ps1` chạy hết `setup-index` → `compare` (5 câu hỏi × hops 0/1/2,
gọi Gemini API thật), sinh `reports/qa_comparison.md`. Không lỗi runtime,
script tới khung "HOÀN TẤT".

## 2. Lỗi thật phát hiện sau khi đọc báo cáo (đã sửa)

**Mọi dòng nguồn trong `qa_comparison.md` đều ghi `doc_id=None`.**

Nguyên nhân: `vector_search()` trong `graph_search.py` đọc thẳng
`node.doc_id` từ Chunk trả về bởi vector index. Nhưng theo đúng schema đã nạp
ở Buổi 10 (`neo4j_loader.upsert_chunk`), **node `(:Chunk)` không hề có thuộc
tính `doc_id`** — chỉ Chunk gốc (level cao nhất) mới nối `[:PART_OF]` thẳng
tới Document; Chunk con biết văn bản của mình gián tiếp qua chuỗi
`[:PARENT_OF]` leo lên tới gốc. Đọc `node.doc_id` luôn ra `NULL`.

**Hệ quả nghiêm trọng hơn:** vì `doc_id` là `None`, `search_context()` gom
`doc_ids_seen = {None}`, khiến `neighbor_documents()` chạy
`MATCH (start:Document {doc_id: None})` — không khớp Document nào — nên
**multi-hop hoàn toàn không hoạt động** dù không báo lỗi gì. Đây chính là lý
do kết quả hops=0/1/2 trong bản chạy đầu **giống hệt nhau ở cả 5 câu hỏi**
(có thể thấy rõ trong log: "5 chunk ngữ cảnh" ở cả ba mức hops, mọi câu hỏi).

**Đã sửa:** `vector_search()` nay truy ngược từ Chunk khớp lên Chunk gốc
(`MATCH (top:Chunk)-[:PARENT_OF*0..]->(node) WHERE NOT ()-[:PARENT_OF]->(top)`)
rồi mới lấy `d.doc_id AS doc_id` từ `(top)-[:PART_OF]->(d:Document)`. Đã cập
nhật SPEC_buoi_11.md mục 4 khớp với code sửa.

**Đã xác nhận bằng lần chạy lại thật (22:25:40):** mọi dòng nguồn trong
`qa_comparison.md` nay hiển thị đúng `doc_id=41/2016/TT-NHNN` thay vì `None`.
Bug đã sửa dứt điểm.

**Quan sát thêm sau khi sửa:** nguồn ở hops=0/1/2 vẫn giống hệt nhau (vẫn 5
chunk, đều từ `41/2016/TT-NHNN`) — đây KHÔNG phải dấu hiệu multi-hop còn lỗi,
mà đúng như dự đoán ở mục 4: `neighbor_documents()` nay tìm đúng 3 Document
lân cận qua `CAN_CU` (`46/2010/QH12`, `47/2010/QH12`, `156/2013/NĐ-CP`), nhưng
cả 3 đều là node stub từ Buổi 10 (`has_chunks: false`, không có Chunk nào) nên
`chunks_for_document_by_similarity` trả về rỗng cho chúng — multi-hop "tìm
đúng đường" nhưng không có gì để mượn thêm. Muốn thấy multi-hop thực sự đổi
kết quả, cần nạp toàn văn 3 văn bản đó vào Buổi 10 trước.

## 3. Đối chiếu nội dung câu trả lời với SPEC mục 6 (PASS)

Dù multi-hop bị lỗi ở lần chạy đầu, phần quan trọng nhất — **không bịa câu trả
lời** — đã đúng như thiết kế:

| Câu hỏi | Kỳ vọng (SPEC mục 6) | Kết quả thật |
|---|---|---|
| 1 (Nghị định 46/2023/NĐ-CP) | Không đủ thông tin | ĐÚNG — Gemini từ chối trả lời cả 3 mức hops |
| 2 (VBHN 52/VBHN-NHNN) | Không đủ thông tin | ĐÚNG |
| 3 (TT 01/2025/TT-NHNN) | Không đủ thông tin | ĐÚNG |
| 4 (TT 41/2016/TT-NHNN căn cứ luật nào) | Có dữ liệu nhưng ngữ cảnh vector-search tình cờ không trúng đoạn "Căn cứ..." | Gemini trả lời trung thực "không đủ thông tin" thay vì suy đoán — xem mục 4 |
| 5 (TT về giao nhận tiền mặt) | Không đủ thông tin | ĐÚNG |

Không có trường hợp nào Gemini bịa số hiệu văn bản hay nội dung không có
trong ngữ cảnh — đạt đúng yêu cầu Bước 3 của đề bài.

## 4. Giới hạn thật của Câu hỏi 4 (không phải lỗi code, cần nói rõ)

Câu hỏi 4 lẽ ra khớp được (Thông tư 41/2016/TT-NHNN toàn văn có sẵn, 3 quan hệ
`CAN_CU` cũng có sẵn), nhưng cả 5 chunk top-k trực tiếp đều là các đoạn ở phần
mở đầu (level `doan`, điểm tương đồng ~0.90 nhưng là các dòng tiêu đề/thể thức
văn bản, KHÔNG phải đoạn "Căn cứ Luật..." thật) — nên Gemini đúng khi nói
"không đủ thông tin" thay vì đoán. Đây là giới hạn của top-5 vector search
trên một câu hỏi khá cụ thể, có hai hướng khắc phục (không bắt buộc phải làm
ngay, ghi nhận cho lần sau):

- Tăng `top_k_direct` (ví dụ 8–10) để nhiều khả năng vét trúng đoạn "Căn cứ...".
- Sau khi sửa lỗi `doc_id` ở mục 2, multi-hop từ hop=1 sẽ tự động kéo thêm
  ngữ cảnh từ 3 Document liên quan qua `CAN_CU` — nhưng 3 Document đó hiện là
  **node stub, chưa nạp toàn văn** (`has_chunks: false` trong
  `buoi_10/data/doc_relationships.json`), nên `chunks_for_document_by_similarity`
  sẽ trả về rỗng cho chúng dù tìm thấy đúng Document lân cận. Muốn multi-hop
  thực sự bổ sung được nội dung, cần nạp toàn văn 3 luật/nghị định đó vào
  Buổi 10 trước (đúng SPEC_buoi_10.md mục 8, không sửa gì ở Buổi 11).

## 4b. Đã nạp bổ sung toàn văn 3 văn bản liên quan (2026-08-12, sau khi user yêu cầu "nạp dùm")

Đã bổ sung vào `buoi_10/data/raw_html/`:
- `46_2010_QH12.html` — Luật NHNN, **toàn văn đầy đủ Điều 1–66** (lấy từ phần
  tiếng Việt công khai miễn phí trên thuvienphapluat.vn).
- `156_2013_ND_CP.html` — Nghị định 156/2013/NĐ-CP, **toàn văn đầy đủ Điều 1–6**.
- `47_2010_QH12.html` — Luật các TCTD, **CHỈ Điều 1–49 trong tổng số 165 Điều**
  (nguồn công khai miễn phí trên thuvienphapluat.vn dừng ở khoảng đó; không có
  quyền thực thi mã trong phiên này để tự động hoá thu thập/định dạng toàn bộ
  165 Điều một cách đáng tin cậy). Đã ghi rõ giới hạn này trong meta
  `source-note` của file và trong `note` của `doc_relationships.json` — không
  che giấu.

`doc_relationships.json` đã cập nhật `has_chunks: true` + `source_file` cho cả
3 văn bản (trước đó là node stub rỗng). Không sửa `41_2016_TT_NHNN.html` và
không đổi cấu trúc cột dữ liệu nào khác.

**Việc cần làm để dữ liệu này có hiệu lực (bắt buộc chạy lại ở Buổi 10 trước):**
1. Chạy lại `buoi_10\chay_buoi_10.ps1` — script không cần sửa, tự động
   glob `data\raw_html\*.html` nên sẽ tự nạp thêm 3 văn bản mới cùng
   `41_2016_TT_NHNN.html` (MERGE, không tạo trùng, không ảnh hưởng dữ liệu cũ).
2. Sau khi Buổi 10 nạp xong, chạy lại `buoi_11\chay_buoi_11.ps1` (bước
   `compare`) để `qa_comparison.md` phản ánh nội dung thật thay vì node stub
   rỗng — kỳ vọng hops=1/2 của Câu hỏi 4 sẽ khác hops=0 vì giờ đã có nội dung
   thật ở `46/2010/QH12` để mượn qua quan hệ `CAN_CU`.
3. Lưu ý: `47/2010/QH12` mới có Điều 1–49 — nếu multi-hop cần nội dung ở Điều
   50 trở lên (ví dụ chi tiết về hoạt động cấp tín dụng, tỷ lệ an toàn ở các
   chương sau) thì sẽ không tìm thấy — đây là giới hạn dữ liệu đã biết.

## 4c. Xác nhận bằng lần chạy thật sau khi nạp toàn văn (2026-08-13, 05:47:57)

Multi-hop nay **thực sự thay đổi kết quả** — khác hẳn 2 lần chạy trước (khi
3 văn bản còn là stub, hops=0/1/2 luôn giống hệt nhau):

| Câu hỏi | hops=0 | hops=1 | hops=2 |
|---|---|---|---|
| 1 | 5 chunk | 7 chunk (thêm từ 41/2016) | 7 chunk (giống hops=1) |
| 3 | 5 chunk | 7 chunk | **11 chunk** (thêm từ 46/2010, 156/2013) |
| 4 | 5 chunk | **11 chunk** (thêm từ 47/2010, 46/2010, 156/2013) | 11 chunk (giống hops=1) |
| 5 | 5 chunk | 9 chunk | 9 chunk (giống hops=1) |

→ Multi-hop hoạt động đúng như thiết kế: mở rộng ngữ cảnh qua `CAN_CU` khi
tăng hops, nội dung mở rộng là thật (không còn node rỗng).

Cả 15/15 lượt trả lời (5 câu × 3 hops) vẫn đúng yêu cầu "không bịa" — 14/15
đúng là từ chối vì văn bản được hỏi không có trong đồ thị; Câu hỏi 4 (văn bản
*có* trong đồ thị) **vẫn** trả lời "không đủ thông tin" dù giờ đã có thêm
ngữ cảnh thật, vì lý do đã dự đoán ở mục 4: top-5 vector-search trực tiếp
vẫn chỉ trúng 5 đoạn mở đầu/thể thức văn bản của 41/2016/TT-NHNN (điểm giống
hệt nhau 0.9013 — dấu hiệu đây là các đoạn gần trùng lặp, không phải đoạn
"Căn cứ Luật..."), và nội dung mượn thêm qua hop=1 (từ 46/2010, 47/2010 —
về thanh tra/giám sát ngân hàng) không nói rõ đây là "căn cứ" của 41/2016 nên
Gemini đúng khi không suy đoán. Đây là giới hạn của tham số `top_k_direct=5`,
không phải lỗi — có thể cải thiện bằng cách tăng `top_k_direct` (SPEC mục 4,
đã ghi từ trước, không bắt buộc phải sửa ngay).

## 5. Kết luận

Buổi 11 đạt đủ yêu cầu đề bài: kết nối Neo4j, tìm kiếm vector + multi-hop có
cấu hình số bước nhảy, tích hợp Gemini với quy tắc không bịa, kiểm thử 5 câu
hỏi ở 3 mức hops và ghi `qa_comparison.md` thật. Giới hạn duy nhất còn lại là
dữ liệu nguồn (3 văn bản liên quan chưa nạp toàn văn ở Buổi 10) khiến multi-hop
chưa thể hiện khác biệt nội dung — đã ghi rõ, không che giấu.

**Việc còn lại (tuỳ chọn, không bắt buộc):** muốn thấy multi-hop thực sự thay
đổi câu trả lời, cần quay lại Buổi 10, bổ sung toàn văn HTML của
`46/2010/QH12`, `47/2010/QH12`, `156/2013/NĐ-CP` vào `data/raw_html/`, nạp lại,
rồi chạy lại `compare` ở Buổi 11.
