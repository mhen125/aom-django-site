import base64
import json
import zlib
from typing import Any


def decode_zlib_base64(encoded_value: str) -> str:
    compressed_bytes = base64.b64decode(encoded_value)
    decompressed_bytes = zlib.decompress(compressed_bytes)
    decoded_text = decompressed_bytes.decode("utf-8", errors="replace")

    return decoded_text.rstrip("\x00")


def decode_options(encoded_options: str | None) -> dict[str, Any]:
    if not encoded_options:
        return {}

    decoded_text = decode_zlib_base64(encoded_options)
    return json.loads(decoded_text)


def decode_slotinfo(encoded_slotinfo: str | None) -> dict[str, Any]:
    if not encoded_slotinfo:
        return {
            "slot_count": 0,
            "slots": [],
        }

    decoded_text = decode_zlib_base64(encoded_slotinfo)
    comma_index = decoded_text.find(",")

    if comma_index == -1:
        return {
            "slot_count": 0,
            "slots": [],
            "raw_decoded_slotinfo": decoded_text,
            "decode_warning": "Unexpected slotinfo format",
        }

    slot_count_text = decoded_text[:comma_index]
    slots_json_text = decoded_text[comma_index + 1:]

    return {
        "slot_count": int(slot_count_text),
        "slots": json.loads(slots_json_text),
    }