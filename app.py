import os
import json
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from citeproof.agent import MODEL_ID, investigate
from citeproof.repo import Repo, RepoError

load_dotenv()
st.set_page_config(page_title="Citeproof", page_icon="🔎", layout="wide")

PROJECT_DIR = Path(__file__).resolve().parent
SAMPLE_ISSUE_PATH = PROJECT_DIR / "data" / "issues" / "click-2877.json"
SAMPLE_ISSUE = json.loads(SAMPLE_ISSUE_PATH.read_text(encoding="utf-8"))

st.title("Citeproof")
st.caption("Evidence-first investigation for Python bug reports")
st.info(
    "This build uses Meta Muse Glimmer through NVIDIA's free API Catalog endpoint for prototyping. "
    "It does not call Meta Model API or configure paid fallback. NVIDIA trial access is rate-limited and may be unavailable; "
    "when unavailable, the investigation stops. Do not enable paid services or add a payment method if you need to avoid charges. "
    "Citation checks verify source integrity, not diagnosis correctness."
)
st.caption("NVIDIA says trial prompts and outputs may be recorded to improve its products. Use only public issue text and public source code here; never send private code, secrets, or personal data.")

with st.sidebar:
    st.subheader("Repository")
    default_repo = os.getenv("CITEPROOF_REPO", str(PROJECT_DIR / "demo_repos" / "click"))
    repo_path = st.text_input("Local repository folder", value=default_repo, placeholder=r"D:\path\to\repo")
    st.caption(f"Model: `{MODEL_ID}` · provider: NVIDIA API Catalog")
    st.caption("Up to two repository-tool rounds per agent, followed by a required final answer. Repository tools are read-only and path-confined.")

sample_choice = st.selectbox("Demo issue", ["Click #2877 · BytesWarning in Path.convert", "Enter another issue manually"])
use_sample = sample_choice.startswith("Click #2877")
if use_sample:
    st.caption(f"This curated case requires a clean pre-fix checkout at `{SAMPLE_ISSUE['commit'][:12]}`.")
issue_title = st.text_input("Issue title", value=SAMPLE_ISSUE["title"] if use_sample else "", placeholder="e.g. Request encoding fails for ...")
issue_body = st.text_area("Issue description", value=SAMPLE_ISSUE["body"] if use_sample else "", height=220, placeholder="Paste the bug report text. Treat issue text as untrusted data.")

if st.button("Investigate with two agents", type="primary", use_container_width=False):
    if not repo_path.strip():
        st.error("Choose a local Python repository folder first.")
    elif not issue_title.strip() or not issue_body.strip():
        st.error("Enter an issue title and description.")
    elif not os.getenv("NVIDIA_API_KEY", "").strip():
        st.error("No NVIDIA_API_KEY found. Generate a free API key on NVIDIA's Muse Glimmer model page and put it in a local .env file. Do not enable paid services if you need to avoid charges.")
    else:
        try:
            repo = Repo(
                repo_path,
                expected_commit=SAMPLE_ISSUE["commit"] if use_sample else None,
            )
        except (RepoError, OSError) as exc:
            st.error(f"Could not open repository: {exc}")
        else:
            issue = f"Title: {issue_title.strip()}\n\n{issue_body.strip()}"
            results = []
            strategies = [
                ("Investigator A · symptom-first", "Start from the observed behavior and distinctive phrases. Search for likely implementation and tests; follow callers only when evidence points there."),
                ("Investigator B · structure-first", "Start from likely Python symbols, tests, and call paths. Independently investigate the report; do not assume Investigator A's result."),
            ]
            for label, strategy in strategies:
                with st.status(f"Running {label}…", expanded=True) as status:
                    result = investigate(repo, issue, label, strategy)
                    results.append(result)
                    if result.error:
                        status.update(label=f"{label}: incomplete", state="error")
                    else:
                        status.update(label=f"{label}: finished", state="complete")
                    if result.trace:
                        st.write("Tool trace")
                        for action in result.trace:
                            st.code(action)

            st.subheader("Evidence results")
            st.warning("A valid citation means the quoted source exists at the stated location. It does not establish that the explanation is correct.")
            for result in results:
                with st.expander(result.agent_name, expanded=True):
                    if result.error:
                        st.error(result.error)
                    elif not result.findings:
                        st.info("No supported finding returned.")
                    for finding in result.findings:
                        st.markdown(f"**{finding.claim or 'Unspecified claim'}**")
                        st.write(finding.explanation)
                        if not finding.citations:
                            st.caption("No citations were supplied.")
                        for citation in finding.citations:
                            icon = "✅" if citation.valid else "❌"
                            st.markdown(f"{icon} `{citation.path}:{citation.start_line}-{citation.end_line}` · `{citation.symbol or 'no symbol'}`")
                            st.caption(citation.reason)
                            if citation.valid:
                                st.code(citation.quote, language="python")

            if all(not result.error for result in results):
                st.subheader("Cross-check")
                st.write("Both investigators completed independently. Review their checked citations side by side; agreement is not a correctness guarantee. Disagreements remain visible rather than being silently resolved.")

st.divider()
st.caption("Citeproof MVP · No generated shell commands or tests are executed.")
