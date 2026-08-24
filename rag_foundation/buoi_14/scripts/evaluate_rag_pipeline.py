"""
BUOI 16 - RAG Evaluation Pipeline (Ragas).

Script DUY NHAT tu dong hoa toan bo quy trinh danh gia he thong RAG:

    a. Sinh Golden Dataset (20 cau hoi + dap an chuan) tu chunks_secure.csv,
       phan bo theo usecase (HR / Risk / General) va do kho (easy/medium/hard).
    b. Chay SecureRetriever (buoi 15) de lay contexts, roi goi Model Pipeline
       (Generator) qua HF Router de sinh cau tra loi RAG.
    c. Cham diem 4 metrics Ragas (Context Precision, Context Recall,
       Faithfulness, Answer Relevancy) bang Model Judger (Evaluator) qua HF
       Router - tach biet khoi Generator de tranh Self-preference bias.
    d. Phan tich loi + xuat bao cao toi uu hoa ra outputs/ragas_evaluation_report.md.

Cach chay:
    python scripts/evaluate_rag_pipeline.py

Yeu cau: buoi_14/.env (hoac .env.txt) phai co HF_TOKEN.
"""

from __future__ import annotations

import json
import os
import random
import re
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config  # noqa: E402
from src.secure_retriever import secure_search  # noqa: E402

# ---------------------------------------------------------------- error log
# (Chinh sach chung: moi loi khi chay code/xu ly file phai duoc ghi log va
#  bao ngay - xem outputs/buoi16_error_log.txt)
ERROR_LOG = config.OUTPUTS_DIR / "buoi16_error_log.txt"


def log_error(stage: str, exc: Exception) -> None:
    ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(ERROR_LOG, "a", encoding="utf-8") as fh:
        fh.write(f"\n[{datetime.now().isoformat(timespec='seconds')}] STAGE={stage}\n")
        fh.write(f"{type(exc).__name__}: {exc}\n")
        fh.write(traceback.format_exc())
        fh.write("\n" + "-" * 80 + "\n")


# ---------------------------------------------------------------- HF Router
GENERATOR_MODEL = os.getenv("RAG_GENERATOR_MODEL", "Qwen/Qwen3.5-9B:deepinfra")
JUDGER_MODEL = os.getenv("RAG_JUDGER_MODEL", "openai/gpt-oss-20b:deepinfra")

HF_TOKEN = os.environ.get("HF_TOKEN", "").strip()
if not HF_TOKEN:
    raise RuntimeError(
        "HF_TOKEN chua duoc cau hinh. Them dong HF_TOKEN=hf_xxx vao buoi_14/.env "
        "(hoac .env.txt) roi chay lai."
    )

from openai import OpenAI  # noqa: E402

client = OpenAI(base_url="https://router.huggingface.co/v1", api_key=HF_TOKEN)

_THINK_TAG_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def _strip_reasoning(text: str) -> str:
    """Don phong khi model van tra ve chain-of-thought du da yeu cau tat."""
    return _THINK_TAG_RE.sub("", text or "").strip()


