from __future__ import annotations

import argparse
import os

from pyngrok import conf, ngrok


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Open an explicit optional ngrok tunnel."
    )
    parser.add_argument("service", choices=("fastapi", "streamlit"))
    args = parser.parse_args()
    token = os.getenv("NGROK_AUTHTOKEN")
    if not token:
        raise SystemExit(
            "Set NGROK_AUTHTOKEN in the environment; never commit the token."
        )
    conf.get_default().auth_token = token
    port = 8000 if args.service == "fastapi" else 8501
    tunnel = ngrok.connect(port, bind_tls=True)
    print(f"{args.service} tunnel: {tunnel.public_url}")
    print("Press Ctrl+C to close the tunnel.")
    try:
        ngrok.get_process().proc.wait()
    finally:
        ngrok.disconnect(tunnel.public_url)


if __name__ == "__main__":
    main()
