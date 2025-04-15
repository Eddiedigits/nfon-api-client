# NFON Service Portal API

EN:
This is starter code to help get past the Authentication roadblock.

DE:
Der Code soll helfen, die Schwierigkeiten mit der Authentifizierung zu überwinden.

Link to General Information from NFON
https://www.nfon.com/en/service/documentation/manuals/serviceportalapi

Example Usage:

```python
import configparser
from .nfon_api_base_client import NfonApiBaseClient

config = configparser.ConfigParser()
config.read('config.ini')

napi = NfonApiBaseClient(config['user_id'], config['key'], config['secret'], config['base_url'])
knum = KXXXX
ep = napi.ep('targets', customer_id=knum)
response = napi.get(ep)
```

Or start building your own Subclass to fit your needs:

```python
from .nfon_api_base_client import NfonApiBaseClient

class NfonApiClient(NfonApiBaseClient):
    '''napi = NfonApiClient(user_id, key, secret, base_url)'''
    def __init__(self, user_id, key, secret, base_url):
        super().__init__(user_id, key, secret, base_url)

    @staticmethod
    def list_to_dict(data):
        '''converts a list of key value pairs to a dict'''
        dct = {}
        for item in data:
            k,v = tuple(item.values())
            dct[k] = v
        return dct
    
    @staticmethod
    def dict_to_list(data, key='name', value='value'):
        '''converts a dict to a list of key value pairs'''
        return [{key: k, value: v} for k, v in data.items()]

  # etc...etc...
```
