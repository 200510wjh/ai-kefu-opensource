from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    scripts = package.get("scripts", {})
    build = package.get("build", {})
    dev_deps = package.get("devDependencies", {})

    require(package.get("main") == "desktop/electron/main.cjs", "package main must point to Electron main file")
    require("electron" in dev_deps, "electron dev dependency missing")
    require("electron-builder" in dev_deps, "electron-builder dev dependency missing")
    require(scripts.get("desktop:mac") == "electron-builder --mac dmg zip", "desktop:mac script missing")
    require(scripts.get("desktop:preview") == "electron .", "desktop:preview script missing")

    require(build.get("appId") == "cn.wjhai.merchant-ai", "mac appId mismatch")
    require(build.get("productName") == "商家AI增长工作台", "productName mismatch")
    require("dmg" in build.get("mac", {}).get("target", []), "mac dmg target missing")
    require("zip" in build.get("mac", {}).get("target", []), "mac zip target missing")

    required_files = [
        "desktop/electron/main.cjs",
        "desktop/electron/preload.cjs",
        "scripts/build_mac_installer.sh",
        "运营计划/今日交付包/Mac安装包打包说明.md",
    ]
    for item in required_files:
        require((ROOT / item).exists(), f"Missing file: {item}")

    for js_file in ["desktop/electron/main.cjs", "desktop/electron/preload.cjs"]:
        subprocess.run(["node", "-c", str(ROOT / js_file)], check=True)

    print(json.dumps({
        "status": "passed",
        "productName": build.get("productName"),
        "appId": build.get("appId"),
        "macTargets": build.get("mac", {}).get("target", []),
        "note": "Run npm run desktop:mac on macOS to generate dmg/zip."
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
