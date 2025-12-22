import requests
from utils.util import *

class PLAIN_API:
    def __init__(self, ip: str = "192.168.11.1", port: int = 1448):
        """
        Configures a simple REST client for the AMR with base URL and headers.
        args:
         - ip: string IPv4/host for the target device.
         - port: integer TCP port serving the HTTP API.
        return:
         - None: initializes base URL and default headers.
        """
        self.base_url = f"http://{ip}:{port}"
        self.headers_json = {"Content-Type": "application/json"}
        self.headers_accept = {"Accept": "application/json"}

    def _get(self, endpoint):
        """
        Performs a GET request against an API endpoint with error handling.
        args:
         - endpoint: string path to append to the base URL.
        return:
         - dict or None: JSON-decoded response body, or None on error.
        """
        try:
            resp = requests.get(f"{self.base_url}{endpoint}", headers=self.headers_accept)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            print(f"❌ GET {endpoint} failed:", e)
            return None

    def _post(self, endpoint, payload=None):
        """
        Performs a POST request with a JSON payload and robust error handling.
        args:
         - endpoint: string path to append to the base URL.
         - payload: dict or None JSON body to send in the request.
        return:
         - dict or None: JSON-decoded response body, or None on error.
        """
        try:
            resp = requests.post(f"{self.base_url}{endpoint}", headers=self.headers_json, json=payload)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            print(f"❌ POST {endpoint} failed:", e)
            return None
    
    def _put(self, endpoint, payload=None):
        """
        Performs a PUT request with a JSON payload to update a resource.
        args:
         - endpoint: string path to append to the base URL.
         - payload: dict or None JSON body to send in the request.
        return:
         - dict or None: JSON-decoded response body, or None on error.
        """
        try:
            resp = requests.put(f"{self.base_url}{endpoint}", headers=self.headers_json, json=payload)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            print(f"❌ PUT {endpoint} failed:", e)
            return None

    def _delete(self, endpoint):
        """
        Issues a DELETE request to remove a resource at the endpoint.
        args:
         - endpoint: string path to append to the base URL.
        return:
         - dict or None: JSON-decoded response or status dict, or None on error.
        """
        try:
            resp = requests.delete(f"{self.base_url}{endpoint}", headers=self.headers_accept)
            resp.raise_for_status()
            return {"status": "deleted"} if resp.text == "" else resp.json()
        except requests.RequestException as e:
            print(f"❌ DELETE {endpoint} failed:", e)
            return None