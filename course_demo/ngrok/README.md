# Optional ngrok demonstration

ngrok is never started by the application or test suite. A tunnel makes a local service
public; use it only with non-sensitive demo data. The local EnterpriseRAG profile has no
authentication or tenant isolation.

## Safe local setup

Keep the token in the process environment:

```bash
export NGROK_AUTHTOKEN='replace-in-your-shell-only'
backend/.venv/bin/uvicorn app.main:app --app-dir backend --port 8000
backend/.venv/bin/python course_demo/ngrok/launch_tunnel.py fastapi
```

For Streamlit:

```bash
backend/.venv/bin/streamlit run course_demo/streamlit_app/app.py
backend/.venv/bin/python course_demo/ngrok/launch_tunnel.py streamlit
```

Never put the token in source code, notebooks, `.env.example`, output artifacts, or
screenshots. Rotate the token immediately if it is exposed.

## Colab

Install `pyngrok`, assign the token from Colab Secrets to `NGROK_AUTHTOKEN`, start the
service in a background process, then call `ngrok.connect(port, bind_tls=True)`. Stop the
tunnel and service when the demonstration ends.

## Kaggle

Outbound tunnels may be restricted by Kaggle sessions or competition policies. Check the
current notebook Internet setting and platform terms. If tunnels are prohibited, use
Kaggle's notebook output instead; do not attempt to bypass the restriction.
