import base64
import os
import random
from pathlib import Path
from typing import Annotated

import typer
import uvicorn

app = typer.Typer()

KEY_FILE = Path.cwd() / '.webui_secret_key'


def version_callback(value: bool) -> None:
    if value:
        from open_webui.env import VERSION

        typer.echo(f'Open WebUI version: {VERSION}')
        raise typer.Exit()


@app.command()
def main(
    version: Annotated[bool | None, typer.Option('--version', callback=version_callback)] = None,
):
    pass


@app.command()
def serve(
    host: str = '0.0.0.0',
    port: int = 8080,
):
    os.environ['FROM_INIT_PY'] = 'true'
    if os.getenv('WEBUI_SECRET_KEY') is None:
        typer.echo('Loading WEBUI_SECRET_KEY from file, not provided as an environment variable.')
        if not KEY_FILE.exists():
            typer.echo(f'Generating a new secret key and saving it to {KEY_FILE}')
            KEY_FILE.write_bytes(base64.b64encode(random.randbytes(12)))
        typer.echo(f'Loading WEBUI_SECRET_KEY from {KEY_FILE}')
        os.environ['WEBUI_SECRET_KEY'] = KEY_FILE.read_text()

    if os.getenv('USE_CUDA_DOCKER', 'false') == 'true':
        typer.echo('Warning: USE_CUDA_DOCKER=true is not supported in slim build. Ignoring.')
        os.environ['USE_CUDA_DOCKER'] = 'false'

    import open_webui.main  # noqa: F401
    from open_webui.env import UVICORN_WORKERS  # Import the workers setting

    uvicorn.run(
        'open_webui.main:app',
        host=host,
        port=port,
        forwarded_allow_ips='*',
        workers=UVICORN_WORKERS,
    )


@app.command()
def dev(
    host: str = '0.0.0.0',
    port: int = 8080,
    reload: bool = True,
):
    uvicorn.run(
        'open_webui.main:app',
        host=host,
        port=port,
        reload=reload,
        forwarded_allow_ips='*',
    )


if __name__ == '__main__':
    app()
