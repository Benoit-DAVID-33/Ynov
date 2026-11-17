"""Check the Triton inference server directly, without the application.

    python scripts/triton_check.py                       # health and models
    python scripts/triton_check.py input.mp4             # + streamed transcription
    python scripts/triton_check.py input.mp4 --to fr     # + translation of the text
    python scripts/triton_check.py --url localhost:8101 --model whisper_small_en input.wav

Talks gRPC to the port published by docker-compose.gpu.yml (127.0.0.1:8101). A file
other than a 16 kHz mono wav is converted with ffmpeg (needed on this machine).
"""

import argparse
import queue
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

import numpy as np
import tritonclient.grpc as grpcclient


def read_audio(path: Path) -> np.ndarray:
    with tempfile.TemporaryDirectory() as tmp:
        wav_path = path
        if path.suffix.lower() != ".wav":
            wav_path = Path(tmp) / "audio.wav"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000",
                            "-c:a", "pcm_s16le", str(wav_path)], check=True)
        with wave.open(str(wav_path), "rb") as wav:
            if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (16000, 1, 2):
                sys.exit("wav attendu en 16 kHz mono 16 bits (ou passez un autre format, converti par ffmpeg)")
            return np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)


def transcribe(client, model: str, samples: np.ndarray) -> list[str]:
    answers: queue.Queue = queue.Queue()
    client.start_stream(callback=lambda result, error: answers.put((result, error)))
    audio = grpcclient.InferInput("AUDIO", [len(samples)], "INT16")
    audio.set_data_from_numpy(samples)
    started = time.perf_counter()
    client.async_stream_infer(model, [audio], enable_empty_final_response=True)
    lines, first = [], None
    while True:
        result, error = answers.get(timeout=600)
        if error is not None:
            sys.exit(f"Erreur du serveur : {error}")
        if result.as_numpy("LANGUAGE") is not None:
            print(f"  langue : {result.as_numpy('LANGUAGE')[0].decode()}")
        if result.as_numpy("TEXT") is not None:
            first = first or time.perf_counter() - started
            start, end = result.as_numpy("START")[0], result.as_numpy("END")[0]
            text = result.as_numpy("TEXT")[0].decode()
            lines.append(text)
            print(f"  [{start:6.1f} → {end:6.1f}] {text}")
        params = result.get_response().parameters
        if "triton_final_response" in params and params["triton_final_response"].bool_param:
            break
    client.stop_stream()
    total = time.perf_counter() - started
    duration = len(samples) / 16000
    print(f"  {len(lines)} segments ; premier segment après {first or 0:.1f} s ; "
          f"{total:.1f} s pour {duration:.0f} s d'audio (× {total / duration:.2f})")
    return lines


def translate(client, texts: list[str], target: str) -> None:
    sentences = grpcclient.InferInput("TEXT", [len(texts)], "BYTES")
    sentences.set_data_from_numpy(np.array([t.encode() for t in texts], dtype=np.object_))
    language = grpcclient.InferInput("TARGET", [1], "BYTES")
    language.set_data_from_numpy(np.array([target.encode()], dtype=np.object_))
    started = time.perf_counter()
    result = client.infer("translator", [sentences, language])
    for text in result.as_numpy("TRANSLATION")[:5]:
        print(f"  {text.decode()}")
    print(f"  {len(texts)} phrases traduites en {time.perf_counter() - started:.2f} s")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("media", nargs="?", type=Path)
    parser.add_argument("--url", default="localhost:8101", help="adresse gRPC de Triton")
    parser.add_argument("--model", default="whisper_medium_en")
    parser.add_argument("--to", help="langue de traduction (fr, es, ru, ar, zh)")
    args = parser.parse_args()

    client = grpcclient.InferenceServerClient(
        args.url, channel_args=[("grpc.max_send_message_length", -1), ("grpc.max_receive_message_length", -1)])
    print(f"Serveur {args.url} : vivant={client.is_server_live()} prêt={client.is_server_ready()}")
    for model in client.get_model_repository_index().models:
        print(f"  modèle {model.name:24} {model.state or 'non chargé'}")
    if args.media:
        print(f"Transcription de {args.media} par {args.model} :")
        lines = transcribe(client, args.model, read_audio(args.media))
        if args.to:
            print(f"Traduction en {args.to} :")
            translate(client, lines, args.to)
    client.close()


if __name__ == "__main__":
    main()
