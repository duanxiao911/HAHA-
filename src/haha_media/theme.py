"""Visual language for the clean-slate HAHA MVP."""

from __future__ import annotations

import streamlit as st


def apply_theme() -> None:
    st.markdown(
        """
        <style>
          :root {--paper:#f6f1e9;--ink:#24201c;--muted:#746b61;--line:#d9cfc0;--red:#a63f34;}
          .block-container {max-width:1180px;padding-top:2rem;padding-bottom:4rem;}
          [data-testid="stAppViewContainer"] {background:var(--paper);color:var(--ink);}
          .site-header {display:flex;justify-content:space-between;align-items:baseline;padding:0 0 1.2rem;border-bottom:1px solid var(--line);}
          .wordmark {font-family:Georgia,serif;font-size:1.7rem;font-weight:700;letter-spacing:.04em;}
          .wordmark span,.header-note {font-family:Arial,sans-serif;font-size:.65rem;color:var(--muted);letter-spacing:.12em;}
          .media-hero {margin:1.5rem 0 1.3rem;padding:3.2rem;border-radius:20px;color:#fff;background:linear-gradient(120deg,#431f1b,#a63f34 62%,#da9273);}
          .media-hero span {font:700 .72rem Arial,sans-serif;letter-spacing:.15em;opacity:.8;}
          .media-hero h1 {margin:.7rem 0;font:700 clamp(2.2rem,5vw,4.6rem)/1.05 Georgia,serif;}
          .media-hero p {max-width:35rem;margin:0;font-size:1rem;line-height:1.8;opacity:.88;}
          .cover {height:10rem;border-radius:12px;padding:1rem;display:flex;flex-direction:column;justify-content:space-between;color:#fff;overflow:hidden;}
          .cover span {font:5rem/1 Georgia,serif;opacity:.88;}.cover small {font:700 .63rem Arial,sans-serif;letter-spacing:.12em;}
          .cover.red {height:25rem;background:radial-gradient(circle at 72% 28%,#e4a78e,transparent 23%),linear-gradient(135deg,#501e1b,#b94738);}
          .cover.green {background:linear-gradient(135deg,#1c463e,#6f9b7c);}.cover.blue {background:linear-gradient(135deg,#1d3e5a,#638aa1);}
          .cover.gold {background:linear-gradient(135deg,#715228,#c69c50);}.cover.purple {background:linear-gradient(135deg,#493259,#a67693);}
          .channel-banner {display:flex;align-items:center;justify-content:space-between;gap:1rem;margin:1.2rem 0 1.5rem;padding:1.3rem 1.6rem;border-radius:14px;color:#fff;background:linear-gradient(100deg,#263c4a,#587987);}
          .channel-banner small,.channel-banner span {display:block;font:600 .7rem Arial,sans-serif;letter-spacing:.08em;opacity:.82;}.channel-banner strong {display:block;margin:.25rem 0;font:700 1.4rem Georgia,serif;}.channel-banner b {font:4rem/1 Georgia,serif;opacity:.75;}
          .ranking-item {display:flex;gap:.65rem;padding:.75rem 0;border-bottom:1px solid var(--line);}.ranking-item>b{color:var(--red);font:700 1rem Georgia,serif;}.ranking-item strong,.ranking-item small{display:block;line-height:1.4;}.ranking-item strong{font-size:.84rem;}.ranking-item small{margin-top:.25rem;color:var(--muted);font-size:.68rem;}
          .creator-head {margin:1rem 0 1.5rem;padding-bottom:1.3rem;border-bottom:1px solid var(--line);}.creator-head span {color:var(--red);font:700 .7rem Arial,sans-serif;letter-spacing:.14em;}.creator-head h2{margin:.35rem 0;font:700 2rem Georgia,serif;}.creator-head p{margin:0;color:var(--muted);}.upload-tip {margin:0 0 1rem;padding:.7rem .85rem;border-radius:8px;background:#eee5d7;color:var(--muted);font-size:.8rem;}
          .creator-rule {display:grid;grid-template-columns:2rem 1fr;column-gap:.55rem;padding:1rem 0;border-bottom:1px solid var(--line);}.creator-rule b{grid-row:span 2;color:var(--red);font:700 1.1rem Georgia,serif;}.creator-rule strong{font-size:.88rem;}.creator-rule span{margin-top:.3rem;color:var(--muted);font-size:.76rem;line-height:1.6;}
          [data-testid="stFileUploaderDropzone"] {min-height:11rem;border:2px dashed #bd897d;background:#fffaf4;}
          [data-testid="stTabs"] button {font-weight:600;} [data-testid="stTabs"] button[aria-selected="true"] {color:var(--red);}
          @media (max-width:700px) {.site-header{display:block}.header-note{margin-top:.4rem}.media-hero{padding:2.6rem 1.5rem}.cover.red{height:18rem}}
        </style>
        """,
        unsafe_allow_html=True,
    )
