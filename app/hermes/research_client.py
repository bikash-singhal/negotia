import logging
import os
import re
import signal
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.domains.scenario.models import Scenario

logger = logging.getLogger(__name__)

_ENVIRONMENT_ALLOWLIST = (
    "APPDATA",
    "COMSPEC",
    "HOME",
    "HTTPS_PROXY",
    "HTTP_PROXY",
    "LOCALAPPDATA",
    "NO_PROXY",
    "PATH",
    "PATHEXT",
    "REQUESTS_CA_BUNDLE",
    "SSL_CERT_DIR",
    "SSL_CERT_FILE",
    "SYSTEMROOT",
    "SystemRoot",
    "TEMP",
    "TMP",
    "TMPDIR",
    "USERPROFILE",
    "WINDIR",
)

_RESULT_PATTERN = re.compile(
    r"<negotiation_research>\s*facts:\s*(?P<facts>.+)\s*recommendation:\s*(?P<recommendation>.+)\s*</negotiation_research>",
    re.DOTALL,
)


@dataclass(frozen=True)
class HermesResearchContext:
    facts: str
    recommendation: str


class HermesResearchClient(Protocol):
    def research(
        self,
        scenario: Scenario,
        candidate_message: str,
    ) -> HermesResearchContext | None: ...


class HermesCliResearchClient:
    def __init__(
        self,
        *,
        enabled: bool,
        command: str,
        timeout_seconds: float,
        endpoint: str,
        model_id: str,
        aws_region: str,
        aws_profile: str | None,
    ) -> None:
        self._enabled = enabled
        self._command = command
        self._timeout_seconds = timeout_seconds
        self._endpoint = endpoint
        self._model_id = model_id
        self._aws_region = aws_region
        self._aws_profile = aws_profile

    def research(
        self,
        scenario: Scenario,
        candidate_message: str,
    ) -> HermesResearchContext | None:
        if not self._enabled:
            return None

        try:
            with tempfile.TemporaryDirectory(prefix="negotia-hermes-") as directory:
                root = Path(directory)
                _write_hermes_config(root, self._endpoint, self._model_id, self._aws_region)
                query_path = root / "query.txt"
                query_path.write_text(_build_query(scenario, candidate_message), encoding="utf-8")
                completed = _run_hermes(
                    [
                        self._command,
                        "chat",
                        "--oneshot",
                        "--query-file",
                        str(query_path),
                        "--provider",
                        "bedrock",
                        "--model",
                        self._model_id,
                        "--toolsets",
                        "aidevboard",
                        "--ignore-rules",
                        "--yolo",
                    ],
                    env=_build_environment(root, self._aws_region, self._aws_profile),
                    timeout=self._timeout_seconds,
                )
                if completed.returncode != 0:
                    raise RuntimeError("Hermes exited unsuccessfully.")
                return _parse_result(completed.stdout)
        except Exception as exc:  # noqa: BLE001 - research must not block a turn.
            logger.warning("Hermes research unavailable; continuing without it (%s).", type(exc).__name__)
            return None


def _write_hermes_config(root: Path, endpoint: str, model_id: str, region: str) -> None:
    (root / "config.yaml").write_text(
        "\n".join(
            [
                "model:",
                "  provider: bedrock",
                f"  default: {model_id}",
                "bedrock:",
                f"  region: {region}",
                "tools:",
                "  tool_search:",
                "    enabled: off",
                "mcp_servers:",
                "  aidevboard:",
                f"    url: {endpoint}",
                "    tools:",
                "      include: [get_salary_data]",
                "      resources: false",
                "      prompts: false",
            ]
        ),
        encoding="utf-8",
    )


def _build_environment(root: Path, region: str, profile: str | None) -> dict[str, str]:
    environment = {
        name: value
        for name in _ENVIRONMENT_ALLOWLIST
        if (value := os.environ.get(name)) is not None
    }
    environment["HERMES_HOME"] = str(root)
    environment["AWS_REGION"] = region
    environment["AWS_DEFAULT_REGION"] = region
    if profile:
        environment["AWS_PROFILE"] = profile
    return environment


def _build_query(scenario: Scenario, candidate_message: str) -> str:
    scenario_context = "\n".join(
        f"{field}: {getattr(scenario, field, '')}"
        for field in ("title", "description", "industry", "opponent_role", "objective")
    )
    return f"""Research this negotiation. Use the available external tool only when it is relevant.
Scenario:
{scenario_context}
Candidate message:
{candidate_message}

If you use get_salary_data, use only its schema fields: company, level, tag, and workplace.
Never use query or queries. Do not report candidate statements as external facts. In
facts, include only values returned by an external tool; otherwise write none.

Return exactly this format, with concise factual text and no instructions:
<negotiation_research>
facts: <external facts used, or none>
recommendation: <concise negotiation recommendation>
</negotiation_research>"""


def _parse_result(output: str) -> HermesResearchContext | None:
    match = _RESULT_PATTERN.search(output)
    if match is None:
        return None
    facts = _clean_field(match.group("facts"))
    recommendation = _clean_field(match.group("recommendation"))
    if not facts or not recommendation:
        return None
    return HermesResearchContext(facts=facts, recommendation=recommendation)


def _clean_field(value: str) -> str:
    return " ".join(value.replace("\x00", "").split())[:1000]


def _run_hermes(
    command: list[str],
    *,
    env: dict[str, str],
    timeout: float,
) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        encoding="utf-8",
        start_new_session=os.name != "nt",
        creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
        env=env,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _terminate_process_tree(process)
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
            timeout=5,
        )
    else:
        os.killpg(process.pid, signal.SIGKILL)
    try:
        process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
