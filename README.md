# NFON Service Portal API Client

EN:  
Starter client for authenticated access to the NFON Service Portal API.  
DE:  
Einfacher Einstieg in die authentifizierte Nutzung der NFON Service Portal API.

📄 Link to official docs:  
https://www.nfon.com/en/service/documentation/manuals/web-applications/nfon-service-portal-api/nfon-service-portal-api-manual/

## Installation

Clone this repository or install as part of your project.

## Example Usage

```python
from nfon_api_client import NfonApiBaseClient

napi = NfonApiBaseClient(
    uid="KXXXX",
    api_key="your_key",
    api_secret="your_secret",
    api_base_url="https://nfon.example.com"
)

# Use .ep(key, **kwargs) to resolve endpoints
endpoint = napi.ep('customers')
response = napi.get(endpoint)

# Use a customer-specific endpoint
customer_id = "K123456"
endpoint = napi.ep('customer_basic_data', customer_id=customer_id)
response = napi.get(endpoint)
print(response.json())

```

Or start building your own Subclass to fit your needs:

```python
from nfon_api_client import NfonApiBaseClient

class NfonApiClient(NfonApiBaseClient):
    def __init__(self, user_id, key, secret, base_url):
        super().__init__(user_id, key, secret, base_url)

    @staticmethod
    def list_to_dict(data):
        return {item['name']: item['value'] for item in data}

    @staticmethod
    def dict_to_list(data, key='name', value='value'):
        return [{key: k, value: v} for k, v in data.items()]
  # etc...etc...
```
## Error Handling

This library defines custom exceptions to help you handle different failure modes cleanly:

- `NFONApiError` – Base class for all API-related errors
- `AuthHeaderError` – Raised when the authentication header cannot be generated
- `RequestFailed` – Raised when an HTTP request fails (e.g., network issue or server error)
- `EndpointFormatError` – Raised when `.ep()` is called with missing or incorrect arguments

### Example:

```python
from nfon_api_client import NfonApiBaseClient
from nfon_api_client.exceptions import RequestFailed, AuthHeaderError

napi = NfonApiBaseClient("KXXXX", "your_key", "your_secret", "https://nfon.example.com")

try:
    response = napi.get(napi.ep('version'))
    print(response.json())
except RequestFailed as e:
    print("Request failed:", e)
except AuthHeaderError as e:
    print("Header generation failed:", e)

```
