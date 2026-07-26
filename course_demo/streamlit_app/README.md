# Streamlit course demo

This presentation UI is intentionally separate from the React product.

```bash
cd /Users/fariskishtah/Desktop/EnterpriseRAG
backend/.venv/bin/streamlit run course_demo/streamlit_app/app.py
```

The LangChain selection processes the uploaded PDF with `PyPDFLoader`,
`RecursiveCharacterTextSplitter`, `HuggingFaceEmbeddings`, and persistent FAISS. The
custom selection calls the existing FastAPI service, which must already be running.

Model loading is lazy. The first LangChain request may download configured public model
weights unless `ENTERPRISE_RAG_HF_LOCAL_FILES_ONLY=true` is set.
