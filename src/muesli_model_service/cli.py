from pathlib import Path
from typing import Annotated

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
) -> None:
    settings = Settings(
        host=host,
        port=port,
        log_level=log_level,
        replay_path=str(replay_path) if replay_path else None,
        enable_mock_backend=enable_mock_backend,
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
