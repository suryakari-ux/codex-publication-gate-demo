import json
import os
from pathlib import Path

from openai_codex import Codex, Sandbox


# The workflow runs this file from the repository root.
REPO_ROOT = Path(__file__).parent
DOCS_DIR = REPO_ROOT / "docs"
CODEX_MODEL = "gpt-5.6-sol"


# This is the predictable answer GitHub will act on.
DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {
            "type": "string",
            "enum": ["proceed", "hold", "needs_human_review"],
        },
        "reason": {"type": "string"},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "next_action": {"type": "string"},
    },
    "required": ["decision", "reason", "evidence", "next_action"],
    "additionalProperties": False,
}


def read_document(name: str) -> str:
    '''Read one trusted document from the repository.'''
    return (DOCS_DIR / name).read_text(encoding="utf-8")


def build_prompt() -> str:
    '''Give Codex the rules, approved facts, and proposed public text.'''
    return f'''Review the proposed public release notes against the approved sources.

Return only the requested JSON decision.

Rules:
{read_document("publishing_policy.md")}

Approved features:
{read_document("approved_features.md")}

Approved compliance statements:
{read_document("compliance_status.md")}

Proposed release notes:
{read_document("release_notes.md")}
'''


def review_release_notes() -> dict:
    '''Run one read-only Codex review and parse its structured answer.'''
    with Codex() as codex:
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            codex.login_api_key(api_key)

        thread = codex.thread_start(
            cwd=str(REPO_ROOT),
            model=CODEX_MODEL,
            sandbox=Sandbox.read_only,
        )
        result = thread.run(
            build_prompt(),
            output_schema=DECISION_SCHEMA,
            sandbox=Sandbox.read_only,
        )

    if result.final_response is None:
        raise RuntimeError("Codex completed without a final response.")
    return json.loads(result.final_response)


if __name__ == "__main__":
    report = review_release_notes()
    Path("publication_gate_report.json").write_text(
        json.dumps(report, indent=2) + chr(10),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))

    # GitHub shows exit code 0 as green and exit code 1 as red.
    raise SystemExit(0 if report["decision"] == "proceed" else 1)
