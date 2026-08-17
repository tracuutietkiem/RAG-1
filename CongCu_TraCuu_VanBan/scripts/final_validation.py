#!/usr/bin/env python3
"""
Kiem tra cuoi buoi theo checklist muc 26 cua de bai.

Output: buoi_14/outputs/final_validation_report.md
"""

import csv
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config  # noqa: E402
from src import corpus, hybrid_retriever, pipeline, reranker  # noqa: E402

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

QUERY = "Ai có thẩm quyền quyết định cấp tín dụng vượt hạn mức?"


def check(name: str, fn) -> tuple[str, bool, str]:
    try:
        ok, detail = fn()
        return name, ok, detail
    except Exception as exc:  # noqa: BLE001
        return name, False, f"{type(exc).__name__}: {str(exc)[:160]}"


def main() -> int:
    checks: list[tuple[str, bool, str]] = []

    def c_corpus():
        rows = corpus.load_chunks()
        ids = [r["chunk_id"] for r in rows]
        return (len(ids) == len(set(ids)) and len(rows) > 100,
                f"{len(rows)} chunk / {len({r['document_id'] for r in rows})} van ban, "
                f"chunk_id duy nhat")

    def c_files():
        need = [
            "scripts/inspect_project.py", "scripts/prepare_corpus.py",
            "scripts/baseline_retrieval.py", "scripts/hybrid_search.py",
            "scripts/rerank.py", "scripts/compare_retrieval.py",
            "scripts/load_mini_kg.py", "scripts/query_demo.py",
            "src/bm25_retriever.py", "src/dense_retriever.py",
            "src/hybrid_retriever.py", "src/reranker.py", "src/citation.py",
            "src/pipeline.py", "cypher/schema.cypher", "cypher/demo_queries.cypher",
            "app.py", "requirements.txt", "README.md", ".env.example",
            "data/processed/chunks_normalized.csv", "data/eval/questions.csv",
            "outputs/inspection_report.md", "outputs/retrieval_examples.md",
            "outputs/retrieval_comparison.csv", "outputs/evaluation_report.md",
            "outputs/kg_build_report.md", "tests/test_retrieval.py",
        ]
        missing = [f for f in need if not (config.BASE_DIR / f).exists()]
        return not missing, f"thieu: {missing}" if missing else f"du {len(need)} file bat buoc"

    def c_bm25():
        r = pipeline.retrieve(QUERY, "bm25", 5)["results"]
        return bool(r), f"{len(r)} ket qua"

    def c_dense():
        r = pipeline.retrieve(QUERY, "dense", 5)["results"]
        return bool(r), f"{len(r)} ket qua"

    def c_hybrid_dung_ca_hai():
        r = hybrid_retriever.get_retriever().search(QUERY, top_k=5, candidate_k=20)
        has_bm = any(x.get("bm25_rank") for x in r)
        has_dn = any(x.get("dense_rank") for x in r)
        return has_bm and has_dn, f"bm25_rank={has_bm}, dense_rank={has_dn}"

    def c_fusion_khong_cong_raw():
        src = (config.BASE_DIR / "src/hybrid_retriever.py").read_text(encoding="utf-8")
        return ("RRF_K" in src and "retrieval_score + " not in src,
                "dung RRF tren THU HANG, khong cong thang BM25 score voi cosine")

    def c_rerank_chi_candidate():
        cands = hybrid_retriever.get_retriever().candidates(QUERY, candidate_k=15)
        out = reranker.get_reranker().rerank(QUERY, cands, top_k=5)
        subset = {x["chunk_id"] for x in out}.issubset({c["chunk_id"] for c in cands})
        return (subset and len(cands) <= 15,
                f"candidate={len(cands)} -> top={len(out)}, ket qua nam trong candidate")

    def c_before_after():
        out = pipeline.retrieve(QUERY, "hybrid_rerank", 5, 20)
        before = [x["chunk_id"] for x in out["before_rerank"][:5]]
        after = [x["chunk_id"] for x in out["results"]]
        return (bool(before) and bool(after),
                f"co ca BEFORE ({len(out['before_rerank'])}) va AFTER ({len(after)}); "
                f"thu tu {'CO doi' if before != after else 'khong doi'}")

    def c_citation():
        bad = []
        for m in pipeline.METHODS:
            for r in pipeline.retrieve(QUERY, m, 5)["results"]:
                if not (r.get("citation") and r.get("chunk_id") and r.get("document_id")):
                    bad.append((m, r.get("chunk_id")))
        return not bad, "citation con nguyen o ca 4 method" if not bad else f"thieu: {bad}"

    def c_evaluation():
        p = config.OUTPUTS_DIR / "retrieval_comparison.csv"
        rows = list(csv.DictReader(open(p, encoding="utf-8")))
        methods = {r["method"] for r in rows}
        qs = {r["question_id"] for r in rows}
        return (methods == set(pipeline.METHODS),
                f"{len(qs)} cau hoi x {len(methods)} cau hinh = {len(rows)} dong")

    def c_gold_xac_minh():
        idx = corpus.chunk_index()
        rows = list(csv.DictReader(open(config.QUESTIONS_CSV, encoding="utf-8")))
        bad = [r["question_id"] for r in rows if r["expected_chunk_id"] not in idx]
        return not bad, ("moi gold deu ton tai trong corpus" if not bad else f"gold sai: {bad}")

    def c_kg_co_can_cu():
        """
        Kiem tra CHUOI CYPHER THUC SU DUOC CHAY, khong bat nham dong ghi chu
        canh bao trong docstring. Dung ast de lay cac string literal that su
        duoc dung lam lenh, bo qua docstring cua module/ham/class.
        """
        import ast

        path = config.BASE_DIR / "scripts/load_mini_kg.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                d = ast.get_docstring(node, clean=False)
                if d:
                    docstrings.add(d)

        # Chi soi cac string THUC SU duoc dung lam lenh Cypher, tuc la doi so
        # cua session.run(...). Cac chuoi khac (docstring, dong van ban ghi vao
        # bao cao Markdown) khong phai lenh chay -> khong tinh.
        cypher_args: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            is_run = isinstance(fn, ast.Attribute) and fn.attr == "run"
            if not is_run:
                continue
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    cypher_args.append(arg.value)
                elif isinstance(arg, ast.JoinedStr):  # f-string
                    parts = [
                        v.value for v in arg.values
                        if isinstance(v, ast.Constant) and isinstance(v.value, str)
                    ]
                    cypher_args.append("".join(parts))

        unguarded = [
            s.strip()[:70] for s in cypher_args
            if "DETACH DELETE" in s.upper() and "lab_session" not in s
        ]

        # Cypher file: lenh xoa phai bi comment (//) hoac co lab_session
        cy = (config.BASE_DIR / "cypher/demo_queries.cypher").read_text(encoding="utf-8")
        for line in cy.splitlines():
            t = line.strip()
            if "DETACH DELETE" in t.upper() and not t.startswith("//") and "lab_session" not in t:
                unguarded.append(f"demo_queries.cypher: {t[:60]}")

        has_lab = "lab_session" in path.read_text(encoding="utf-8")
        ok = not unguarded and has_lab
        return ok, (
            f"moi lenh DETACH DELETE deu bi rang buoc lab_session; "
            f"gan lab_session='buoi_14'={has_lab}"
            if ok else f"lenh xoa khong duoc bao ve: {unguarded}"
        )

    def c_khong_ghi_nguon():
        outside = not str(config.KB_DIR).startswith(str(config.BASE_DIR))
        inside = all(
            str(p).startswith(str(config.BASE_DIR))
            for p in (config.CHUNKS_CSV, config.QUESTIONS_CSV, config.OUTPUTS_DIR,
                      config.CACHE_DIR)
        )
        return outside and inside, "moi output nam trong buoi_14/, KB_DIR chi doc"

    def c_tests():
        r = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
            cwd=config.BASE_DIR, capture_output=True, text=True,
        )
        tail = (r.stderr or r.stdout).strip().splitlines()
        return r.returncode == 0, tail[-1] if tail else "?"

    def c_streamlit():
        try:
            import streamlit  # noqa: F401
        except ImportError:
            return False, "chua cai streamlit"
        src = (config.BASE_DIR / "app.py").read_text(encoding="utf-8")
        return ("pipeline.retrieve" in src,
                "app.py goi dung src.pipeline.retrieve (khong viet lai pipeline rieng)")

    for name, fn in [
        ("Corpus da chuan hoa", c_corpus),
        ("Du file nop bai", c_files),
        ("BM25 co ket qua", c_bm25),
        ("Dense co ket qua", c_dense),
        ("Hybrid dung CA HAI retriever (bm25_rank + dense_rank)", c_hybrid_dung_ca_hai),
        ("Fusion khong cong raw score sai cach", c_fusion_khong_cong_raw),
        ("Reranker chi xu ly candidate cua Hybrid", c_rerank_chi_candidate),
        ("Co Before/After Rerank", c_before_after),
        ("Citation khong bi mat", c_citation),
        ("Co evaluation cho ca 4 cau hinh", c_evaluation),
        ("Gold cua bo cau hoi xac minh duoc", c_gold_xac_minh),
        ("Mini KG co can cu + khong xoa graph buoi truoc", c_kg_co_can_cu),
        ("Khong ghi vao du lieu nguon", c_khong_ghi_nguon),
        ("Test tu dong pass", c_tests),
        ("Streamlit dung dung pipeline", c_streamlit),
    ]:
        checks.append(check(name, fn))

    bk = pipeline.backend_info()
    passed = sum(1 for _, ok, _ in checks if ok)
    ready = passed == len(checks)

    L: list[str] = []
    add = L.append
    add("# Bao cao validation cuoi - Buoi 14\n")
    add(f"- Working root: `{config.BASE_DIR}`")
    add(f"- Du lieu nguon (chi doc): `{config.KB_DIR}`\n")

    add("## Backend thuc te\n")
    add(f"- Dense: `{bk['dense_backend']}` — "
        f"**{'NEURAL' if bk['dense_is_neural'] else 'FALLBACK (khong phai neural embedding)'}**")
    add(f"- Reranker: `{bk['rerank_backend']}` — "
        f"**{'NEURAL' if bk['rerank_is_neural'] else 'FALLBACK (khong phai neural cross-encoder)'}**\n")

    add("## Checklist\n")
    add("| # | Muc kiem tra | Ket qua | Chi tiet |")
    add("|---|---|---|---|")
    for i, (name, ok, detail) in enumerate(checks, start=1):
        add(f"| {i} | {name} | {'PASS' if ok else 'FAIL'} | {detail} |")
    add("")
    add(f"**{passed}/{len(checks)} muc PASS**\n")

    add("## Ket luan\n")
    add("```")
    add(f"READY FOR DEMO: {'YES' if ready else 'NO'}")
    add("```")
    if not bk["dense_is_neural"] or not bk["rerank_is_neural"]:
        add("\n> Luu y trung thuc: pipeline dang chay o che do FALLBACK cho "
            f"{'Dense' if not bk['dense_is_neural'] else ''}"
            f"{' va ' if (not bk['dense_is_neural'] and not bk['rerank_is_neural']) else ''}"
            f"{'Reranker' if not bk['rerank_is_neural'] else ''}. "
            "Cau truc pipeline va toan bo kiem tra o tren van dung, nhung so lieu chat "
            "luong chua phai cua model neural. Tren may co tai duoc model tu HuggingFace, "
            "dat `DENSE_BACKEND=sentence_transformers` va `RERANKER_BACKEND=cross_encoder` "
            "trong `.env` roi chay lai `scripts/compare_retrieval.py`.")

    out = config.OUTPUTS_DIR / "final_validation_report.md"
    out.write_text("\n".join(L), encoding="utf-8")

    print("=" * 78)
    print("FINAL VALIDATION")
    print("=" * 78)
    for name, ok, detail in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        if not ok:
            print(f"         -> {detail}")
    print()
    print(f"{passed}/{len(checks)} PASS")
    print(f"READY FOR DEMO: {'YES' if ready else 'NO'}")
    print(f"Da ghi: {out.relative_to(config.BASE_DIR)}")
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
