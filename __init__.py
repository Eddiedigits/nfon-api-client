
try:
    from .nfon_api_base_client import NfonApiBaseClient
except ImportError:
    from modules.nfon_api.nfon_api_base_client import NfonApiBaseClient