"""AWS 문서 URL을 렌더링해서 본문만 추출한 뒤 마크다운으로 저장한다.

URLS 목록에 링크만 추가하면, 실행할 때마다 새 URL을 가져와서
data/aws_docs/에 마크다운 파일로 저장한다. 그 뒤 build_vectordb.py를 실행하면
(langchain/langgraph는 fingerprint 기반으로) 자동으로 청킹+임베딩+ChromaDB 저장까지 이어진다.

실행: python fetch_docs.py
"""
import hashlib
import os
import re

import trafilatura
from playwright.sync_api import sync_playwright

import config

# 여기에 URL만 추가하면 됨.
URLS = [
    "https://docs.aws.amazon.com/compute-on-aws-how-to-choose/",
    "https://docs.aws.amazon.com/wellarchitected/latest/cost-optimization-pillar/welcome.html",
    "https://aws.amazon.com/ec2/pricing/",
    "https://aws.amazon.com/lambda/pricing/",
    "https://aws.amazon.com/fargate/pricing/",
]


def _slugify(url: str) -> str:
    slug = re.sub(r"^https?://", "", url)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", slug).strip("-").lower()
    return slug[:80] or hashlib.sha1(url.encode()).hexdigest()[:12]


def render_html(url: str, browser) -> str:
    """자바스크립트로 내용을 그리는 페이지도 실제 렌더링된 HTML을 가져온다."""
    page = browser.new_page()
    page.goto(url, wait_until="networkidle", timeout=30000)
    html = page.content()
    page.close()
    return html


def fetch_one(url: str, browser) -> tuple[str, str]:
    """(제목, 마크다운 본문)을 반환한다."""
    html = render_html(url, browser)
    markdown = trafilatura.extract(
        html, output_format="markdown", include_links=False, include_tables=True, url=url
    )
    metadata = trafilatura.extract_metadata(html)
    title = (metadata.title if metadata and metadata.title else url).strip()
    return title, markdown or ""


def fetch_all(urls=None) -> None:
    urls = urls or URLS
    os.makedirs(config.DATA_DIR, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for url in urls:
            print(f"가져오는 중: {url}")
            try:
                title, markdown = fetch_one(url, browser)
            except Exception as e:  # noqa: BLE001
                print(f"  실패: {e}")
                continue

            if not markdown.strip():
                print("  본문을 추출하지 못했습니다 (건너뜀)")
                continue

            filename = _slugify(url) + ".md"
            path = os.path.join(config.DATA_DIR, filename)
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# {title}\n\n")
                f.write(f"<!-- 출처: {url} -->\n\n")
                f.write(markdown)
            print(f"  저장: {filename} ({len(markdown)}자)")
        browser.close()

    print("완료. python build_vectordb.py로 인덱싱하세요.")


if __name__ == "__main__":
    fetch_all()
