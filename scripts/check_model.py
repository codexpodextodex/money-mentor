"""Check that the model in .env works for Money Mentor.

Run this right after putting a key in .env:

    python scripts/check_model.py

It lists the Nemotron models the key can see, then asks the configured model
one real question with tools, and one with a small test image. The key itself
is never printed.
"""

from __future__ import annotations

import base64
import pathlib
import struct
import sys
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

from app import agent, config, db, insights  # noqa: E402


def tiny_png() -> str:
    """A 32x32 green square as a PNG data URL, made without any image library."""
    width = height = 32
    row = b"\x00" + bytes([11, 122, 75]) * width
    raw = zlib.compress(row * height)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(png).decode()


def main() -> None:
    if not config.LLM_API_KEY:
        sys.exit("No key found. Copy .env.example to .env and set LLM_API_KEY.")
    print(f"Endpoint: {config.LLM_BASE_URL}")
    headers = {"Authorization": f"Bearer {config.LLM_API_KEY}"}

    try:
        response = httpx.get(f"{config.LLM_BASE_URL}/models", headers=headers, timeout=30)
        response.raise_for_status()
        ids = sorted(m.get("id", "") for m in response.json().get("data", []))
        nemotron = [i for i in ids if "nemotron" in i.lower()]
        print(f"The key works. {len(ids)} models visible, {len(nemotron)} Nemotron:")
        for model_id in nemotron or ids[:20]:
            print("   ", model_id)
        if not config.LLM_MODEL and nemotron:
            best = next((i for i in nemotron if "super-vl" in i.lower()), nemotron[0])
            print(f"\nLLM_MODEL is not set. Add this line to .env:\n    LLM_MODEL={best}")
            return
    except httpx.HTTPError as exc:
        print(f"Could not list models ({exc.__class__.__name__}). Carrying on with LLM_MODEL as set.")

    if not config.LLM_MODEL:
        sys.exit("Set LLM_MODEL in .env, then run this again.")
    print(f"\nModel: {config.LLM_MODEL}")

    db.init()
    cid = insights.personas()[0]["customer_id"]

    def ask(question: str, image: str | None = None, must_use_tool: bool = False, must_say: str | None = None) -> bool:
        events = list(agent.run(cid, question, image=image))
        answer = events[-1]
        tools_called = [e["name"] for e in events if e["type"] == "tool_call"]
        text = answer.get("text", "")
        print(f"\nQ: {question}{'  [with image]' if image else ''}")
        print(f"   mode: {answer.get('mode')}   answered by: {answer.get('served_by')}   tools: {tools_called or 'none'}   {answer.get('seconds')} s")
        if answer.get("note"):
            print(f"   note: {answer['note']}")
        print(f"   numbers checked: {answer['grounding']['numbers_checked']}, unverified: {answer['grounding']['unverified']}")
        print("   A:", text[:400].replace("\n", " "))
        # A model that is up but broken still "answers": it must also call a tool, or say the expected word.
        if answer.get("mode") != "nemotron":
            return False
        if must_use_tool and not tools_called:
            return False
        return not must_say or must_say.lower() in text.lower()

    ok_text = ask("How much did I spend on groceries last month, and is that more than the month before?", must_use_tool=True)
    ok_image = ask("This is a test image. What colour is it? Answer in one short sentence.", image=tiny_png(), must_say="green")
    print()
    print("Text and tools:", "OK" if ok_text else "FAILED (no model answer, or the model did not call a tool)")
    print("Image input:   ", "OK" if ok_image else "FAILED (the endpoint may not accept images, or it did not see a green square)")
    if not (ok_text and ok_image):
        sys.exit(1)


if __name__ == "__main__":
    main()
