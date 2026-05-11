"""Retail assistant CLI wired to databricks-job-runner."""

import argparse
from pathlib import Path
import sys

from databricks.sdk.service.jobs import PythonWheelTask, RunResultState, SubmitTask
from databricks_job_runner import Runner
from databricks_job_runner.errors import RunnerError


ENTRY_POINTS = {
    "retail-agent-deploy": "retail-agent-deploy",
    "retail-agent-load-products": "retail-agent-load-products",
    "retail-agent-load-graphrag": "retail-agent-load-graphrag",
    "retail-agent-demo": "retail-agent-demo",
    "retail-agent-demo-retrievers": "retail-agent-demo-retrievers",
    "retail-agent-check-knowledge": "retail-agent-check-knowledge",
    "retail-agent-deploy-supervisor": "retail-agent-deploy-supervisor",
}

PIPELINE_STEPS = (
    ("upload", None),
    ("load-products", "retail-agent-load-products"),
    ("load-graphrag", "retail-agent-load-graphrag"),
    ("deploy", "retail-agent-deploy"),
    ("demo", "retail-agent-demo"),
    ("demo-retrievers", "retail-agent-demo-retrievers"),
    ("check-knowledge", "retail-agent-check-knowledge"),
)

PIPELINE_MODES = {
    "all": tuple(step for step, _ in PIPELINE_STEPS),
    "data": ("upload", "load-products", "load-graphrag"),
    "deploy": ("upload", "deploy"),
    "verify": ("demo", "demo-retrievers", "check-knowledge"),
}


