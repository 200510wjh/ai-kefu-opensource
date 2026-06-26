import json
import sys
import time
import urllib.request


BASE_URL = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "https://wjhai.cn/merchant-admin"


def get_json(path: str):
    with urllib.request.urlopen(BASE_URL + path, timeout=25) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def post_json(path: str, payload: dict):
    request = urllib.request.Request(
        BASE_URL + path,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=45) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def main() -> int:
    brief = {
        "industry": "本地健身房",
        "product_name": "夏季减脂体验课",
        "selling_points": "7天体验, 私教评估, 到店领体测报告",
        "platform": "抖音",
        "video_type": "local_promo",
        "segment": "local_merchant",
        "generation_kind": "short_video",
        "style": "clean",
        "budget_mode": "balanced",
        "audience": "附近3公里想减脂的新客",
        "call_to_action": "私信领取7天体验课",
    }
    reply_payload = {
        "channel": "douyin_dm",
        "scenario": "抖音私信咨询健身体验课",
        "conversation": "客户：你们这个体验课多少钱？我怕去了被推销。",
        "goal": "缓解顾虑并引导留下联系方式",
        "tone": "high_eq",
        "recipient_profile": "附近想减脂的新客",
    }

    results = {}
    results["health"] = get_json("/api/health")[1]["status"]
    results["diagnostics"] = get_json("/api/system/diagnostics")[1]["status"]
    results["providers"] = get_json("/api/providers")[1]["mode"]

    _, scripts = post_json("/api/scripts", brief)
    results["scripts"] = {"count": len(scripts), "scenes": len(scripts[0]["scenes"])}

    render_payload = {
        "brief": brief,
        "script": scripts[0],
        "generation_kind": "short_video",
        "variant_count": 1,
    }
    results["hyperframes"] = post_json("/api/hyperframes/render-plan", render_payload)[1]["template"]
    service_kit = post_json("/api/workflow/script-customer-service", render_payload)[1]
    results["script_customer_service"] = {
        "opening": len(service_kit["opening_messages"]),
        "qualification": len(service_kit["qualification_flow"]),
        "objections": len(service_kit["objection_handling"]),
        "closing": len(service_kit["closing_messages"]),
    }
    _, image_result = post_json("/api/images/generate", {"brief": brief, "image_kind": "main_image"})
    results["image_generation"] = {
        "mode": image_result["mode"],
        "has_prompt": bool(image_result["prompt"]),
        "has_image": bool(image_result.get("image_url") or image_result.get("artifact_url")),
    }
    results["reply_candidates"] = len(post_json("/api/reply-assistant", reply_payload)[1]["candidates"])

    _, task = post_json("/api/render", render_payload)
    latest = task
    for _ in range(10):
        time.sleep(0.8)
        _, latest = get_json("/api/tasks/" + task["id"])
        if latest["status"] == "done":
            break
    results["render"] = {
        "status": latest["status"],
        "progress": latest["progress"],
        "artifact": bool(latest.get("artifact_url")),
    }

    print(json.dumps(results, ensure_ascii=False, indent=2))
    failures = [
        results["health"] != "ok",
        results["scripts"]["count"] < 3,
        results["scripts"]["scenes"] < 3,
        results["script_customer_service"]["opening"] < 1,
        results["script_customer_service"]["objections"] < 1,
        results["script_customer_service"]["closing"] < 1,
        not results["image_generation"]["has_prompt"],
        results["reply_candidates"] < 3,
        results["render"]["status"] != "done",
        not results["render"]["artifact"],
    ]
    return 1 if any(failures) else 0


if __name__ == "__main__":
    raise SystemExit(main())
