import re
from typing import Optional
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel


class ParsedSite(BaseModel):
    """Parsed website data."""

    url: str
    title: str = ""
    meta_description: str = ""
    h1: str = ""
    main_text: str = ""
    images: list[str] = []
    links: list[str] = []
    contact_info: dict = {}
    social_links: list[str] = []
    detected_language: str = "ru"
    is_telegram: bool = False


class ParsedTelegram(BaseModel):
    """Parsed Telegram channel data."""

    url: str
    channel_name: str = ""
    channel_username: str = ""
    description: str = ""
    subscribers: Optional[int] = None
    avatar_url: Optional[str] = None
    recent_posts: list[str] = []


class ParserService:
    """Service for parsing websites and Telegram channels."""

    def __init__(self):
        self.timeout = 30.0

    async def parse(self, url: str) -> ParsedSite | ParsedTelegram:
        """Parse URL - automatically detect if it's a website or Telegram channel."""
        parsed_url = urlparse(url)

        if "t.me" in parsed_url.netloc or "telegram" in parsed_url.netloc:
            return await self.parse_telegram(url)
        else:
            return await self.parse_website(url)

    async def parse_website(self, url: str) -> ParsedSite:
        """Parse a regular website."""
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            response = await client.get(url, headers={"User-Agent": "AdFlow Bot/1.0"})
            response.raise_for_status()
            html = response.text

        soup = BeautifulSoup(html, "lxml")

        # Remove scripts ; styles
        for tag in soup(["script", "style", "noscript", "iframe"]):
            tag.decompose()

        # Extract data
        result = ParsedSite(url=url)

        # Title
        if soup.title:
            result.title = soup.title.string.strip() if soup.title.string else ""

        # Meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            result.meta_description = meta_desc.get("content", "")

        # H1
        h1 = soup.find("h1")
        if h1:
            result.h1 = h1.get_text(strip=True)

        # Main text (try common content containers)
        main_text_parts = []
        for selector in ["main", "article", '[role="main"]', ".content", "#content"]:
            content = soup.select_one(selector)
            if content:
                main_text_parts.append(content.get_text(separator=" ", strip=True))
                break

        if not main_text_parts:
            # Fallback: get body text
            body = soup.find("body")
            if body:
                main_text_parts.append(body.get_text(separator=" ", strip=True)[:5000])

        result.main_text = " ".join(main_text_parts)[:5000]  # Limit text

        # Images
        images = []
        for img in soup.find_all("img", src=True)[:20]:
            src = img["src"]
            if src.startswith("http"):
                images.append(src)
        result.images = images

        # Contact info
        result.contact_info = self._extract_contact_info(result.main_text, soup)

        # Social links
        result.social_links = self._extract_social_links(soup)

        # Language detection (simple)
        result.detected_language = self._detect_language(result.main_text)

        return result

    async def parse_telegram(self, url: str) -> ParsedTelegram:
        """Parse a Telegram channel preview page."""
        # Convert t.me/channel to t.me/s/channel for web preview
        parsed = urlparse(url)
        path = parsed.path.strip("/")

        if not path.startswith("s/"):
            preview_url = f"https://t.me/s/{path}"
        else:
            preview_url = url

        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            response = await client.get(preview_url, headers={"User-Agent": "AdFlow Bot/1.0"})
            response.raise_for_status()
            html = response.text

        soup = BeautifulSoup(html, "lxml")

        result = ParsedTelegram(url=url)

        # Channel name
        name_el = soup.select_one(".tgme_channel_info_header_title")
        if name_el:
            result.channel_name = name_el.get_text(strip=True)

        # Username
        username_el = soup.select_one(".tgme_channel_info_header_username")
        if username_el:
            result.channel_username = username_el.get_text(strip=True).strip("@")

        # Description
        desc_el = soup.select_one(".tgme_channel_info_description")
        if desc_el:
            result.description = desc_el.get_text(strip=True)

        # Subscribers
        counter_el = soup.select_one(".tgme_channel_info_counter .counter_value")
        if counter_el:
            count_text = counter_el.get_text(strip=True).replace(" ", "").replace(",", "")
            # Handle K, M suffixes
            if count_text.endswith("K"):
                result.subscribers = int(float(count_text[:-1]) * 1000)
            elif count_text.endswith("M"):
                result.subscribers = int(float(count_text[:-1]) * 1000000)
            else:
                try:
                    result.subscribers = int(count_text)
                except ValueError:
                    pass

        # Avatar
        avatar_el = soup.select_one(".tgme_channel_info_header img")
        if avatar_el and avatar_el.get("src"):
            result.avatar_url = avatar_el["src"]

        # Recent posts
        posts = []
        for msg in soup.select(".tgme_widget_message_text")[:5]:
            text = msg.get_text(strip=True)
            if text:
                posts.append(text[:500])
        result.recent_posts = posts

        return result

    def _extract_contact_info(self, text: str, soup: BeautifulSoup) -> dict:
        """Extract contact information from page."""
        contact = {}

        # Email
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        emails = re.findall(email_pattern, text)
        if emails:
            contact["email"] = emails[0]

        # Phone (Russian format)
        phone_pattern = r"[\+7|8][\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}"
        phones = re.findall(phone_pattern, text)
        if phones:
            contact["phone"] = phones[0]

        # Address hints
        addr_el = soup.find(string=re.compile(r"адрес|address", re.I))
        if addr_el:
            parent = addr_el.parent
            if parent:
                contact["address_hint"] = parent.get_text(strip=True)[:200]

        return contact

    def _extract_social_links(self, soup: BeautifulSoup) -> list[str]:
        """Extract social media links."""
        social_domains = ["vk.com", "t.me", "telegram", "instagram", "facebook", "youtube"]
        social_links = []

        for link in soup.find_all("a", href=True):
            href = link["href"]
            for domain in social_domains:
                if domain in href:
                    social_links.append(href)
                    break

        return list(set(social_links))[:10]

    def _detect_language(self, text: str) -> str:
        """Simple language detection."""
        # Count Cyrillic vs Latin characters
        cyrillic = len(re.findall(r"[а-яА-ЯёЁ]", text))
        latin = len(re.findall(r"[a-zA-Z]", text))

        if cyrillic > latin:
            return "ru"
        return "en"


# Global instance
parser_service = ParserService()