def call_llm(model: str, system: str, user: str, temperature: float = 0.2,
             max_tokens: int = 1200, max_retries: int = 4) -> str:
    """Goi HF Router (OpenAI-compatible). Thu tat reasoning bang extra_body,
    neu provider khong ho tro thi tu dong goi lai khong co extra_body."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    last_exc: Exception | None = None
    for attempt in range(1, max_retries + 1):
        for use_extra_body in (True, False):
            try:
                kwargs = dict(model=model, messages=messages, temperature=temperature,
                              max_tokens=max_tokens)
                if use_extra_body:
                    kwargs["extra_body"] = {"reasoning": {"effort": "none"}}
                resp = client.chat.completions.create(**kwargs)
                msg = resp.choices[0].message
                content = (msg.content or "").strip()
                if not content:
                    content = (getattr(msg, "reasoning_content", "") or "").strip()
                return _strip_reasoning(content)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if use_extra_body:
                    continue  # thu lai ngay khong co extra_body, khong tinh la 1 lan retry
                break
        wait = min(2 ** attempt, 20)
        time.sleep(wait)
    log_error(f"call_llm[{model}]", last_exc or RuntimeError("unknown"))
    raise RuntimeError(f"Goi model {model} that bai sau {max_retries} lan thu: {last_exc}")


# =========================================================================
# BUOC A - Sinh Golden Dataset
# =========================================================================
USECASE_LABELS = {"HR": "Nhân sự", "RISK": "Rủi ro", "GENERAL": "Quy định chung"}
DIFFICULTIES = ["easy", "medium", "hard"]


def _load_secure_df() -> pd.DataFrame:
    import csv
    csv.field_size_limit(min(sys.maxsize, 2 ** 31 - 1))
    return pd.read_csv(config.CHUNKS_SECURE_CSV, engine="python")


def _pick_source_chunks(df: pd.DataFrame, n_per_cat: dict, seed: int = 42) -> pd.DataFrame:
    """Chon ngau nhien (co seed) mot so chunk tieu bieu cho moi usecase, uu
    tien cac chunk co do dai van ban hop ly (khong qua ngan / qua nhieu boilerplate)."""
    rng = random.Random(seed)
    picked = []
    for cat, n in n_per_cat.items():
        sub = df[(df["security_category"] == cat) & (df["text"].str.len() >= 200)]
        idx = list(sub.index)
        rng.shuffle(idx)
        picked.extend(idx[:n])
    return df.loc[picked]


def generate_golden_dataset() -> pd.DataFrame:
    print("\n[BUOC A] Sinh Golden Dataset tu chunks_secure.csv ...")
    df = _load_secure_df()

    # 10-15 chunk nguon, phan bo theo 3 nhom bao mat: HR / RISK / GENERAL
    src_chunks = _pick_source_chunks(df, {"GENERAL": 5, "RISK": 5, "HR": 4}, seed=42)
    print(f"  - Da chon {len(src_chunks)} chunk nguon (GENERAL/RISK/HR).")

    # Phan bo 20 cau hoi theo do kho gan deu: 7 easy / 7 medium / 6 hard
    n_total = 20
    n_chunks = len(src_chunks)
    quotas = [n_total // n_chunks + (1 if i < n_total % n_chunks else 0) for i in range(n_chunks)]

    rows = []
    diff_cycle = (DIFFICULTIES * ((n_total // len(DIFFICULTIES)) + 1))[:n_total]
    diff_iter = iter(diff_cycle)

    for (_, rec), n_q in zip(src_chunks.iterrows(), quotas):
        if n_q <= 0:
            continue
        difficulties_for_chunk = [next(diff_iter) for _ in range(n_q)]
        usecase = USECASE_LABELS.get(rec["security_category"], rec["security_category"])
        system = (
            "Bạn là chuyên gia soạn đề kiểm tra hiểu văn bản quy phạm pháp luật "
            "trong lĩnh vực ngân hàng tại Việt Nam. CHỈ được sinh câu hỏi và đáp án "
            "dựa HOÀN TOÀN vào đoạn văn bản được cung cấp, KHÔNG được suy diễn hay "
            "thêm thông tin ngoài đoạn văn bản đó."
        )
        diff_desc = ", ".join(difficulties_for_chunk)
        user = f"""Đoạn văn bản nguồn (mã chunk: {rec['chunk_id']}, văn bản: {rec.get('so_ky_hieu','')}):
---
{str(rec['text'])[:2500]}
---

Hãy sinh đúng {n_q} câu hỏi kiểm tra (kèm đáp án chuẩn - ground_truth) dựa CHÍNH XÁC \
vào đoạn văn bản trên, theo thứ tự độ khó lần lượt là: {diff_desc}.
- easy: hỏi trực tiếp một sự kiện/số liệu/quy định rõ ràng có trong đoạn văn.
- medium: cần kết hợp 2 chi tiết trong đoạn văn để trả lời.
- hard: đòi hỏi hiểu điều kiện/ngoại lệ hoặc suy luận sát nghĩa trong đoạn văn.

