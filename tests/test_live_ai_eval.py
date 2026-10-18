from haha_media.model_router import CallEvidence, ModelCallError
from scripts.run_live_ai_eval import _evaluate_case


class FailingBudgetRouter:
    class Status:
        text_ready = True

    def status(self):
        return self.Status()

    def generate_json(self, *args, **kwargs):
        raise ModelCallError(
            "truncated response",
            evidence=CallEvidence(
                provider="deepseek",
                model="deepseek-flash",
                request_id="request-test",
                latency_ms=10,
                input_tokens=1120,
                output_tokens=600,
                status="failed",
            ),
        )


def test_failed_live_call_keeps_consumed_token_cost() -> None:
    case = {
        "id": "cost-evidence",
        "craft": "测试技艺",
        "story_seed": "测试现场",
        "audience": "文化爱好者",
        "platform": "B站",
        "tone": "纪录片",
        "duration": "45秒",
        "aspect_ratio": "9:16",
    }

    result = _evaluate_case(case, "deepseek-flash", FailingBudgetRouter())

    assert result["status"] == "failed"
    assert result["evidence"]["input_tokens"] == 1120
    assert result["evidence"]["output_tokens"] == 600
    assert result["estimated_peak_cost_usd"] == 0.001056