class RetailAgentRunner(Runner):
    """Runner that keeps local Neo4j setup secrets out of job parameters."""

    _LOCAL_ONLY_ENV_KEYS = frozenset({
        "DATABRICKS_CONFIG_PROFILE",
        "NEO4J_URI",
        "NEO4J_PASSWORD",
    })

    def _job_params(self) -> list[str]:
        params = self.config.env_params(secret_keys=self.secret_keys)
        return [
            param
            for param in params
            if param.partition("=")[0] not in self._LOCAL_ONLY_ENV_KEYS
        ]

    def main(self, argv: list[str] | None = None) -> None:
        """Dispatch project-specific commands before the shared runner CLI."""
        args = list(sys.argv[1:] if argv is None else argv)
        if not args or args[0] in {"-h", "--help"}:
            self._print_project_help()
            return
        if args[0] == "pipeline":
            try:
                self.pipeline(args[1:])
            except RunnerError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                sys.exit(1)
            return
        super().main(args)

    def _print_project_help(self) -> None:
        print(f"Databricks job runner ({self.run_name_prefix})")
        print()
        print("Common commands:")
        print("  pipeline      Run the Agentic Commerce deployment pipeline")
        print("  upload        Upload scripts/wheels to Databricks")
        print("  submit        Submit a wheel entry point as a Databricks job")
        print("  validate      Validate compute and available wheel entry points")
        print("  logs          Print stdout/stderr from a submitted run")
        print("  download      Download or list files from a UC Volume")
        print()
        print("Examples:")
        print(f"  {self.cli_command} pipeline --all")
        print(f"  {self.cli_command} pipeline --data")
        print(f"  {self.cli_command} submit retail-agent-demo")
        print()
        print("Use '<command> --help' for command-specific options.")

    def pipeline(self, argv: list[str] | None = None) -> None:
        """Run a named sequence of wheel upload and Databricks job steps."""
        parser = argparse.ArgumentParser(
            prog=f"{self.cli_command} pipeline",
            description="Run the Agentic Commerce Databricks pipeline.",
        )
        modes = parser.add_mutually_exclusive_group()
        modes.add_argument(
            "--all",
            dest="mode",
            action="store_const",
            const="all",
            help="Upload, load data, deploy, and run all verification jobs.",
        )
        modes.add_argument(
            "--data",
            dest="mode",
            action="store_const",
            const="data",
            help="Upload the wheel, load products, and build GraphRAG.",
        )
        modes.add_argument(
            "--deploy",
            dest="mode",
            action="store_const",
            const="deploy",
            help="Upload the wheel and deploy the agent endpoint.",
        )
        modes.add_argument(
            "--verify",
            dest="mode",
            action="store_const",
            const="verify",
            help="Run endpoint, retriever, and knowledge verification jobs.",
        )
        parser.add_argument(
            "--compute",
            choices=["cluster", "serverless"],
            default=None,
            help="Override compute mode for submitted jobs.",
        )
        parser.add_argument(
            "--skip-upload",
            action="store_true",
            help="Skip the upload step when the selected pipeline includes it.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print the commands that would run without contacting Databricks.",
        )

        args = parser.parse_args(argv)
        mode = args.mode or "all"
        steps = list(PIPELINE_MODES[mode])
        if args.skip_upload:
            steps = [step for step in steps if step != "upload"]

        print(f"Agentic Commerce pipeline: {mode}")
        print("---")
        for index, step in enumerate(steps, start=1):
            print(f"{index}. {self._pipeline_command(step, args.compute)}")
        print()

        for index, step in enumerate(steps, start=1):
            print("=" * 60)
            print(f"Pipeline step {index}/{len(steps)}: {step}")
            print("=" * 60)
            if args.dry_run:
                continue
            self._run_pipeline_step(step, compute_mode=args.compute)
            print()

        if args.dry_run:
            print("Dry run complete.")
        else:
            print("Pipeline complete.")

    def _pipeline_command(self, step: str, compute_mode: str | None) -> str:
        if step == "upload":
            return f"{self.cli_command} upload --wheel"
        entry_point = self._pipeline_entry_point(step)
        command = f"{self.cli_command} submit {entry_point}"
        if compute_mode:
            command = f"{command} --compute {compute_mode}"
        return command

    def _pipeline_entry_point(self, step: str) -> str:
        for step_name, entry_point in PIPELINE_STEPS:
            if step_name == step and entry_point:
                return entry_point
        raise RunnerError(f"Unknown pipeline step: {step}")

    def _run_pipeline_step(
        self,
        step: str,
        *,
        compute_mode: str | None = None,
    ) -> None:
        if step == "upload":
            self.upload_wheel()
            return
        self.submit(self._pipeline_entry_point(step), compute_mode=compute_mode)

    def submit(
        self,
        script: str,
        *,
        no_wait: bool = False,
        compute_mode: str | None = None,
    ) -> None:
        if script not in ENTRY_POINTS:
            available = "\n  ".join(sorted(ENTRY_POINTS))
            raise RunnerError(
                f"Unknown Agentic Commerce entry point: {script}\n"
                f"Available entry points:\n  {available}"
            )

        params = self._job_params()
        run_name = f"{self.run_name_prefix}: {script}"

        if params:
            print(f"  Params:   {len(params)} env values from .env")

        wheel_name = self.find_wheel()
        if not wheel_name:
            raise RunnerError(
                "No retail_agent wheel found in dist/. "
                "Run: uv run python -m cli upload --wheel"
            )
        wheel_path = f"{self.wheel_volume_dir}/{wheel_name}"
        print(f"  Wheel:    {wheel_path}")

        compute = self._compute(compute_mode)
        compute.validate(self.ws)

        print("Submitting wheel entry point")
        print(f"  Entry:    {script}")
        print(f"  Run name: {run_name}")
        print("---")

        entry_point = ENTRY_POINTS[script]
        task = SubmitTask(
            task_key="run_entry_point",
            python_wheel_task=PythonWheelTask(
                package_name=self.wheel_package or "retail_agent",
                entry_point=entry_point,
                parameters=params if params else None,
            ),
        )
        task = compute.decorate_task(task, wheel_path)

        waiter = self.ws.jobs.submit(
            run_name=run_name,
            tasks=[task],
            environments=compute.environments(wheel_path),
        )

        run_id: int | None = waiter.run_id
        if run_id is None:
            raise RunnerError("Databricks did not return a run_id.")
        print(f"  Run ID:   {run_id}")

        if no_wait:
            print("\nJob submitted (--no-wait). Check status in the Databricks UI.")
        else:
            print("  Waiting for completion...")
            run = waiter.result()
            result_state = run.state.result_state if run.state else None
            state_name = result_state.value if result_state else "UNKNOWN"
            page_url = run.run_page_url or ""

            print(f"\n  Result:   {state_name}")
            if page_url:
                print(f"  URL:      {page_url}")
            if result_state != RunResultState.SUCCESS:
                raise RunnerError(f"Job finished with non-success state: {state_name}")
            print("\nJob complete.")

        print()
        print("Next steps:")
        print(f"  View logs:          {self.cli_command} logs {run_id}")
        if self.config.databricks_volume_path:
            print(f"  List results:       {self.cli_command} download --list results")
            print(f"  Download results:   {self.cli_command} download results/<filename>")

    def upload_all(self) -> None:
        """No-op because jobs run Python wheel entry points directly."""
        print("No job scripts to upload.")
        print("Agentic Commerce jobs run from the uploaded wheel entry points.")
        print("Run: uv run python -m cli upload --wheel")

    def validate(self, file: str | None = None) -> None:
        """Validate compute and wheel-entry-point configuration."""
        self._compute().validate(self.ws)
        if file and file not in ENTRY_POINTS:
            available = "\n  ".join(sorted(ENTRY_POINTS))
            raise RunnerError(
                f"Unknown Agentic Commerce entry point: {file}\n"
                f"Available entry points:\n  {available}"
            )
        print()
        print("Available wheel entry points:")
        for entry_point in sorted(ENTRY_POINTS):
            print(f"  {entry_point}")
        print()
        print("Validation complete.")


runner = RetailAgentRunner(
    run_name_prefix="retail_agent",
    project_dir=Path(__file__).resolve().parent.parent,
    wheel_package="retail_agent",
)
