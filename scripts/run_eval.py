import json
from pathlib import Path

from app.langgraph_agent import answer_with_langgraph


REPO_PATH = "data/repos/SimpleFastPyAPI"
EVAL_FILE = Path("eval/eval_cases.json")


def contains_any_keyword(answer: str, keywords: list[str]) -> bool:
    lowered_answer = answer.lower()

    return any(
        keyword.lower() in lowered_answer
        for keyword in keywords
    )


def main():
    cases = json.loads(EVAL_FILE.read_text(encoding="utf-8"))

    total = len(cases)
    passed = 0

    for case in cases:
        case_id = case["id"]
        question = case["question"]
        expected_keywords = case.get("expected_keywords", [])
        require_sources = case.get("require_sources", False)

        print(f"\n[Eval] Running {case_id}")
        print(f"[Eval] Question: {question}")

        try:
            answer = answer_with_langgraph(
                repo_path=REPO_PATH,
                question=question,
            )
        except Exception as exc:
            print(f"[FAIL] {case_id} - exception: {exc}")
            continue

        checks = []

        if answer.strip():
            checks.append(True)
        else:
            print(f"[FAIL] {case_id} - empty answer")
            checks.append(False)

        if expected_keywords:
            keyword_ok = contains_any_keyword(answer, expected_keywords)
            if not keyword_ok:
                print(
                    f"[FAIL] {case_id} - missing expected keywords: "
                    f"{expected_keywords}"
                )
            checks.append(keyword_ok)

        if require_sources:
            source_ok = "参考文件" in answer
            if not source_ok:
                print(f"[FAIL] {case_id} - missing source citations")
            checks.append(source_ok)

        if all(checks):
            passed += 1
            print(f"[PASS] {case_id}")
        else:
            print(f"[FAIL] {case_id}")

        print("[Eval] Answer preview:")
        print(answer[:500])

    print(f"\n[Eval] Passed {passed}/{total}")


if __name__ == "__main__":
    main()