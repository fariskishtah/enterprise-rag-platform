"""Generate the deterministic, extractable policy PDF used by real API evaluations."""

from pathlib import Path


def build_pdf(lines: list[str]) -> bytes:
    encoded_lines = []
    for line in lines:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        encoded_lines.append(f"({safe}) Tj T*")
    stream = ("BT /F1 10 Tf 54 738 Td 14 TL " + " ".join(encoded_lines) + " ET").encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    result = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, value in enumerate(objects, start=1):
        offsets.append(len(result))
        result.extend(f"{number} 0 obj\n".encode())
        result.extend(value)
        result.extend(b"\nendobj\n")
    xref_offset = len(result)
    result.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    result.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        result.extend(f"{offset:010d} 00000 n \n".encode())
    result.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode()
    )
    return bytes(result)


def main() -> None:
    fixture_directory = Path(__file__).parents[1] / "tests" / "fixtures"
    source = fixture_directory / "remote_work_policy.txt"
    destination = fixture_directory / "remote_work_policy.pdf"
    destination.write_bytes(build_pdf(source.read_text(encoding="utf-8").splitlines()))
    print(f"Generated {destination} ({destination.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
