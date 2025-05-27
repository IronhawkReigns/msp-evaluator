

# -*- coding: utf-8 -*-
import base64
import json
import http.client
import uuid
import os
from http import HTTPStatus

class Executor:
    def __init__(self):
        self._host = "clovastudio.stream.ntruss.com"
        self._api_key = os.getenv("CLOVA_API_KEY")
        self._request_id = str(uuid.uuid4())

    def _send_request(self, request):
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'Authorization': self._api_key,
            'X-NCP-CLOVASTUDIO-REQUEST-ID': self._request_id,
        }

        conn = http.client.HTTPSConnection(self._host)
        conn.request('POST', '/testapp/v1/routers/haxvawqc/versions/1/route', json.dumps(request), headers)
        response = conn.getresponse()
        status = response.status
        result = json.loads(response.read().decode(encoding='utf-8'))
        conn.close()
        return result, status

    def execute(self, request):
        res, status = self._send_request(request)
        print("📦 CLOVA Router raw response:", res)
        print("📦 CLOVA Router HTTP status:", status)

        if status == HTTPStatus.OK and isinstance(res, dict) and "result" in res:
            return res["result"]
        else:
            return {
                "error": "Router 호출 실패",
                "raw_status": status,
                "response": res
            }
