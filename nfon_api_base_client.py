'''module providing authentication methods for the
nfon service portal api'''
import json
import hashlib
import hmac
import base64
import datetime
from configparser import ConfigParser
from string import Formatter

from requests import Session, Request
from requests.exceptions import RequestException
from requests.adapters import HTTPAdapter
from tenacity import retry, stop_after_attempt

from .endpoints import api_endpoints, version

api_retry = retry(stop=stop_after_attempt(3))

class NfonApiBaseClient():
    '''base nfon service portal api client with auth and simple api call functions'''
    def __init__(self, uid, api_key, api_secret, api_base_url):
        self.user_id = uid.upper()
        self.key = api_key
        self.secret = api_secret
        self.base_url = api_base_url
        self._auth_debug = False
        self.timeout = 10
        self.session = Session()
        # retries = Retry(total=5, backoff_factor=1, status_forcelist=[ 502, 503, 504 ])
        adapter = HTTPAdapter(max_retries=3)
        self.session.mount(self.base_url, adapter)
        self.api_endpoints = api_endpoints
        self.ep_version = version


    # #### Auth request_types #### #
    def _get_utc(self):
        '''returns utc time as string formatted for use in the request http headers'''
        return datetime.datetime.now(datetime.UTC).strftime('%a, %d %b %Y %H:%M:%S GMT')

    def _content_md5(self, data=''):
        if data:
            body=json.dumps(data)
        else:
            body = data
        try:
            content_md5 = hashlib.md5(body.encode('utf-8')).hexdigest()
            return content_md5
        except:
            print("Error in creating content_md5: ", data)
            raise

    def _auth_header(self,
            request_type,
            endpoint,
            date,
            content_md5,
            content_type="application/json"):
        '''makes the auth header with following steps:
            - make string to be signed
            - use secret to sign string
            - put the signature and key into a http header
            - return header string'''
        
        # make string to be signed #
        string_to_sign = request_type + "\n" + \
            content_md5 + "\n" +\
            content_type + "\n" +\
            date + "\n" +\
            endpoint
        if self._auth_debug: print(string_to_sign)
    
        # sign the string, creating the signature #
        try:
            digest = hmac.new(
                bytes(self.secret.encode('utf-8')),
                string_to_sign.encode('utf-8'),
                digestmod = hashlib.sha1
            ).digest()
            signature = base64.b64encode(digest).decode()
        except:
            print("Error in creating signature")
            raise

        # return the auth header
        return ("NFON-API " + self.key + ":" + signature)

    def _http_headers(self,
            auth_base_header,
            date,
            host,
            content_md5,
            content_type):
        return({
            "Authorization": auth_base_header, 
            "Date": date, 
            "Host": host, 
            "Content-MD5": content_md5, 
            "Content-Type": content_type, 
            })
    
    def _prep_headers(self,
            request_type,
            endpoint,
            data,
            content_type):
        '''takes the request type and the endpoint
        - endpoint should be preformatted with any variables before this point
        - other variables i.e api key and secret are class variables
        returns headers ready for use in a request
        - data should be a json serializable python object or empty for GET requests
        '''
        try:
            date = self._get_utc()
            if self._auth_debug: print(date)
            content_md5 = self._content_md5(data)
            if self._auth_debug: print(content_md5)
            auth_base_header = self._auth_header(
                request_type,
                endpoint,
                date,
                content_md5,
                content_type)
            if self._auth_debug: print(auth_base_header)
            host = self.base_url.replace('https://', '')
            if self._auth_debug: print(host)
            headers = self._http_headers(
                    auth_base_header,
                    date,
                    host,
                    content_md5,
                    content_type)
            if self._auth_debug: print(headers)
            return headers
        except:
            print('Error with request preparation')
            raise

    # #### END Auth methods #### #
    @api_retry
    def _execute_request(self,
            request_type,
            endpoint,
            data='',
            timeout=None,
            content_type='application/json'):

        if not timeout:
            timeout = self.timeout

        headers = self._prep_headers(
            request_type,
            endpoint,
            data,
            content_type)
        
        # using a session to add retry functionality
        try:
            if data:
                data = json.dumps(data).encode('utf-8')
            url = self.base_url + endpoint
            if self._auth_debug: print(url)
            req = Request(
                request_type,
                url,
                headers=headers,
                data = data)
            prepped = req.prepare()
            resp = self.session.send(prepped, timeout = timeout)
            resp.raise_for_status()
        except RequestException as error:
            print(f"Error fetching data from the API: {error}")
        finally:
            return resp

        
        # # using a simple request
        # try:
        #     if data:
        #         data = json.dumps(data).encode('utf-8')
        #     url = self.base_url + endpoint
        #     if self._auth_debug: print(url)
        #     req = request(
        #         request_type,
        #         url,
        #         data = data,
        #         headers = headers,
        #         timeout = timeout,
        #     )
        #     # response.raise_for_status()  # Raise an exception for HTTP errors
        #     # return response.json()  # Assuming the API returns JSON data
        #     return req
        # except RequestException as error:
        #     print(f"Error fetching data from the API: {error}")

    def get(self, endpoint):
        return self._execute_request('GET', endpoint)

    def post(self, endpoint, data=None):
        return self._execute_request('POST', endpoint, data=data)

    def put(self, endpoint, data=None):
        return self._execute_request('PUT', endpoint, data=data)

    def delete(self, endpoint):
        return self._execute_request('DELETE', endpoint)
    
    def ep_vars(self, key):
        '''returns the variables in the endpoint'''
        return [fn for _, fn, _, _ in Formatter().parse(self.api_endpoints[key])]
    
    def ep(self, key, **kwargs):
        '''returns the endpoint with the variables formatted, if any.
        if there are missing variables the returned error message
        includes all required variables for the endpoint'''
        try:
            endpoint = self.api_endpoints[key]
            try:
                return endpoint.format(**kwargs)
            except KeyError as error:
                f_vars = self.ep_vars(key)
                raise KeyError(f"Missing variable: {error.args[0]}."
                               f"Required variables: {f_vars}."
                                f"Endpoint: {endpoint}") from error
        except KeyError as error:
            raise KeyError(f"Endpoint not found: {key}") from error
        
    def api_test(self):
        r = self.get(self.ep('version'))
        r.raise_for_status()
        print('The Endpoints are up-to-date: ', r.json()['data'][0]['value'] == self.ep_version)
        return r

# Example usage:
# file = open('nfon_api_base_client.py')
# exec(file.read())
if __name__ == "__main__":
    from pprint import PrettyPrinter
    pp = PrettyPrinter()
    config = ConfigParser()
    config.read('config.ini')
    base_url = config['API']['base_url']
    user_id = config['API']['user_id']
    key = config['API']['key']
    secret = config['API']['secret']


    napi = NfonApiBaseClient(user_id, key, secret, base_url)
    # napi.debug = True
    def api_test():
        '''simple get request to confirm that
          the auth is working'''
        if napi.user_id[:1] == 'S':
            systemIntegratorId = napi.user_id
            ep = f'/api/system-integrators/{systemIntegratorId}/customers'
        elif napi.user_id[:1] == 'K':
            identifier = napi.user_id
            ep = f'/api/customers/{identifier}'
        r = napi.get(ep)
        pp.pprint(r.json())
    # do test
    api_test()
