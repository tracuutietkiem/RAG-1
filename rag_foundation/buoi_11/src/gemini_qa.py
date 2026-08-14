"""Bước 3 (SPEC_buoi_11.md mục 2): build prompt từ ngữ cảnh đồ thị + gọi
Gemini API (`gemini-flash-latest`).

`call_fn` luôn injectable — test dùng fake trả text cố định, không gọi API
thật, không cần `GEMINI_API_KEY` (tests/test_gemini_qa.py).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Sequence

from .graph_search import ContextChunk

# (system_prompt, user_prompt) -> câu trả lời text
CallFn = Callable[[str, str], str]

DEFAULT_MODEL = "gemini-flash-latest"

NO_CONTEXT_ANSWER_HINT = (
    "không có đủ thông tin trong ngữ cảnh được cung cấp để trả lời câu hỏi này"
)


@dataclass
class GeminiConfig:
    api_key: str = ""
    model: str = DEFAULT_MODEL

    @classmethod
    def from_env(cls) -> "GeminiConfig":
        return cls(
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model=os.getenv("GEMINI_MODEL", DEFAULT_MODEL),
        )


class GeminiClient:
    """Bọc SDK `google-genai`, lazy import — test/parse-only không bắt buộc
    cài SDK hay có API key."""

    def __init__(self, config: GeminiConfig | None = None):
        self.config = config or GeminiConfig.from_env()
        self._client = None

    def _load(self):
        if self._client is None:
            if not self.config.api_key:
                raise ValueError(
                    "GEMINI_API_KEY trống. Điền vào .env trước khi gọi Gemini API thật."
                )
            from google import genai  # type: ignore lazy import

            self._client = genai.Client(api_key=self.config.api_key)
        return self._client

    def __call__(self, system_prompt: str, user_prompt: str) -> str:
        from google.genai import types  # type: ignore lazy import

        client = self._load()
        response = client.models.generate_content(
            model=self.config.model,
            contents=user_prompt,
            config=types.GenerateContentConfig(system_instruction=system_prompt),
        )
        return response.text or ""


def build_system_prompt() -> str:
    """System prompt mô tả schema đồ thị + cấu trúc văn bản luật tiếng Việt,
    và quy tắc bắt buộc chỉ trả lời từ ngữ cảnh (SPEC mục 2, đề bài Bước 3)."""

    return (
        "Bạn là trợ lý tra cứu văn bản pháp luật ngân hàng Việt Nam, trả lời dựa "
        "trên một đồ thị tri thức Neo4j có cấu trúc sau:\n"
        "- Node (:Document): một văn bản luật (Luật, Nghị định, Thông tư...), "
        "có thuộc tính doc_id (số hiệu văn bản), title, doc_type.\n"
        "- Node (:Chunk): một đoạn văn bản đã làm sạch, có thuộc tính level "
        "(chuong|muc|dieu|khoan|diem|doan|bang), heading (tiêu đề nếu có), text.\n"
        "- Quan hệ [:PART_OF] nối Chunk gốc vào Document chứa nó; [:PARENT_OF] "
        "thể hiện cấu trúc phân cấp Chương→Mục→Điều→Khoản→Điểm; [:NEXT] giữ "
        "thứ tự đọc.\n"
        "- Quan hệ cấp văn bản [:CAN_CU] (căn cứ), [:THAY_THE] (thay thế), "
        "[:HOP_NHAT] (hợp nhất từ) nối hai Document với nhau.\n\n"
        "Ngữ cảnh đưa cho bạn là danh sách đoạn trích (Chunk) liên quan tới câu "
        "hỏi, mỗi đoạn ghi rõ văn bản nguồn (doc_id), tiêu đề (heading nếu có) "
        "và khoảng cách hop (hop=0 là khớp trực tiếp với câu hỏi; hop=1,2,... là "
        "lấy từ văn bản liên quan qua CAN_CU/THAY_THE/HOP_NHAT).\n\n"
        "QUY TẮC BẮT BUỘC:\n"
        "1. Chỉ trả lời dựa trên nội dung trong ngữ cảnh được cung cấp. "
        "Không tự suy đoán, không dùng kiến thức ngoài ngữ cảnh.\n"
        f"2. Nếu ngữ cảnh không đủ thông tin để trả lời, phải nói rõ "
        f'"{NO_CONTEXT_ANSWER_HINT}" thay vì bịa câu trả lời.\n'
        "3. Khi trả lời, trích dẫn rõ số hiệu văn bản (doc_id) và tiêu đề "
        "(heading) của đoạn đã dùng.\n"
        "4. Đây không phải tư vấn pháp lý chính thức — nếu câu hỏi liên quan "
        "quyết định thực tế, nhắc người dùng đối chiếu văn bản gốc."
    )


def build_user_prompt(question: str, chunks: Sequence[ContextChunk]) -> str:
    """Ghép câu hỏi + ngữ cảnh thành user prompt. Hàm thuần, không I/O — dễ
    test trực tiếp với danh sách ContextChunk giả."""

    if not chunks:
        context_block = "(không tìm thấy đoạn văn bản nào liên quan)"
    else:
        parts = []
        for c in chunks:
            heading = c.heading or f"(chunk cấp {c.level}, không có tiêu đề)"
            parts.append(
                f"[hop={c.hop} | doc_id={c.doc_id} | {heading}]\n{c.text}"
            )
        context_block = "\n\n".join(parts)

    return f"NGỮ CẢNH:\n{context_block}\n\nCÂU HỎI: {question}"


def answer_question(question: str, chunks: Sequence[ContextChunk], call_fn: CallFn) -> str:
    """Bước 3 tổng hợp: build prompt rồi gọi call_fn (injectable). Hàm mỏng để
    test không phải mock nội bộ GeminiClient."""

    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(question, chunks)
    return call_fn(system_prompt, user_prompt)
