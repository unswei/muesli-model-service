#!/usr/bin/env python3
"""Small HTTP worker for Prismatic-compatible OpenVLA-Mini checkpoints."""

from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from prismatic.models.load import load_vla


class MiniVLAWorker:
    def __init__(
        self,
        *,
        checkpoint: Path,
        device: str,
        unnorm_key: str,
        working_dir: Path,
    ) -> None:
        self.checkpoint = checkpoint
        self.device = device
        self.unnorm_key = unnorm_key
        self.working_dir = working_dir
        self.model = None

    def load(self) -> None:
        os.chdir(self.working_dir)
        model = load_vla(self.checkpoint, hf_token=None, load_for_training=False)
        model.vision_backbone.to(dtype=model.vision_backbone.half_precision_dtype)
        model.llm_backbone.to(dtype=model.llm_backbone.half_precision_dtype)
        model.to(dtype=model.llm_backbone.half_precision_dtype)
        model.to(self.device)
        model.eval()
        self.model = model

    def predict(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.model is None:
            self.load()
        instruction = payload.get("instruction")
        images = payload.get("images")
        if not isinstance(instruction, str) or not instruction.strip():
            raise ValueError("instruction is required")
        if not isinstance(images, list) or not images:
            raise ValueError("images must be a non-empty list of paths")

        loaded_images = [Image.open(path).convert("RGB") for path in images]
        image_input: Any = loaded_images[0] if len(loaded_images) == 1 else loaded_images
        unnorm_key = payload.get("unnorm_key") or self.unnorm_key or None
        action = self.model.predict_action(
            image_input,
            instruction,
            unnorm_key=unnorm_key,
            do_sample=False,
        )
        rows = _normalise_action_rows(action)
        return {
            "status": "action_chunk",
            "actions": rows,
            "metadata": {
                "worker": "prismatic-http",
                "checkpoint": str(self.checkpoint),
                "device": self.device,
                "unnorm_key": unnorm_key,
            },
        }


def _normalise_action_rows(action: Any) -> list[list[float]]:
    if hasattr(action, "detach"):
        action = action.detach().cpu().numpy()
    array = np.asarray(action, dtype=float)
    if array.ndim == 1:
        array = array.reshape(1, -1)
    if array.ndim != 2:
        raise ValueError(f"unsupported action shape {array.shape}")
    return array.tolist()


def make_handler(worker: MiniVLAWorker) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path != "/health":
                self.send_error(404)
                return
            self._send_json({"status": "ok", "loaded": worker.model is not None})

        def do_POST(self) -> None:
            if self.path != "/act":
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("content-length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(payload, dict):
                    raise ValueError("request body must be an object")
                result = worker.predict(payload)
                self._send_json(result)
            except Exception as exc:
                self._send_json({"status": "invalid_output", "error": str(exc)}, status=500)

        def log_message(self, fmt: str, *args: Any) -> None:
            print(fmt % args, flush=True)

        def _send_json(self, payload: dict[str, Any], *, status: int = 200) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--unnorm-key", default="bridge_dataset")
    parser.add_argument("--working-dir", default=Path.cwd(), type=Path)
    args = parser.parse_args()

    worker = MiniVLAWorker(
        checkpoint=args.checkpoint,
        device=args.device,
        unnorm_key=args.unnorm_key,
        working_dir=args.working_dir,
    )
    worker.load()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(worker))
    print(f"MiniVLA Prismatic worker listening on http://{args.host}:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
