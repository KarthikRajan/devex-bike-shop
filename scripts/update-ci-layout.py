#!/usr/bin/env python3
"""Update all 13 component ci.yml files to use parallel job layout."""

import subprocess
import base64
import json
import sys
import re

REPOS = [
    "bikeshop-db",
    "bikeshop-services",
    "bikeshop-ui",
    "bikeshop-auth",
    "bikeshop-payments",
    "bikeshop-inventory",
    "bikeshop-notifications",
    "bikeshop-analytics",
    "bikeshop-storefront",
    "bikeshop-admin",
    "bikeshop-mobile-api",
    "bikeshop-cdn",
    "bikeshop-docs",
]

ORG = "pdutta25"
PATH = ".github/workflows/ci.yml"

# Map of needs changes: job_pattern -> new_needs
# Current chain: detect → build → lint → test → quality → security → artifact → deploy → telemetry
# New layout:
#   detect → [build, lint, test, quality, security] (all parallel) → artifact → [deploy, telemetry] (parallel)
NEEDS_CHANGES = {
    # lint currently: needs: build → needs: detect
    r"(  lint:\n    name:.*\n    needs:) build": r"\1 detect",
    # test currently: needs: lint → needs: detect
    r"(  test:\n    name:.*\n    needs:) lint": r"\1 detect",
    # quality currently: needs: test → needs: detect
    r"(  quality:\n    name:.*\n    needs:) test": r"\1 detect",
    # security currently: needs: quality → needs: detect
    r"(  security:\n    name:.*\n    needs:) quality": r"\1 detect",
    # artifact currently: needs: [detect, security] → needs: [detect, build, lint, test, quality, security]
    r"(  artifact:\n    name:.*\n    needs:) \[detect, security\]": r"\1 [detect, build, lint, test, quality, security]",
    # telemetry currently: needs: [detect, deploy] → needs: [detect, artifact]
    r"(  telemetry:\n    name:.*\n    needs:) \[detect, deploy\]": r"\1 [detect, artifact]",
}


def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: {result.stderr.strip()}")
        return None
    return result.stdout.strip()


def main():
    for repo in REPOS:
        full_repo = f"{ORG}/{repo}"
        print(f"\n{'='*60}")
        print(f"  {repo}")
        print(f"{'='*60}")

        # Fetch current file
        raw = run(f"gh api repos/{full_repo}/contents/{PATH}")
        if not raw:
            print("  SKIP: Could not fetch file")
            continue

        data = json.loads(raw)
        sha = data["sha"]
        content = base64.b64decode(data["content"]).decode("utf-8")

        # Apply needs changes
        updated = content
        changes_made = 0
        for pattern, replacement in NEEDS_CHANGES.items():
            new_content = re.sub(pattern, replacement, updated)
            if new_content != updated:
                changes_made += 1
                updated = new_content

        if changes_made == 0:
            print("  SKIP: No changes needed")
            continue

        print(f"  Changes: {changes_made} needs: lines updated")

        # Encode and push
        encoded = base64.b64encode(updated.encode("utf-8")).decode("utf-8")
        payload = json.dumps({
            "message": "ci: parallelize build/lint/test/quality/security for compact graph layout",
            "content": encoded,
            "sha": sha,
            "branch": "main"
        })

        result = run(f"gh api repos/{full_repo}/contents/{PATH} -X PUT --input - <<'JSONEOF'\n{payload}\nJSONEOF")
        if result:
            print("  ✅ Pushed successfully")
        else:
            print("  ❌ Push failed")


if __name__ == "__main__":
    main()
