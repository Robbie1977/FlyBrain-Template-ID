#!/usr/bin/env python3
"""Update per-job alignment progress JSON.

Called by align_single_cmtk.sh at each stage boundary to record
timing and current stage in corrected/{image_base}_alignment_progress.json.

Usage:
    python3 update_alignment_progress.py <image_base> start
    python3 update_alignment_progress.py <image_base> stage_start <stage_name>
    python3 update_alignment_progress.py <image_base> stage_end <stage_name>
    python3 update_alignment_progress.py <image_base> complete
    python3 update_alignment_progress.py <image_base> fail "<error_message>"
"""

import json
import os
import sys
from datetime import datetime, timezone

PROGRESS_DIR = "corrected"


def get_progress_file(image_base):
    return os.path.join(PROGRESS_DIR, f"{image_base}_alignment_progress.json")


def read_progress(image_base):
    filepath = get_progress_file(image_base)
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return {
        "image_base": image_base,
        "stages": {},
        "current_stage": None,
        "started_at": None,
        "completed_at": None,
        "failed_at": None,
        "error": None
    }


def write_progress(image_base, data):
    filepath = get_progress_file(image_base)
    os.makedirs(PROGRESS_DIR, exist_ok=True)
    tmp = filepath + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, filepath)


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def main():
    if len(sys.argv) < 3:
        print("Usage: update_alignment_progress.py <image_base> <action> [args...]")
        print("Actions:")
        print("  start                    - Mark alignment as started")
        print("  stage_start <stage_name> - Mark a stage as started")
        print("  stage_end <stage_name>   - Mark a stage as completed")
        print("  complete                 - Mark alignment as completed")
        print("  fail <error_message>     - Mark alignment as failed")
        sys.exit(1)

    image_base = sys.argv[1]
    action = sys.argv[2]

    data = read_progress(image_base)
    now = now_iso()

    if action == "start":
        data["started_at"] = now
        data["current_stage"] = "initializing"
        data["completed_at"] = None
        data["failed_at"] = None
        data["error"] = None

    elif action == "stage_start":
        stage_name = sys.argv[3]
        data["current_stage"] = stage_name
        if "stages" not in data:
            data["stages"] = {}
        data["stages"][stage_name] = {
            "started_at": now,
            "completed_at": None,
            "duration_seconds": None
        }

    elif action == "stage_end":
        stage_name = sys.argv[3]
        if "stages" not in data:
            data["stages"] = {}
        if stage_name in data["stages"] and data["stages"][stage_name].get("started_at"):
            started = datetime.fromisoformat(
                data["stages"][stage_name]["started_at"].replace("Z", "+00:00")
            )
            ended = datetime.now(timezone.utc)
            duration = (ended - started).total_seconds()
            data["stages"][stage_name]["completed_at"] = now
            data["stages"][stage_name]["duration_seconds"] = round(duration, 1)
        else:
            data["stages"][stage_name] = {
                "started_at": now,
                "completed_at": now,
                "duration_seconds": 0
            }

    elif action == "complete":
        data["current_stage"] = "completed"
        data["completed_at"] = now

    elif action == "fail":
        error_msg = sys.argv[3] if len(sys.argv) > 3 else "Unknown error"
        data["current_stage"] = "failed"
        data["failed_at"] = now
        data["error"] = error_msg

    else:
        print(f"Unknown action: {action}")
        sys.exit(1)

    write_progress(image_base, data)


if __name__ == "__main__":
    main()
