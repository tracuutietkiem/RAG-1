# Buổi 17 — Secure Retrieval Test (PROMPT 2)

Số chunk chỉ dành riêng cho {Admin, HR} (không Staff/Guest/Risk_Manager): 478

## Test 1 — role được phép (HR) nhận được chunk

- Câu hỏi: *Quy định về bổ nhiệm, miễn nhiệm cán bộ quản lý là gì?*
- Số chunk HR nhận được: 5
- Kết quả: **PASS**

## Test 2 — role không được phép (Guest) không nhận đúng các chunk hạn chế đó

- Chunk HR-only vô tình lọt vào kết quả của Guest: (không có)
- Kết quả: **PASS**

## Test 3 — unauthorized chunk không xuất hiện trong context (kể cả before_rerank)

- Số candidate kiểm tra (before_rerank + results): 25
- Candidate không đúng quyền Guest lọt vào: (không có)
- Kết quả: **PASS**

## Test 4 — citation/document_id/chunk_id không bị mất

- Trường bị thiếu: (không có)
- Ví dụ 1 kết quả đầy đủ: `{'rank': 1, 'chunk_id': '186888_D6K2p2_013', 'document_id': '186888', 'title': '62/2025/TT-NHNN', 'article': '6', 'citation': 'Thông tư số 62/2025/TT-NHNN Quy định về hệ thống kiểm soát nội bộ của tổ chức tín dụng là hợp tác xã, tổ chức tài chính vi mô | Điều 6 | 186888_D6K2p2_013', 'allowed_roles': ['Admin', 'HR'], 'access_decision': 'GRANTED', 'retrieval_method': 'secure_hybrid_rerank', 'score': 0.709114, 'text': 'Điều 6. Cơ cấu tổ chức thực hiện của hệ thống kiểm soát nội bộ\nbất thường của ủy ban;\n\n(iv) Việc đưa ra quyết định của ủy ban;\n\nd) Quy định chức năng, nhiệm vụ của các ủy ban:\n\n(i) Ủy ban quản lý rủi ro:\n\n- Tham mưu cho Hội đồng quản trị trong việc ban hành chính sách quản lý rủi ro, quy trình, quy định nội bộ về quản lý rủi ro trong hoạt động theo quy định của pháp luật và Điều lệ của tổ chức tín dụng là hợp tác xã;\n\n- Phân tích, đưa ra những cảnh báo về mức độ an toàn của tổ chức tín dụng là hợp tác xã trước những nguy cơ, tiềm ẩn rủi ro có thể ảnh hưởng và biện pháp phòng ngừa đối với các rủi ro này trong ngắn hạn, dài hạn;\n\n- Xem xét, đánh giá tính phù hợp và hiệu quả của các quy trình, chính sách quản lý rủi ro hiện hành của tổ chức tín dụng là hợp tác xã để đưa các khuyến nghị, đề xuất đối với Hội đồng quản trị về những yêu cầu cần thay đổi quy trình, chính sách hiện hành, chiến lược hoạt động;\n\n- Tham mưu cho Hội đồng quản trị trong việc quyết định phê duyệt các khoản đầu tư, các giao dịch có liên quan, chính sách quản lý và phương án xử lý rủi ro trong phạm vi chức năng, nhiệm vụ do Hội đồng quản trị giao.\n\n(ii) Ủy ban nhân sự:\n\n- Tham mưu cho Hội đồng quản trị về quy mô và cơ cấu Hội đồng quản trị, người điều hành phù hợp với quy mô hoạt động và chiến lược phát triển của tổ chức tín dụng là hợp tác xã;\n\n- Tham mưu cho Hội đồng quản trị xử lý các vấn đề về nhân sự phát sinh trong quá trình tiến hành các thủ tục bầu, bổ nhiệm, bãi nhiệm, miễn nhiệm các chức danh thành viên Hội đồng quản trị, thành viên Ban kiểm soát và người điều hành tổ chức tín dụng là hợp tác xã theo đúng quy định của pháp luật và Điều lệ tổ chức tín dụng là hợp tác xã;\n\n- Nghiên cứu, tham mưu cho Hội đồng quản trị trong việc ban hành các quy định nội bộ của tổ chức tín dụng là hợp tác xã thuộc thẩm quyền của Hội đồng quản trị về chế độ tiền lương, thù lao, tiền thưởng, quy chế tuyển chọn nhân sự, đào tạo và các chính sách đãi ngộ khác đối với người điều hành, các cán bộ, nhân viên của tổ chức tín dụng là hợp tác xã.'}`
- Kết quả: **PASS**

## Kết luận

SECURE RETRIEVAL REUSE: PASS
NO UNAUTHORIZED CONTEXT: PASS
CITATION PRESERVED: PASS
