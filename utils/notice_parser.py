from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, urlunparse, parse_qs, urlencode
from typing import Optional, Tuple

from ..constants import NOTICE_BLOG_BASE


def upscale_naver_thumb(url: Optional[str]) -> Optional[str]:
    """
        네이버 블로그 썸네일(blogthumb...?type=s2)을 원본 호스트(postfiles)의
        큰 사이즈(type=w966)로 변환. 변환 불가/비대상이면 None.
        실제 다운로드 실패 시 호출부에서 원본 URL로 폴백한다.
    """
    if not url:
        return None
    try:
        parsed = urlparse(url)
        if 'pstatic.net' not in parsed.netloc:
            return None
        host = parsed.netloc.replace('blogthumb2', 'postfiles').replace('blogthumb', 'postfiles')
        query = parse_qs(parsed.query)
        query['type'] = ['w966']
        new_url = urlunparse(parsed._replace(netloc=host, query=urlencode(query, doseq=True)))
        return new_url if new_url != url else None
    except Exception:
        return None


def _normalize_url(url: Optional[str]) -> Optional[str]:
    """
        상대/프로토콜 상대 URL을 절대 URL로 변환
    """
    if not url:
        return None
    url = url.strip()
    if not url or url.lower().startswith('javascript:'):
        return None
    if url.startswith('//'):
        return 'https:' + url
    if url.startswith('http://') or url.startswith('https://'):
        return url
    return urljoin(NOTICE_BLOG_BASE + '/', url)


class _BccParser(HTMLParser):
    """
        첫 번째 <td class="bcc">의 첫 이미지(src)와 첫 링크(href)를 추출
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.img: Optional[str] = None
        self.link: Optional[str] = None
        self._in_bcc = False
        self._td_depth = 0
        self._done = False

    def handle_starttag(self, tag, attrs):
        if self._done:
            return
        attrs_dict = dict(attrs)

        if tag == 'td':
            if not self._in_bcc:
                classes = (attrs_dict.get('class') or '').split()
                if 'bcc' in classes:
                    self._in_bcc = True
                    self._td_depth = 1
            else:
                self._td_depth += 1
            return

        if not self._in_bcc:
            return

        if tag == 'a' and self.link is None:
            self.link = attrs_dict.get('href')
        elif tag == 'img' and self.img is None:
            # 네이버 lazy-load 대비: data-* 속성도 확인
            self.img = (
                attrs_dict.get('src')
                or attrs_dict.get('data-src')
                or attrs_dict.get('data-lazy-src')
            )

    def handle_endtag(self, tag):
        if self._done or not self._in_bcc or tag != 'td':
            return
        self._td_depth -= 1
        if self._td_depth <= 0:
            self._in_bcc = False
            self._done = True  # 첫 번째 bcc만 사용


def parse_first_bcc(html: str) -> Tuple[Optional[str], Optional[str]]:
    """
        HTML에서 첫 <td class="bcc">의 (이미지 URL, 링크 URL) 반환.
        찾지 못하면 (None, None).
    """
    parser = _BccParser()
    try:
        parser.feed(html)
    except Exception:
        pass
    return _normalize_url(parser.img), _normalize_url(parser.link)
