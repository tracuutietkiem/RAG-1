# Báo cáo Đánh giá Hệ thống RAG bằng Ragas — Buổi 16

*Thời điểm chạy: 21/08/2026 07:36:01*  
*Model Pipeline (Generator): `Qwen/Qwen3.5-9B:deepinfra`*  
*Model Judger (Evaluator): `openai/gpt-oss-20b:deepinfra`*  
*Số câu hỏi đánh giá: 20*

## 1. Bảng tóm tắt điểm trung bình 4 metrics

| Metric | Điểm trung bình | Đánh giá |
| :--- | :---: | :--- |
| Context Precision | 0,913 | ✅ Đạt |
| Context Recall | 0,950 | ✅ Đạt |
| Faithfulness | 0,728 | ⚠️ Cần cải thiện |
| Answer Relevancy | 0,626 | ⚠️ Cần cải thiện |

## 2. Điểm trung bình theo Use Case

| Use case | Số câu hỏi | Context Precision | Context Recall | Faithfulness | Answer Relevancy |
| :--- | :---: | :---: | :---: | :---: | :---: |
| Nhân sự | 4 | 0,967 | 1,000 | 0,700 | 0,726 |
| Quy định chung | 10 | 0,989 | 1,000 | 0,825 | 0,635 |
| Rủi ro | 6 | 0,750 | 0,833 | 0,583 | 0,545 |

## 3. Điểm trung bình theo độ khó

| Độ khó | Số câu hỏi | Context Precision | Context Recall | Faithfulness | Answer Relevancy |
| :--- | :---: | :---: | :---: | :---: | :---: |
| easy | 7 | 0,929 | 1,000 | 0,643 | 0,535 |
| medium | 7 | 0,984 | 1,000 | 0,686 | 0,680 |
| hard | 6 | 0,811 | 0,833 | 0,875 | 0,671 |

## 4. Phân tích các câu hỏi có điểm số thấp (< 0,7)

Có **15/20** câu hỏi có ít nhất một metric dưới 0,7:

| # | Câu hỏi | Use case | Độ khó | Metric thấp nhất | Điểm | Nguyên nhân khả dĩ |
| :---: | :--- | :--- | :--- | :--- | :---: | :--- |
| 1 | Theo Điều 4, mục 19 của văn bản, một thành viên được xếp vào loại 'Thà... | Quy định chung | easy | Faithfulness | 0,500 | Generator có thể đã suy diễn/thêm thông tin ngoài ngữ cảnh được cấp. |
| 2 | Để xác định một thành viên có phải là 'Thành viên liên kết không góp v... | Quy định chung | medium | Answer Relevancy | 0,692 | Câu trả lời lạc đề hoặc dài dòng, chưa đi thẳng vào câu hỏi. |
| 3 | Để thực hiện nhiệm vụ quản lý nhà nước về phát triển tổ hợp tác, hợp t... | Quy định chung | easy | Answer Relevancy | 0,488 | Câu trả lời lạc đề hoặc dài dòng, chưa đi thẳng vào câu hỏi. |
| 4 | Các khoản chi phí liên quan đến việc thiết kế mẫu tiền, chế bản và in,... | Quy định chung | medium | Answer Relevancy | 0,609 | Câu trả lời lạc đề hoặc dài dòng, chưa đi thẳng vào câu hỏi. |
| 5 | Theo quy định tại Điều 17, điều kiện bắt buộc để các khoản chi phí liê... | Quy định chung | hard | Answer Relevancy | 0,636 | Câu trả lời lạc đề hoặc dài dòng, chưa đi thẳng vào câu hỏi. |
| 6 | Theo Điều 51a, trong thời hạn bao nhiêu ngày làm việc kể từ ngày ra qu... | Quy định chung | easy | Answer Relevancy | 0,588 | Câu trả lời lạc đề hoặc dài dòng, chưa đi thẳng vào câu hỏi. |
| 7 | Để hoàn thành quy trình thi hành hình thức đình chỉ hoạt động giao dịc... | Quy định chung | medium | Faithfulness | 0,000 | Generator có thể đã suy diễn/thêm thông tin ngoài ngữ cảnh được cấp. |
| 8 | Theo Điều 54, ai là người có trách nhiệm hướng dẫn về phương pháp tính... | Quy định chung | hard | Answer Relevancy | 0,589 | Câu trả lời lạc đề hoặc dài dòng, chưa đi thẳng vào câu hỏi. |
| 9 | Thông tư số 29/2024/TT-NHNN được ban hành dựa trên căn cứ nào liên qua... | Rủi ro | medium | Faithfulness | 0,000 | Generator có thể đã suy diễn/thêm thông tin ngoài ngữ cảnh được cấp. |
| 10 | Trong số các văn bản pháp luật được nêu trong phần căn cứ để ban hành ... | Rủi ro | hard | Context Precision | 0,000 | Tài liệu liên quan không được xếp hạng cao trong kết quả truy xuất. |
| 11 | Theo quy định tại Điều 4, Tổ chức tín dụng hỗ trợ là tổ chức tín dụng ... | Rủi ro | easy | Faithfulness | 0,000 | Generator có thể đã suy diễn/thêm thông tin ngoài ngữ cảnh được cấp. |
| 12 | Theo Điều 7, ai là người có thẩm quyền quy định cơ cấu tổ chức, nhiệm ... | Rủi ro | medium | Answer Relevancy | 0,688 | Câu trả lời lạc đề hoặc dài dòng, chưa đi thẳng vào câu hỏi. |
| 13 | Dựa trên các căn cứ pháp lý được nêu trong Thông tư, điều kiện nào về ... | Rủi ro | hard | Answer Relevancy | 0,688 | Câu trả lời lạc đề hoặc dài dòng, chưa đi thẳng vào câu hỏi. |
| 14 | Theo Điều 81, thành viên của ngân hàng hợp tác xã bao gồm những đối tư... | Rủi ro | easy | Answer Relevancy | 0,616 | Câu trả lời lạc đề hoặc dài dòng, chưa đi thẳng vào câu hỏi. |
| 15 | Theo Điều 64, trong thời gian đảm nhiệm chức vụ thành viên Hội đồng qu... | Nhân sự | easy | Faithfulness | 0,000 | Generator có thể đã suy diễn/thêm thông tin ngoài ngữ cảnh được cấp. |

