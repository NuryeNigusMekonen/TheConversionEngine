from agent.config import settings
from agent.schemas.tools import ToolExecutionResult, ToolStatus


class Tau2BenchAdapter:
    def status(self) -> ToolStatus:
        available = settings.tau2_bench_path.exists()
        return ToolStatus(
            name="tau2_bench",
            label="tau2-bench Harness",
            mode="configured" if available else "unavailable",
            configured=available,
            available=available,
            details=(
                f"Checks benchmark readiness at {settings.tau2_bench_path}."
                if available
                else "Set TAU2_BENCH_PATH or clone the harness into eval/tau2-bench."
            ),
        )

    def readiness_check(self) -> ToolExecutionResult:
        status = self.status()
        if status.available:
            return ToolExecutionResult(
                name="tau2_bench",
                mode=status.mode,
                status="executed",
                message="tau2-bench harness path is present and ready for later evaluation work.",
                artifact_ref=str(settings.tau2_bench_path),
            )
        return ToolExecutionResult(
            name="tau2_bench",
            mode="unavailable",
            status="skipped",
            message="tau2-bench harness is not present yet, so readiness is recorded as pending.",
        )


tau2_adapter = Tau2BenchAdapter()
