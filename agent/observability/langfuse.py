import hashlib
import json
from collections.abc import Callable
from typing import TypeVar

from agent.config import settings
from agent.schemas.tools import ToolExecutionResult, ToolStatus

try:
    from langfuse import Langfuse
except ImportError:  # pragma: no cover - optional dependency until uv sync installs it
    Langfuse = None

_T = TypeVar("_T")


class LangfuseClient:
    def _is_live_ready(self) -> bool:
        return bool(
            settings.langfuse_public_key
            and settings.langfuse_secret_key
            and settings.langfuse_export_enabled
            and Langfuse
        )

    def _client(self):
        if not self._is_live_ready():
            return None
        return Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )

    def external_trace_id(self, trace_id: str) -> str:
        return hashlib.sha256(trace_id.encode("utf-8")).hexdigest()[:32]

    def trace_url_for(self, trace_id: str | None) -> str | None:
        if not trace_id or not self._is_live_ready():
            return None
        try:
            langfuse = self._client()
            if langfuse is None:
                return None
            return langfuse.get_trace_url(trace_id=self.external_trace_id(trace_id))
        except Exception:
            return None

    def status(self) -> ToolStatus:
        configured = bool(settings.langfuse_public_key and settings.langfuse_secret_key and Langfuse)
        mode = "configured" if configured else "mock"
        details = (
            "Langfuse credentials are present; live export is enabled."
            if configured and settings.langfuse_export_enabled
            else "Langfuse credentials are present; live export is disabled unless LANGFUSE_EXPORT_ENABLED=true."
            if configured
            else "Uses the official Langfuse Python SDK when credentials and the package are installed."
        )
        return ToolStatus(
            name="langfuse",
            label="Langfuse Observability",
            mode=mode,
            configured=configured,
            available=True,
            details=details,
        )

    def mirror_trace(self, trace_id: str, payload: dict, prospect_id: str) -> ToolExecutionResult:
        settings.outbox_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = settings.outbox_dir / f"{prospect_id}_langfuse.json"
        artifact_path.write_text(
            json.dumps(
                {
                    "trace_id": trace_id,
                    "langfuse_host": settings.langfuse_host,
                    "payload": payload,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        status = self.status()
        if status.configured and settings.langfuse_export_enabled and Langfuse:
            try:
                langfuse = self._client()
                if langfuse is None:
                    raise RuntimeError("Langfuse client is not live-ready.")
                external_trace_id = self.external_trace_id(trace_id)
                with langfuse.start_as_current_observation(
                    as_type="span",
                    name="conversion-engine-toolchain",
                    trace_context={"trace_id": external_trace_id},
                ) as span:
                    span.update(
                        input=payload,
                        output={"prospect_id": prospect_id, "internal_trace_id": trace_id},
                        metadata={"prospect_id": prospect_id, "internal_trace_id": trace_id},
                    )
                trace_url = langfuse.get_trace_url(trace_id=external_trace_id)
                langfuse.flush()
                return ToolExecutionResult(
                    name="langfuse",
                    mode="configured",
                    status="executed",
                    message="Trace forwarded to Langfuse successfully.",
                    artifact_ref=str(artifact_path),
                    external_id=trace_url,
                )
            except Exception as exc:
                return ToolExecutionResult(
                    name="langfuse",
                    mode="configured",
                    status="error",
                    message=f"Langfuse trace export failed: {exc}",
                    artifact_ref=str(artifact_path),
                )
        return ToolExecutionResult(
            name="langfuse",
            mode=status.mode,
            status="executed" if status.configured else "previewed",
            message="Trace mirrored to the Langfuse adapter.",
            artifact_ref=str(artifact_path),
        )

    def run_generation(
        self,
        *,
        trace_id: str | None,
        name: str,
        model: str,
        input_payload: dict,
        operation: Callable[[], tuple[_T, dict | None, dict[str, int] | None, dict[str, float] | None]],
        metadata: dict | None = None,
        model_parameters: dict[str, str | int | float | bool | list[str] | None] | None = None,
    ) -> _T:
        if not trace_id or not self._is_live_ready():
            result, _, _, _ = operation()
            return result

        langfuse = self._client()
        if langfuse is None:
            result, _, _, _ = operation()
            return result

        external_trace_id = self.external_trace_id(trace_id)
        with langfuse.start_as_current_observation(
            as_type="generation",
            name=name,
            trace_context={"trace_id": external_trace_id},
            input=input_payload,
            metadata=metadata,
            model=model,
            model_parameters=model_parameters,
            end_on_exit=False,
        ) as generation:
            try:
                result, output_payload, usage_details, cost_details = operation()
                generation.update(
                    output=output_payload,
                    metadata=metadata,
                    usage_details=usage_details,
                    cost_details=cost_details,
                )
                langfuse.flush()
                return result
            except Exception as exc:
                generation.update(
                    output={"error": str(exc)},
                    metadata=metadata,
                    level="ERROR",
                    status_message=str(exc),
                )
                langfuse.flush()
                raise


langfuse_client = LangfuseClient()