## 5. Đề xuất tối ưu hóa hệ thống

| Triệu chứng (Chỉ số thấp) | Nguyên nhân phổ biến | Giải pháp kỹ thuật đề xuất |
| :--- | :--- | :--- |
| **Context Recall thấp** (< 0.7) | Truy vấn BM25 bỏ lỡ từ đồng nghĩa; Dense gặp vấn đề với từ viết tắt; `top_k` quá nhỏ. | Tăng `top_k` (vd 5→8); tích hợp Query Expansion bằng LLM; lấy thêm node lân cận trên đồ thị Neo4j (`NEXT`, `CONTAINS`). |
| **Context Precision thấp** (< 0.7) | Chunk không liên quan có điểm tương đồng vector cao, chiếm vị trí đầu; RRF chưa cân bằng BM25/Dense. | Cấu hình lại trọng số/tham số $k$ trong RRF; nâng cấp/tinh chỉnh Cross-Encoder Reranker. |
| **Faithfulness thấp** (< 0.8) | Generator tự bổ sung kiến thức ngoài ngữ cảnh (hallucination); ngữ cảnh quá dài gây nhiễu. | Siết chặt prompt hệ thống (chỉ trả lời dựa vào context); áp dụng Chain-of-Thought có kiểm soát; rút ngắn/lọc bớt nhiễu trong chunk. |
| **Answer Relevancy thấp** (< 0.8) | Câu trả lời chung chung, không đi thẳng câu hỏi; quá dài dòng. | Điều chỉnh prompt Generator yêu cầu ngắn gọn, súc tích; bổ sung few-shot ví dụ mẫu. |


## 6. Ghi chú vận hành

- Judger (Evaluator) dùng model **khác** với Generator để tránh *Self-preference bias* — đúng chuẩn công nghiệp LLM-as-a-judge.
- Nếu điểm Context Recall thấp mà tăng `top_k` thì Faithfulness có thể giảm (ngữ cảnh dài → nhiễu) — cần cân bằng qua thử nghiệm A/B `top_k`.
- Dữ liệu đưa vào Judger là văn bản quy phạm pháp luật ngân hàng (đã công khai), phù hợp gọi qua API công cộng; với tài liệu nội bộ nhạy cảm hơn nên cân nhắc triển khai Judger nội bộ/offline theo chính sách an toàn thông tin của Agribank.