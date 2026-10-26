import json, os, sys, time
from typing import Literal

from pydantic import BaseModel

from agent import ask, llm
from baseline import basic_rag

RESULTS = "results.json"
SCORE = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}


class Verdict(BaseModel):
    verdict: Literal["correct", "partial", "incorrect"]


def with_retry(fn, *args, tries=5):
    """Retry on free-tier rate limits (429 / quota errors)."""
    for i in range(tries):
        try:
            return fn(*args)
        except Exception as e:
            msg = str(e).lower()
            if "429" in msg or "quota" in msg or "resource_exhausted" in msg:
                wait = 30 * (i + 1)
                print(f"   rate limited, waiting {wait}s ...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("too many rate-limit retries")


def judge(question, reference, answer):
    prompt = (
        "You are grading an answer against a reference answer.\n"
        f"Question: {question}\nReference: {reference}\nAnswer: {answer}\n\n"
        "correct = the answer contains the key information of the reference and nothing contradicting it.\n"
        "partial = it contains some of the key information but misses or muddles important parts.\n"
        "incorrect = it is wrong, off-topic, or declines to answer.\n"
        "Special case: if the reference says the assistant should decline, then declining is correct "
        "and inventing an answer is incorrect."
    )
    return with_retry(lambda: llm.with_structured_output(Verdict).invoke(prompt)).verdict


def run_one(t):
    t0 = time.time()
    base_answer, _ = with_retry(basic_rag, t["question"])
    t_base = time.time() - t0

    t0 = time.time()
    res = with_retry(ask, t["question"])
    t_agent = time.time() - t0

    return {
        "type": t["type"], "question": t["question"], "reference": t["reference"],
        "baseline_answer": base_answer, "agent_answer": res["generation"],
        "route": res.get("route", ""), "retries": res.get("retries", 0),
        "agent_steps": len(res["steps"]),
        "t_base": round(t_base, 1), "t_agent": round(t_agent, 1),
        "baseline_verdict": judge(t["question"], t["reference"], base_answer),
        "agent_verdict": judge(t["question"], t["reference"], res["generation"]),
    }


def summarize(rows):
    def mean(xs):
        return sum(xs) / len(xs) if xs else 0.0

    print("\n=== Correctness (1 = correct, 0.5 = partial, 0 = incorrect) ===")
    print(f"{'type':<14}{'n':>3}{'baseline':>10}{'agent':>8}{'t_base':>8}{'t_agent':>9}")
    for typ in sorted({r["type"] for r in rows}) + ["ALL"]:
        sub = rows if typ == "ALL" else [r for r in rows if r["type"] == typ]
        print(f"{typ:<14}{len(sub):>3}"
              f"{mean([SCORE[r['baseline_verdict']] for r in sub]):>10.2f}"
              f"{mean([SCORE[r['agent_verdict']] for r in sub]):>8.2f}"
              f"{mean([r['t_base'] for r in sub]):>7.1f}s"
              f"{mean([r['t_agent'] for r in sub]):>8.1f}s")

    retried = [r for r in rows if r["retries"] > 0]
    print(f"\nQuestions where the agent retried: {len(retried)}/{len(rows)}")
    if retried:
        print(f"  avg score on those - baseline {mean([SCORE[r['baseline_verdict']] for r in retried]):.2f}, "
              f"agent {mean([SCORE[r['agent_verdict']] for r in retried]):.2f}")
    gave_up = [r for r in rows if "couldn't find" in r["agent_answer"].lower()]
    print(f"Agent gave up / found nothing: {len(gave_up)}/{len(rows)}")


if __name__ == "__main__":
    tests = json.load(open("test_set.json", encoding="utf-8"))
    rows = json.load(open(RESULTS, encoding="utf-8")) if os.path.exists(RESULTS) else []

    if "summary" not in sys.argv:
        limit = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else len(tests)
        done = {r["question"] for r in rows}
        for i, t in enumerate(tests[:limit], 1):
            if t["question"] in done:
                continue
            print(f"[{i}/{limit}] {t['type']}: {t['question']}")
            rows.append(run_one(t))
            json.dump(rows, open(RESULTS, "w", encoding="utf-8"), indent=2)
            time.sleep(3)

    summarize(rows)
