# Python client for the Tablecut API — https://tablecut.com

from __future__ import annotations

import os
from typing import Any, BinaryIO, Iterable, Union

import requests

__all__ = [
    'Tablecut',
    'TablecutError',
    'AuthenticationError',
    'RateLimitError',
    'InvalidRequestError',
    'ServerError',
]

__version__ = '0.1.0'

DEFAULT_BASE_URL = 'https://tablecut.com/v1'
DEFAULT_TIMEOUT = 120.0

FileInput = Union[str, 'os.PathLike[str]', bytes, BinaryIO]


class TablecutError(Exception):
    # Base error. Switch on `code`, never parse `message`.
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
            parts.append(f'(code: {self.code})')
        if self.request_id:
            parts.append(f'(request_id: {self.request_id})')
        return ' '.join(parts)


class AuthenticationError(TablecutError):  # 401
    pass


class RateLimitError(TablecutError):  # 429; code is rate_limited or quota_exceeded
    def __init__(self, message: str, *, retry_after: int | None = None, **kwargs: Any) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after  # seconds, if known


class InvalidRequestError(TablecutError):  # other 4xx
    pass


class ServerError(TablecutError):  # 5xx; nothing is billed
    pass


class Tablecut:
    # api_key defaults to the TABLECUT_API_KEY env var.
    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        session: requests.Session | None = None,
    ) -> None:
        resolved = api_key if api_key is not None else os.environ.get('TABLECUT_API_KEY')
        if not resolved:
            raise AuthenticationError(
                'No API key provided. Pass api_key=... or set TABLECUT_API_KEY. '
                'Get a key at https://tablecut.com'
            )
        self.api_key = resolved
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self._owns_session = session is None
        self._session = session or requests.Session()

    def extract(
        self,
        file: FileInput,
        *,
        pages: str = 'all',  # 'all' or 1-indexed selection like '1,3,5-10'
        format: str | Iterable[str] = 'json',  # any of: json, markdown, csv
        filename: str | None = None,
    ) -> dict[str, Any]:
        data, resolved_name = self._read_file(file, filename)
        format_param = format if isinstance(format, str) else ','.join(format)
        response = self._session.post(
            f'{self.base_url}/extract',
            headers={'X-API-Key': self.api_key},
            files={'file': (resolved_name, data, 'application/pdf')},
            data={'pages': pages, 'format': format_param},
            timeout=self.timeout,
        )
        return self._handle_response(response)

    def health(self) -> dict[str, Any]:
        response = self._session.get(f'{self.base_url}/health', timeout=self.timeout)
        return self._handle_response(response)

    def close(self) -> None:
        if self._owns_session:
            self._session.close()

    def __enter__(self) -> 'Tablecut':
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    @staticmethod
    def _read_file(file: FileInput, filename: str | None) -> tuple[bytes, str]:
        if isinstance(file, bytes):
            return file, filename or 'document.pdf'
        if isinstance(file, (str, os.PathLike)):
            path = os.fspath(file)
            with open(path, 'rb') as handle:
                return handle.read(), filename or os.path.basename(path)
        if hasattr(file, 'read'):
            data = file.read()
            if not isinstance(data, bytes):
                raise TypeError("file must be opened in binary mode ('rb')")
            inferred = filename or os.path.basename(getattr(file, 'name', '') or '') or 'document.pdf'
            return data, inferred
        raise TypeError(
            f'file must be a path, bytes, or a binary file object, not {type(file).__name__}'
        )

    @staticmethod
    def _handle_response(response: requests.Response) -> dict[str, Any]:
        request_id = response.headers.get('X-Request-Id')

        if response.ok:
            try:
                return response.json()
            except ValueError as exc:
                raise TablecutError(
                    'API returned a non-JSON success response',
                    status_code=response.status_code,
                    request_id=request_id,
                ) from exc

        code: str | None = None
        message = f'HTTP {response.status_code}'
        docs_url: str | None = None
        try:
            detail = response.json().get('error', {})
            code = detail.get('code')
            message = detail.get('message') or message
            request_id = detail.get('request_id') or request_id
            docs_url = detail.get('docs_url')
        except ValueError:
            pass

        kwargs: dict[str, Any] = {
            'code': code,
            'status_code': response.status_code,
            'request_id': request_id,
            'docs_url': docs_url,
        }
        if response.status_code == 401:
            raise AuthenticationError(message, **kwargs)
        if response.status_code == 429:
            header = response.headers.get('Retry-After')
            retry_after = int(header) if header and header.isdigit() else None
            raise RateLimitError(message, retry_after=retry_after, **kwargs)
        if response.status_code >= 500:
            raise ServerError(message, **kwargs)
        raise InvalidRequestError(message, **kwargs)
