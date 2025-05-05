import os
import json
import hashlib
import hmac
import base64
import datetime
import logging
from string import Formatter
from typing import Optional, Dict, Any

from requests import Session, Request
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from tenacity import retry, stop_after_attempt

from .exceptions import (
    NFONApiError,
    AuthHeaderError,
    EndpointFormatError,
    RequestFailed,
    )
from .endpoints import api_endpoints, version

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG if 'DEBUG' in os.environ else logging.INFO)

# Retry config shared across requests
api_retry = retry(stop=stop_after_attempt(3))


from .exceptions import NFONApiError, AuthHeaderError, EndpointFormatError, RequestFailed

class NfonApiBaseClient:
    """
    Authenticated client for the NFON Service Portal API.

    Handles HMAC signature generation, header preparation,
    endpoint formatting, and retryable HTTP calls.
    """

    def __init__(self, uid: str, api_key: str, api_secret: str, api_base_url: str, debug: bool = False):
        """
        Initialize a new API client.

        :param uid: User ID (e.g., Kxxxx or Sxxxx)
        :param api_key: API key
        :param api_secret: API secret
        :param api_base_url: API base URL
        :param debug: Enable verbose debug logging
        """
        self.user_id = uid.upper()
        self.key = api_key
        self.secret = api_secret
        self.base_url = api_base_url.rstrip('/')
        self.api_endpoints = api_endpoints
        self.ep_version = version
        self.timeout = 10
        self.debug = debug

        self.session = Session()
        adapter = HTTPAdapter(max_retries=3)
        self.session.mount(self.base_url, adapter)

    def _get_utc(self) -> str:
        """Return the current UTC time formatted for the Date header."""
        return datetime.datetime.now(datetime.UTC).strftime('%a, %d %b %Y %H:%M:%S GMT')

    def _content_md5(self, data: Any = '') -> str:
        """
        Generate an MD5 hash of the request body.

        :param data: JSON-serializable data
        :return: MD5 hash as hex string
        """
        try:
            body = json.dumps(data) if data else ''
            # TODO: spec wants base64, test and change if there is a bug here.
            # return base64.b64encode(hashlib.md5(body.encode('utf-8')).digest()).decode()
            return hashlib.md5(body.encode('utf-8')).hexdigest()
        except Exception as e:
            logger.error("Error creating content_md5", exc_info=e)
            raise AuthHeaderError("Failed to create MD5 hash") from e

    def _auth_header(self, request_type: str, endpoint: str, date: str,
                     content_md5: str, content_type: str = "application/json") -> str:
        """
        Generate the Authorization header using HMAC-SHA1.

        :raises AuthHeaderError: if signing fails
        """
        to_sign = f"{request_type}\n{content_md5}\n{content_type}\n{date}\n{endpoint}"
        if self.debug:
            logger.debug("String to sign:\n%s", to_sign)

        try:
            digest = hmac.new(
                self.secret.encode('utf-8'),
                to_sign.encode('utf-8'),
                hashlib.sha1
            ).digest()
            signature = base64.b64encode(digest).decode()
            return f"NFON-API {self.key}:{signature}"
        except Exception as e:
            logger.error("Error generating HMAC signature", exc_info=e)
            raise AuthHeaderError("Failed to generate authorization header") from e

    def _prep_headers(self, method: str, endpoint: str, data: Any,
                      content_type: str) -> Dict[str, str]:
        """
        Prepare request headers for the given request.

        :raises AuthHeaderError: on header construction failure
        """
        try:
            date = self._get_utc()
            content_md5 = self._content_md5(data)
            auth_header = self._auth_header(method, endpoint, date, content_md5, content_type)
            host = self.base_url.replace("https://", "")

            headers = {
                "Authorization": auth_header,
                "Date": date,
                "Host": host,
                "Content-MD5": content_md5,
                "Content-Type": content_type
            }

            if self.debug:
                logger.debug("Prepared headers: %s", headers)

            return headers
        except Exception as e:
            raise AuthHeaderError("Failed to prepare request headers") from e

    @api_retry
    def _execute_request(self, method: str, endpoint: str,
                         data: Optional[Any] = '', timeout: Optional[int] = None,
                         content_type: str = "application/json"):
        """
        Execute an HTTP request with retries and authentication.

        :raises RequestFailed: on request or response error
        """
        timeout = timeout or self.timeout
        headers = self._prep_headers(method, endpoint, data, content_type)

        try:
            if data:
                data = json.dumps(data).encode('utf-8')

            url = f"{self.base_url}{endpoint}"
            if self.debug:
                logger.debug("Request URL: %s", url)

            req = Request(method, url, headers=headers, data=data)
            prepped = self.session.prepare_request(req)
            resp = self.session.send(prepped, timeout=timeout)
            resp.raise_for_status()
            return resp
        except RequestException as e:
            raise RequestFailed(f"{method} {endpoint} failed") from e

    def get(self, endpoint: str):
        """Send a GET request."""
        return self._execute_request('GET', endpoint)

    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None):
        """Send a POST request with optional JSON data."""
        return self._execute_request('POST', endpoint, data=data)

    def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None):
        """Send a PUT request with optional JSON data."""
        return self._execute_request('PUT', endpoint, data=data)

    def delete(self, endpoint: str):
        """Send a DELETE request."""
        return self._execute_request('DELETE', endpoint)

    def ep_vars(self, key: str):
        """Return the required variables for a given endpoint key."""
        return [fn for _, fn, _, _ in Formatter().parse(self.api_endpoints[key])]

    def ep(self, key: str, **kwargs):
        """
        Format a named endpoint with variables.

        :raises EndpointFormatError: if variables are missing or key is unknown
        """
        try:
            endpoint = self.api_endpoints[key]
        except KeyError as e:
            raise EndpointFormatError(f"Endpoint not found: {key}") from e

        try:
            return endpoint.format(**kwargs)
        except KeyError as e:
            required = self.ep_vars(key)
            raise EndpointFormatError(
                f"Missing variable: {e.args[0]}. Required: {required}. Endpoint: {endpoint}"
            ) from e

    def api_test(self):
        """
        Deprecated. Replaced by check_connection().
        """
        return self.check_connection()

    def check_connection(self):
        """
        Check API connectivity and optionally compare versions.

        - Confirms API is reachable and credentials work.
        - Logs a warning if the API version does not match the documented version.
        - Returns the actual API version string (or None if undetectable).
        """
        try:
            response = self.get(self.ep('version'))
            data = response.json()

            version_list = data.get("data")
            if isinstance(version_list, list) and version_list:
                current_version = version_list[0].get("value")
            else:
                current_version = None

            if current_version:
                if current_version != self.ep_version:
                    logger.warning(
                        f"API version mismatch: received '{current_version}', expected '{self.ep_version}'."
                    )
                else:
                    logger.info(f"API version match confirmed: {current_version}")
            else:
                logger.warning("Could not determine API version from response.")

            return current_version

        except Exception as e:
            logger.warning(f"API connection failed or unexpected response: {e}")
            return None

