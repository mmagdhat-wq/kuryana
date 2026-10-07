from datetime import datetime, timezone
from typing import Any, Dict, List, Type, TypeVar, Union
from urllib.parse import urljoin

import primp
from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

from app import MYDRAMALIST_WEBSITE

T = TypeVar("T", bound="Parser")


ScrapeTypes = {
    "search": urljoin(MYDRAMALIST_WEBSITE, "search?q="),
    "page": MYDRAMALIST_WEBSITE,
}


class Parser:
    """Main Parser"""

    headers: Dict[str, str] = {
        "Referer": MYDRAMALIST_WEBSITE,
    }

    def __init__(
        self, soup: BeautifulSoup | None, query: str, code: int, ok: bool
    ) -> None:
        self.soup = soup
        self.query = query
        self.status_code = code
        self.ok = ok

    @classmethod
    async def scrape(cls: Type[T], query: str, t: str) -> T:
        if t not in ScrapeTypes.keys():
            raise Exception("Invalid type")

        # parse url
        url = urljoin(ScrapeTypes[t], query)
        if t == "search":
            url = ScrapeTypes[t] + query

        ok = True
        code = 500  # default to 500, internal server error
        soup = None

        try:
            client = primp.Client(impersonate="chrome_131", impersonate_os="linux")
            resp = client.get(url, headers=Parser.headers)

            # set the main soup var
            soup = BeautifulSoup(
                resp.text,
                "html.parser",
            )

            # set the status code
            code = resp.status_code
            ok = resp.status_code == 200

        except Exception:
            ok = False

        return cls(soup, query, code, ok)

    # get page err, if possible
    def res_get_err(self) -> Dict[str, Any]:
        if self.soup is None:
            return {}

        container = self.soup.find("div", class_="app-body")

        err: Dict[str, Any] = {}

        if container is None:
            return err

        try:
            box_body = container.find("div", class_="box-body")
            if box_body is not None:
                err["code"] = self.status_code
                err["error"] = True
                h1_elem = box_body.find("h1")
                p_elem = box_body.find("p")
                err["description"] = {
                    "title": h1_elem.get_text().strip() if h1_elem else "",
                    "info": p_elem.get_text().strip() if p_elem else "",
                }

        except Exception:
            pass

        return err


class BaseSearch(Parser):
    def __init__(self, soup: BeautifulSoup, query: str, code: int, ok: bool) -> None:
        super().__init__(soup, query, code, ok)

        self.search_results: Dict[str, List] = {}

    def search(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "results": self.search_results,
            "scrape_date": datetime.now(timezone.utc),
        }


class BaseFetch(Parser):
    def __init__(self, soup: BeautifulSoup, query: str, code: int, ok: bool) -> None:
        super().__init__(soup, query, code, ok)

        self.info: Dict[str, Any] = {
            "link": urljoin(MYDRAMALIST_WEBSITE, query)
        }

        self._img_attrs = ["src", "data-cfsrc", "data-src"]

    def fetch(self) -> Dict[str, Any]:
        return {
            "slug_query": self.query,
            "data": self.info,
            "scrape_date": datetime.now(timezone.utc),
        }

    def _get(self) -> None:
        """handler for parser, override in subclass"""

    def _get_poster(self, container: Union[Tag, NavigableString]) -> Union[str, Any]:
        poster = container.find("img")

        if poster is None:
            return ""

        for i in self._img_attrs:
            if poster.has_attr(i):
                return poster[i]

        return ""

    def _get_details(self, classname: str) -> None:
        if self.soup is None:
            return

        details = self.soup.find("ul", class_=classname)
        if details is None:
            return

        try:
            self.info["details"] = {}
            all_details = details.find_all("li")

            for i in all_details:
                b_tag = i.find("b")
                if b_tag is None:
                    continue
                _title = b_tag.text.strip()

                self.info["details"][
                    _title.replace(":", "").replace(" ", "_").lower()
                ] = i.text.replace(
                    _title + " ", ""
                ).strip()

        except Exception:
            pass

    def _handle_rating(
        self, component: Union[Tag, NavigableString, None]
    ) -> Union[str, float, Any]:
        if component is None:
            return ""
        try:
            return float(component.text)
        except Exception:
            pass

        return component.text
