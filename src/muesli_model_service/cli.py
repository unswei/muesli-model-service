from pathlib import Path
from typing import Annotated, Literal

import typer
import uvicorn
from rich import print_json

from muesli_model_service.app import create_app
from muesli_model_service.config import Settings
from muesli_model_service.protocol.envelope import Operation, RequestEnvelope
from muesli_model_service.runtime.dispatcher import Dispatcher

cli = typer.Typer(no_args_is_help=True)


@cli.command()
def serve(
    host: Annotated[str, typer.Option()] = "127.0.0.1",
    port: Annotated[int, typer.Option()] = 8765,
    log_level: Annotated[str, typer.Option()] = "info",
    replay_path: Annotated[Path | None, typer.Option()] = None,
    enable_mock_backend: Annotated[bool, typer.Option()] = True,
    action_chunk_backend: Annotated[Literal["mock", "smolvla", "minivla"], typer.Option()] = "mock",
    enable_smolvla_backend: Annotated[bool, typer.Option()] = False,
    enable_minivla_backend: Annotated[bool, typer.Option()] = False,
    smolvla_model_path: Annotated[str, typer.Option()] = "lerobot/smolvla_base",
    smolvla_device: Annotated[str, typer.Option()] = "cuda",
    smolvla_profile_path: Annotated[Path | None, typer.Option()] = None,
    smolvla_action_type: Annotated[str, typer.Option()] = "joint_targets",
    smolvla_dt_ms: Annotated[int, typer.Option()] = 33,
    minivla_model_path: Annotated[
        str, typer.Option()
    ] = "Stanford-ILIAD/minivla-vq-bridge-prismatic",
    minivla_device: Annotated[str, typer.Option()] = "cuda",
    minivla_profile_path: Annotated[Path | None, typer.Option()] = None,
    minivla_action_type: Annotated[str, typer.Option()] = "joint_targets",
    minivla_dt_ms: Annotated[int, typer.Option()] = 200,
    minivla_unnorm_key: Annotated[str, typer.Option()] = "",
    minivla_dtype: Annotated[str, typer.Option()] = "bfloat16",
    minivla_worker_url: Annotated[str | None, typer.Option()] = None,
) -> None:
    settings = Settings(
        host=host,
        port=port,
        log_level=log_level,
        replay_path=str(replay_path) if replay_path else None,
        enable_mock_backend=enable_mock_backend,
        action_chunk_backend=action_chunk_backend,
        enable_smolvla_backend=enable_smolvla_backend,
        enable_minivla_backend=enable_minivla_backend,
        smolvla_model_path=smolvla_model_path,
        smolvla_device=smolvla_device,
        smolvla_profile_path=str(smolvla_profile_path) if smolvla_profile_path else None,
        smolvla_action_type=smolvla_action_type,
        smolvla_dt_ms=smolvla_dt_ms,
        minivla_model_path=minivla_model_path,
        minivla_device=minivla_device,
        minivla_profile_path=str(minivla_profile_path) if minivla_profile_path else None,
        minivla_action_type=minivla_action_type,
        minivla_dt_ms=minivla_dt_ms,
        minivla_unnorm_key=minivla_unnorm_key,
        minivla_dtype=minivla_dtype,
        minivla_worker_url=minivla_worker_url,
    )
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level)


@cli.command()
def describe() -> None:
    import asyncio

    async def run() -> None:
        dispatcher: Dispatcher = create_app(Settings()).state.dispatcher
        result = await dispatcher.dispatch(
            RequestEnvelope(id="cli-describe", op=Operation.DESCRIBE)
        )
        print_json(result.model_dump_json())

    asyncio.run(run())


@cli.command("validate-replay")
def validate_replay(path: Path) -> None:
    from muesli_model_service.backends.replay import load_replay_fixtures

    fixtures = load_replay_fixtures(path)
    typer.echo(f"valid replay file: {path} ({len(fixtures)} fixture(s))")


def main() -> None:
    cli()
