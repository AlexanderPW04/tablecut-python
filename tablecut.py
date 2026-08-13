"""Official Python client for the Tablecut API.

Tablecut extracts tables from PDFs and returns clean JSON, markdown, or CSV:
https://tablecut.com

Usage:

    from tablecut import Tablecut

    client = Tablecut()  # reads the TABLECUT_API_KEY environment variable
    result = client.extract("report.pdf", format="json,markdown")
    for table in result["tables"]:
        print(table["markdown"])

The only dependency is `requests`.
"""

from __future__ import annotations

import os
from typing import Any, BinaryIO, Iterable, Union

import requests

__all__ = [
    "Tablecut",
    "TablecutError",
    "AuthenticationError",
    "RateLimitError",
    "InvalidRequestError",
    "ServerError",
]

__version__ = "0.1.0"

DEFAULT_BASE_URL = "https://tablecut.com/v1"
DEFAULT_TIMEOUT = 120.0

FileInput = Union[str, "os.PathLike[str]", bytes, BinaryIO]


class TablecutError(Exception):
    """Base class for all Tablecut API errors.

    Attributes:
        message: Human-readable description (wording may change between
            releases — switch on ``code``, never parse ``message``).
        code: Stable machine-readable error code from the API
            (e.g. ``"file_too_large"``, ``"quota_exceeded"``), or None if
            the error did not come from the API's error envelope.
        status_code: HTTP status code, or None for transport-level errors.
        request_id: Server-assigned request id — include it in support
            requests. None if unavailable.
        docs_url: Optional link to relevant documentation, when the API
            provides one.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        request_id: str | None = None,
        docs_url: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.request_id = request_id
        self.docs_url = docs_url

    def __str__(self) -> str:
        parts = [self.message]
        if self.code:
            parts.append(f"(code: {self.code})")
        if self.request_id:
            parts.append(f"(request_id: {self.request_id})")
        return " ".join(parts)


class AuthenticationError(TablecutError):
    """The API key is missing or invalid (HTTP 401)."""


class RateLimitError(TablecutError):
    """Request rate throttled or monthly quota exhausted (HTTP 429).

    ``code`` distinguishes the two cases: ``"rate_limited"`` (slow down and
    retry after ``retry_after`` seconds) vs ``"quota_exceeded"`` (the monthly
    page quota is used up — retrying won't help until the period resets or
    the plan is upgraded).

    Attributes:
        retry_after: Seconds to wait before retrying, from the
            ``Retry-After`` response header. None if the header was absent.
    """

    def __init__(self, message: str, *, retry_after: int | None = None, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class InvalidRequestError(TablecutError):
    """The request was rejected as invalid (HTTP 4xx other than 401/429).

    Covers bad parameters (``invalid_pages``, ``invalid_format``), oversized
    inputs (``file_too_large``, ``too_many_pages``, ``vision_page_limit``),
    non-PDF uploads (``unsupported_file_type``), and unreadable PDFs
    (``unprocessable_pdf``). Check ``code`` to tell them apart.
    """


class ServerError(TablecutError):
    """The API failed on its end (HTTP 5xx).

    ``internal_error`` (500) is a bug on Tablecut's side; ``vision_unavailable``
    (503) means the vision provider is down *and* the document needed the
    vision fallback — retry later. Nothing is billed on either.
    """


class Tablecut:
    """Client for the Tablecut PDF table extraction API.

    Args:
        api_key: Your Tablecut API key. Defaults to the ``TABLECUT_API_KEY``
            environment variable.
        base_url: API base URL including the version prefix. Defaults to
            ``https://tablecut.com/v1``.
        timeout: Per-request timeout in seconds. Extraction is synchronous
            and can take a while on large scanned documents, so the default
            is generous (120s).
        session: Optional ``requests.Session`` to reuse (e.g. for connection
            pooling or custom retry adapters). If omitted, the client creates
            and owns one; call :meth:`close` (or use the client as a context
            manager) to release it.

    Raises:
        AuthenticationError: If no API key is given and ``TABLECUT_API_KEY``
            is not set.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        session: requests.Session | None = None,
    ) -> None:
        resolved = api_key if api_key is not None else os.environ.get("TABLECUT_API_KEY")
        if not resolved:
            raise AuthenticationError(
                "No API key provided. Pass api_key=... or set the "
                "TABLECUT_API_KEY environment variable. "
                "Get a key at https://tablecut.com"
            )
        self.api_key = resolved
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._owns_session = session is None
        self._session = session or requests.Session()

    # -- public API ----------------------------------------------------------

    def extract(
        self,
        file: FileInput,
        *,
        pages: str = "all",
        format: str | Iterable[str] = "json",
        filename: str | None = None,
    ) -> dict[str, Any]:
        """Extract tables from a PDF.

        Args:
            file: The PDF to process — a filesystem path, raw ``bytes``, or
                an open binary file object.
            pages: Which pages to process, 1-indexed. Either ``"all"``
                (default) or comma-separated numbers and inclusive ranges,
                e.g. ``"1,3,5-10"``.
            format: Which representations each table carries: any combination
                of ``"json"``, ``"markdown"``, and ``"csv"``, as a
                comma-separated string or an iterable of strings.
                Defaults to ``"json"``.
            filename: Filename to report to the API. Inferred from ``file``
                when it is a path; defaults to ``"document.pdf"`` otherwise.

        Returns:
            The parsed response as a dict::

                {
                  "document":  {"filename", "page_count", "pages_processed"},
                  "tables":    [{"id", "page_range", "extraction_layer",
                                 "confidence", "headers", "rows", "spans",
                                 "markdown", "csv", "notes"}, ...],
                  "warnings":  [{"code", "message", "page"?}, ...],
                  "usage":     {"pages_billed", "vision_pages",
                                "vision_page_multiplier"},
                  "processing_time_ms": int,
                  "request_id": str
                }

            A PDF with no detectable tables is a success: ``tables`` is empty
            and ``warnings`` explains why.

        Raises:
            AuthenticationError: Invalid or missing API key (401).
            RateLimitError: Throttled or monthly quota exhausted (429).
            InvalidRequestError: Bad parameters, oversized or non-PDF input,
                or an unreadable PDF (other 4xx).
            ServerError: The API failed on its end (5xx).
            TablecutError: The response could not be interpreted.
            requests.RequestException: Network-level failure (connection,
                timeout).
        """
        data, resolved_name = self._read_file(file, filename)
        if isinstance(format, str):
            format_param = format
        else:
            format_param = ",".join(format)

        response = self._session.post(
            f"{self.base_url}/extract",
            headers={"X-API-Key": self.api_key},
            files={"file": (resolved_name, data, "application/pdf")},
            data={"pages": pages, "format": format_param},
            timeout=self.timeout,
        )
        return self._handle_response(response)

    def health(self) -> dict[str, Any]:
        """Check API liveness (no authentication required).

        Returns:
            ``{"status": "ok", "version": ..., "extraction": ...}``

        Raises:
            ServerError: The API is unhealthy (5xx).
            requests.RequestException: Network-level failure.
        """
        response = self._session.get(f"{self.base_url}/health", timeout=self.timeout)
        return self._handle_response(response)

    def close(self) -> None:
        """Release the underlying HTTP session (only if the client owns it)."""
        if self._owns_session:
            self._session.close()

    def __enter__(self) -> "Tablecut":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- internals -----------------------------------------------------------

    @staticmethod
    def _read_file(file: FileInput, filename: str | None) -> tuple[bytes, str]:
        """Normalize the ``file`` argument to (bytes, filename)."""
        if isinstance(file, bytes):
            return file, filename or "document.pdf"
        if isinstance(file, (str, os.PathLike)):
            path = os.fspath(file)
            with open(path, "rb") as handle:
                return handle.read(), filename or os.path.basename(path)
        if hasattr(file, "read"):
            data = file.read()
            if not isinstance(data, bytes):
                raise TypeError("file must be opened in binary mode ('rb')")
            inferred = filename or os.path.basename(getattr(file, "name", "") or "") or "document.pdf"
            return data, inferred
        raise TypeError(
            "file must be a path, bytes, or a binary file object, "
            f"not {type(file).__name__}"
        )

    @staticmethod
    def _handle_response(response: requests.Response) -> dict[str, Any]:
        """Parse a response, raising a typed error for non-2xx statuses."""
        request_id = response.headers.get("X-Request-Id")

        if response.ok:
            try:
                return response.json()
            except ValueError as exc:
                raise TablecutError(
                    "API returned a non-JSON success response",
                    status_code=response.status_code,
                    request_id=request_id,
                ) from exc

        # Error envelope: {"error": {"code", "message", "request_id", "docs_url"?}}
        code: str | None = None
        message = f"HTTP {response.status_code}"
        docs_url: str | None = None
        try:
            detail = response.json().get("error", {})
            code = detail.get("code")
            message = detail.get("message") or message
            request_id = detail.get("request_id") or request_id
            docs_url = detail.get("docs_url")
        except ValueError:
            pass  # non-JSON error body (e.g. a proxy page); keep the fallback

        kwargs: dict[str, Any] = {
            "code": code,
            "status_code": response.status_code,
            "request_id": request_id,
            "docs_url": docs_url,
        }
        if response.status_code == 401:
            raise AuthenticationError(message, **kwargs)
        if response.status_code == 429:
            retry_after_header = response.headers.get("Retry-After")
            retry_after = int(retry_after_header) if retry_after_header and retry_after_header.isdigit() else None
            raise RateLimitError(message, retry_after=retry_after, **kwargs)
        if response.status_code >= 500:
            raise ServerError(message, **kwargs)
        raise InvalidRequestError(message, **kwargs)