Trả lời DUY NHẤT bằng một JSON array hợp lệ, không thêm chữ nào khác, đúng định dạng:
[{{"question": "...", "ground_truth": "..."}}, ...]"""

        try:
            raw = call_llm(GENERATOR_MODEL, system, user, temperature=0.4, max_tokens=1200)
            raw_json = raw[raw.find("["): raw.rfind("]") + 1]
            qa_list = json.loads(raw_json)
        except Exception as exc:  # noqa: BLE001
            log_error("generate_golden_dataset:parse", exc)
            print(f"  [CANH BAO] Bo qua chunk {rec['chunk_id']} do loi sinh/parse JSON: {exc}")
            continue

        for qa, difficulty in zip(qa_list, difficulties_for_chunk):
            q = (qa.get("question") or "").strip()
            gt = (qa.get("ground_truth") or "").strip()
            if not q or not gt:
                continue
            rows.append({
                "question": q,
                "ground_truth": gt,
                "usecase": usecase,
                "difficulty": difficulty,
                "source_chunk_id": rec["chunk_id"],
                "source_document": rec.get("so_ky_hieu", ""),
            })

    qa_df = pd.DataFrame(rows).head(n_total)
    if qa_df.empty:
        raise RuntimeError("Khong sinh duoc cau hoi nao - kiem tra HF_TOKEN / model Generator.")

    config.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.EVAL_DIR / "qa_dataset.csv"
    qa_df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"  -> Da luu {len(qa_df)} cau hoi vao {out_path.relative_to(BASE_DIR)}")
    return qa_df


# =========================================================================
# BUOC B - Chay RAG Pipeline (Retrieval + Generation)
# =========================================================================
RAG_USER_ROLES = ["Admin", "HR", "Risk_Manager", "Staff"]

RAG_SYSTEM_PROMPT = (
    "Bạn là trợ lý tra cứu văn bản pháp luật ngân hàng nội bộ. CHỈ được trả lời "
    "dựa trên NGỮ CẢNH được cung cấp dưới đây, KHÔNG được suy diễn hay dùng kiến "
    "thức bên ngoài ngữ cảnh. Nếu ngữ cảnh không đủ thông tin để trả lời, hãy nói rõ "
    "'Ngữ cảnh được cung cấp không đủ thông tin để trả lời câu hỏi này.' "
    "Trả lời ngắn gọn, đi thẳng vào trọng tâm, không lặp lại câu hỏi, không thêm lời dẫn thừa."
)


def run_rag_pipeline(qa_df: pd.DataFrame) -> pd.DataFrame:
    print("\n[BUOC B] Chay SecureRetriever + Generator de sinh cau tra loi RAG ...")
    answers, contexts_col, n_ctx_col = [], [], []
    for i, row in qa_df.reset_index(drop=True).iterrows():
        question = row["question"]
        try:
            result = secure_search(question, RAG_USER_ROLES, method="hybrid_rerank",
                                     top_k=config.FINAL_TOP_K)
            contexts = [r["text"] for r in result["results"]]
        except Exception as exc:  # noqa: BLE001
            log_error(f"secure_search[{i}]", exc)
            contexts = []

        if not contexts:
            answer = "Ngữ cảnh được cung cấp không đủ thông tin để trả lời câu hỏi này."
        else:
            ctx_block = "\n\n---\n\n".join(f"[Đoạn {j+1}] {c}" for j, c in enumerate(contexts))
            user = f"NGỮ CẢNH:\n{ctx_block}\n\nCÂU HỎI: {question}\n\nTRẢ LỜI:"
            try:
                answer = call_llm(GENERATOR_MODEL, RAG_SYSTEM_PROMPT, user, temperature=0.0,
                                   max_tokens=600)
            except Exception as exc:  # noqa: BLE001
                log_error(f"generator_answer[{i}]", exc)
                answer = "[LOI] Khong sinh duoc cau tra loi - xem outputs/buoi16_error_log.txt"

        answers.append(answer)
        contexts_col.append(contexts)
        n_ctx_col.append(len(contexts))
        print(f"  [{i+1}/{len(qa_df)}] {question[:60]}... -> {len(contexts)} contexts")

    out = qa_df.reset_index(drop=True).copy()
    out["answer"] = answers
    out["contexts"] = contexts_col
    out["n_contexts"] = n_ctx_col
    return out


# =========================================================================
# BUOC C - Cham diem Ragas (4 metrics) bang Model Judger
# =========================================================================
def run_ragas_evaluation(rag_df: pd.DataFrame) -> pd.DataFrame:
    print("\n[BUOC C] Cham diem Ragas (Context Precision / Recall, Faithfulness, "
          f"Answer Relevancy) bang Model Judger = {JUDGER_MODEL} ...")

    # --- shim: ragas 0.4.x import 1 submodule vertexai da bi go khoi ban
    # langchain-community moi -> stub rong de tranh ModuleNotFoundError khi
    # import (khong dung Vertex AI trong bai nay). ---
    import types as _types
    if "langchain_community.chat_models.vertexai" not in sys.modules:
        _stub = _types.ModuleType("langchain_community.chat_models.vertexai")

        class _ChatVertexAIStub:  # pragma: no cover - khong dung
            pass

        _stub.ChatVertexAI = _ChatVertexAIStub
        sys.modules["langchain_community.chat_models.vertexai"] = _stub

    from datasets import Dataset
    from ragas import evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import (answer_relevancy, context_precision, context_recall,
                                faithfulness)
    from ragas.run_config import RunConfig
    from langchain_openai import ChatOpenAI
    from langchain_huggingface import HuggingFaceEmbeddings

    judger_chat = ChatOpenAI(
        model=JUDGER_MODEL,
        base_url="https://router.huggingface.co/v1",
        api_key=HF_TOKEN,
        temperature=0.0,
    )
    ragas_llm = LangchainLLMWrapper(judger_chat)

    # Answer Relevancy can mot embedding model doc lap (khong phai LLM) de so
    # sanh cau hoi goc voi cau hoi sinh nguoc tu answer. Tai dung embedding
    # local (offline, khong ton chi phi API) cua chinh du an Buoi 14.
    try:
        hf_emb = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL)
        ragas_embeddings = LangchainEmbeddingsWrapper(hf_emb)
    except Exception as exc:  # noqa: BLE001
        log_error("ragas_embeddings_init", exc)
        print("  [CANH BAO] Khong tai duoc embedding model cho Answer Relevancy "
              f"({exc}). Bo qua metric nay.")
        ragas_embeddings = None

    ds = Dataset.from_dict({
        "question": rag_df["question"].tolist(),
        "answer": rag_df["answer"].tolist(),
        "contexts": rag_df["contexts"].tolist(),
        "ground_truth": rag_df["ground_truth"].tolist(),
    })

    metrics = [context_precision, context_recall, faithfulness]
    if ragas_embeddings is not None:
        metrics.append(answer_relevancy)
    metric_names = [m.name for m in metrics]

    run_config = RunConfig(timeout=240, max_retries=6, max_wait=30, max_workers=3)

    # LUU Y: goi evaluate() MOT LAN cho ca 20 cau (batch) tung bi loi ngam -
    # cau nao gap rate-limit/timeout tam thoi bi RAGAS AM THAM LOAI BO khoi
    # ket qua thay vi tra ve NaN, dan den mat du lieu ma khong co canh bao
    # ro rang (vi du 12/20 cau bien mat khong dau vet). De dam bao KHONG BAO
    # GIO mat cau hoi nao va biet chinh xac cau nao loi vi sao, cham tung cau
    # MOT (evaluate() voi dataset 1 dong), ghi log day du khi that bai.
    rows_out = []
    n_ok, n_fail = 0, 0
    for i in range(len(rag_df)):
        row = rag_df.iloc[i]
        single_ds = Dataset.from_dict({
            "question": [row["question"]],
            "answer": [row["answer"]],
            "contexts": [row["contexts"]],
            "ground_truth": [row["ground_truth"]],
        })
        scores = {m: None for m in metric_names}
        try:
            result = evaluate(
                single_ds, metrics=metrics, llm=ragas_llm, embeddings=ragas_embeddings,
                run_config=run_config, raise_exceptions=False, show_progress=False,
            )
            sc = result.to_pandas()
            if len(sc) == 0:
                raise RuntimeError(
                    "Ragas tra ve rong cho cau nay (co the do Judger tra loi sai "
                    "dinh dang khien parser that bai)."
                )
            for m in metric_names:
                if m in sc.columns and pd.notna(sc.iloc[0][m]):
                    scores[m] = float(sc.iloc[0][m])
            n_ok += 1
        except Exception as exc:  # noqa: BLE001
            log_error(f"ragas_row[{i}]:{row['question'][:60]}", exc)
            n_fail += 1
            print(f"  [CANH BAO] Cau {i+1}/{len(rag_df)} loi khi cham Ragas: {exc}")

        out_row = row.to_dict()
        out_row.update(scores)
        rows_out.append(out_row)
        score_str = ", ".join(
            f"{m}={scores[m]:.3f}" if scores[m] is not None else f"{m}=N/A"
            for m in metric_names
        )
        print(f"  [{i+1}/{len(rag_df)}] {score_str}")

    merged = pd.DataFrame(rows_out)
    print(f"\n  Tong ket cham diem: {n_ok}/{len(rag_df)} cau thanh cong, "
          f"{n_fail} cau loi (chi tiet xem outputs/buoi16_error_log.txt).")

    config.EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.EVAL_DIR / "evaluation_results.csv"
    merged.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"  -> Da luu ket qua chi tiet vao {out_path.relative_to(BASE_DIR)}")
    return merged


# =========================================================================
# BUOC D - Bao cao danh gia + de xuat toi uu
# =========================================================================
METRIC_COLS = ["context_precision", "context_recall", "faithfulness", "answer_relevancy"]

OPTIMIZATION_TABLE = """\
| Triệu chứng (Chỉ số thấp) | Nguyên nhân phổ biến | Giải pháp kỹ thuật đề xuất |
| :--- | :--- | :--- |
| **Context Recall thấp** (< 0.7) | Truy vấn BM25 bỏ lỡ từ đồng nghĩa; Dense gặp vấn đề với từ viết tắt; `top_k` quá nhỏ. | Tăng `top_k` (vd 5→8); tích hợp Query Expansion bằng LLM; lấy thêm node lân cận trên đồ thị Neo4j (`NEXT`, `CONTAINS`). |
| **Context Precision thấp** (< 0.7) | Chunk không liên quan có điểm tương đồng vector cao, chiếm vị trí đầu; RRF chưa cân bằng BM25/Dense. | Cấu hình lại trọng số/tham số $k$ trong RRF; nâng cấp/tinh chỉnh Cross-Encoder Reranker. |
| **Faithfulness thấp** (< 0.8) | Generator tự bổ sung kiến thức ngoài ngữ cảnh (hallucination); ngữ cảnh quá dài gây nhiễu. | Siết chặt prompt hệ thống (chỉ trả lời dựa vào context); áp dụng Chain-of-Thought có kiểm soát; rút ngắn/lọc bớt nhiễu trong chunk. |
| **Answer Relevancy thấp** (< 0.8) | Câu trả lời chung chung, không đi thẳng câu hỏi; quá dài dòng. | Điều chỉnh prompt Generator yêu cầu ngắn gọn, súc tích; bổ sung few-shot ví dụ mẫu. |
"""


def _fmt_vn(x: float, digits: int = 3) -> str:
    """Dinh dang so kieu Viet Nam: dau phay la dau thap phan."""
    if pd.isna(x):
        return "N/A"
    return f"{x:.{digits}f}".replace(".", ",")


def build_report(df: pd.DataFrame) -> str:
    print("\n[BUOC D] Phan tich loi + xuat bao cao ...")
    present_metrics = [m for m in METRIC_COLS if m in df.columns]
    means = {m: df[m].mean() for m in present_metrics}

    failed_mask = pd.Series(True, index=df.index)
    for m in present_metrics:
        failed_mask = failed_mask & df[m].isna()
    n_failed = int(failed_mask.sum())
    n_scored = len(df) - n_failed

    lines = []
    lines.append("# Báo cáo Đánh giá Hệ thống RAG bằng Ragas — Buổi 16\n")
    lines.append(f"*Thời điểm chạy: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*  ")
    lines.append(f"*Model Pipeline (Generator): `{GENERATOR_MODEL}`*  ")
    lines.append(f"*Model Judger (Evaluator): `{JUDGER_MODEL}`*  ")
    lines.append(f"*Số câu hỏi trong Golden Dataset: {len(df)} — chấm điểm thành công: {n_scored}"
                  + (f", lỗi khi chấm: {n_failed} (xem mục 7)" if n_failed else "") + "*\n")

    lines.append("## 1. Bảng tóm tắt điểm trung bình 4 metrics\n")
    lines.append("| Metric | Điểm trung bình | Đánh giá |")
    lines.append("| :--- | :---: | :--- |")
    thresholds = {"context_precision": 0.7, "context_recall": 0.7,
                  "faithfulness": 0.8, "answer_relevancy": 0.8}
    labels = {"context_precision": "Context Precision", "context_recall": "Context Recall",
              "faithfulness": "Faithfulness", "answer_relevancy": "Answer Relevancy"}
    for m in present_metrics:
        v = means[m]
        verdict = "✅ Đạt" if v >= thresholds.get(m, 0.7) else "⚠️ Cần cải thiện"
        lines.append(f"| {labels.get(m, m)} | {_fmt_vn(v)} | {verdict} |")
    lines.append("")

    if {"usecase"}.issubset(df.columns):
        lines.append("## 2. Điểm trung bình theo Use Case\n")
        lines.append("| Use case | Số câu hỏi | " + " | ".join(labels[m] for m in present_metrics) + " |")
        lines.append("| :--- | :---: | " + " | ".join([":---:"] * len(present_metrics)) + " |")
        for uc, g in df.groupby("usecase"):
            row = [uc, str(len(g))] + [_fmt_vn(g[m].mean()) for m in present_metrics]
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    if {"difficulty"}.issubset(df.columns):
        lines.append("## 3. Điểm trung bình theo độ khó\n")
        lines.append("| Độ khó | Số câu hỏi | " + " | ".join(labels[m] for m in present_metrics) + " |")
        lines.append("| :--- | :---: | " + " | ".join([":---:"] * len(present_metrics)) + " |")
        for d in DIFFICULTIES:
            g = df[df["difficulty"] == d]
            if g.empty:
                continue
            row = [d, str(len(g))] + [_fmt_vn(g[m].mean()) for m in present_metrics]
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    # ---- phan tich cau hoi diem thap ----
    lines.append("## 4. Phân tích các câu hỏi có điểm số thấp (< 0,7)\n")
    low_mask = pd.Series(False, index=df.index)
    for m in present_metrics:
        low_mask = low_mask | (df[m] < 0.7)
    low_df = df[low_mask]

    if low_df.empty:
        lines.append("Không có câu hỏi nào có điểm số dưới ngưỡng 0,7 trên cả 4 metrics.\n")
    else:
        lines.append(f"Có **{len(low_df)}/{len(df)}** câu hỏi có ít nhất một metric dưới 0,7:\n")
        lines.append("| # | Câu hỏi | Use case | Độ khó | Metric thấp nhất | Điểm | Nguyên nhân khả dĩ |")
        lines.append("| :---: | :--- | :--- | :--- | :--- | :---: | :--- |")
        cause_map = {
            "context_recall": "Retriever bỏ lỡ tài liệu chứa đáp án đúng (top_k nhỏ / lệch từ khóa).",
            "context_precision": "Tài liệu liên quan không được xếp hạng cao trong kết quả truy xuất.",
            "faithfulness": "Generator có thể đã suy diễn/thêm thông tin ngoài ngữ cảnh được cấp.",
            "answer_relevancy": "Câu trả lời lạc đề hoặc dài dòng, chưa đi thẳng vào câu hỏi.",
        }
        for i, (_, row) in enumerate(low_df.iterrows(), start=1):
            sub_scores = {m: row[m] for m in present_metrics if pd.notna(row[m])}
            worst_metric = min(sub_scores, key=sub_scores.get) if sub_scores else "N/A"
            worst_val = sub_scores.get(worst_metric, float("nan"))
            q_short = str(row["question"])[:70].replace("|", "/")
            lines.append(
                f"| {i} | {q_short}... | {row.get('usecase','')} | {row.get('difficulty','')} | "
                f"{labels.get(worst_metric, worst_metric)} | {_fmt_vn(worst_val)} | "
                f"{cause_map.get(worst_metric, '')} |"
            )
        lines.append("")

    lines.append("## 5. Đề xuất tối ưu hóa hệ thống\n")
    lines.append(OPTIMIZATION_TABLE)

    if n_failed:
        lines.append("\n## 6. Câu hỏi bị lỗi khi chấm điểm Ragas (không có trong bảng trên)\n")
        lines.append(
            f"Có **{n_failed}/{len(df)}** câu hỏi Model Judger không chấm được (timeout/lỗi định dạng "
            "phản hồi...), KHÔNG được tính vào điểm trung bình ở mục 1. Xem chi tiết lỗi trong "
            "`outputs/buoi16_error_log.txt`. Nên chạy lại script để chấm bù các câu này.\n"
        )
        lines.append("| # | Câu hỏi | Use case | Độ khó |")
        lines.append("| :---: | :--- | :--- | :--- |")
        for i, (_, row) in enumerate(df[failed_mask].iterrows(), start=1):
            q_short = str(row["question"])[:80].replace("|", "/")
            lines.append(f"| {i} | {q_short}... | {row.get('usecase','')} | {row.get('difficulty','')} |")
        lines.append("")

    lines.append("\n## 7. Ghi chú vận hành\n")
    lines.append(
        "- Judger (Evaluator) dùng model **khác** với Generator để tránh "
        "*Self-preference bias* — đúng chuẩn công nghiệp LLM-as-a-judge.\n"
        "- Nếu điểm Context Recall thấp mà tăng `top_k` thì Faithfulness có thể "
        "giảm (ngữ cảnh dài → nhiễu) — cần cân bằng qua thử nghiệm A/B `top_k`.\n"
        "- Dữ liệu đưa vào Judger là văn bản quy phạm pháp luật ngân hàng (đã công "
        "khai), phù hợp gọi qua API công cộng; với tài liệu nội bộ nhạy cảm hơn nên "
        "cân nhắc triển khai Judger nội bộ/offline theo chính sách an toàn thông tin "
        "của Agribank."
    )

    report = "\n".join(lines)
    config.OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = config.OUTPUTS_DIR / "ragas_evaluation_report.md"
    out_path.write_text(report, encoding="utf-8")
    print(f"  -> Da luu bao cao vao {out_path.relative_to(BASE_DIR)}")
    return report


# =========================================================================
def main() -> None:
    t0 = time.time()
    try:
        qa_df = generate_golden_dataset()
        rag_df = run_rag_pipeline(qa_df)
        scored_df = run_ragas_evaluation(rag_df)
        report = build_report(scored_df)
    except Exception as exc:  # noqa: BLE001
        log_error("main", exc)
        print(f"\n[LOI NGHIEM TRONG] {type(exc).__name__}: {exc}")
        print(f"Chi tiet da duoc ghi vao {ERROR_LOG}")
        raise

    present_metrics = [m for m in METRIC_COLS if m in scored_df.columns]
    print("\n" + "=" * 70)
    print("KET QUA TRUNG BINH 4 METRICS RAGAS")
    print("=" * 70)
    for m in present_metrics:
        print(f"  {m:<20s}: {scored_df[m].mean():.4f}")
    print(f"\nThoi gian chay: {time.time() - t0:.1f}s")
    print("\n" + "=" * 70)
    print("BAO CAO MAU (outputs/ragas_evaluation_report.md)")
    print("=" * 70)
    print(report[:3000])


if __name__ == "__main__":
    main()
