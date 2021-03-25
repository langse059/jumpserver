from typing import Iterable, AnyStr

from django.utils.translation import ugettext_lazy as _
from rest_framework.exceptions import APIException
from requests.exceptions import ReadTimeout
import requests
from django.core.cache import cache
import hashlib

from common.utils.common import get_logger


logger = get_logger(__name__)


class NetError(APIException):
    default_code = 'net_error'
    default_detail = _('Network error, please contact system administrator')


class WeComError(APIException):
    default_code = 'wecom_error'
    default_detail = _('WeCom error, please contact system administrator')


class URL:
    GET_TOKEN = 'https://qyapi.weixin.qq.com/cgi-bin/gettoken'
    SEND_MESSAGE = 'https://qyapi.weixin.qq.com/cgi-bin/message/send'


def update_values(default: dict, others: dict):
    for key in default.keys():
        if key in others:
            default[key] = others[key]


def set_default(data: dict, default: dict):
    for key in default.keys():
        if key not in data:
            data[key] = default[key]


def digest(corpid, corpsecret):
    md5 = hashlib.md5()
    md5.update(corpid.encode())
    md5.update(corpsecret.encode())
    digest = md5.hexdigest()
    return digest


class Requests:
    """
    处理系统级错误，抛出 API 异常，直接生成 HTTP 响应，业务代码无需关心这些错误
    """

    def __init__(self, timeout=None):
        self._request_kwargs = {
            'timeout': timeout
        }

    def get(self, url, params=None, **kwargs):
        try:
            set_default(kwargs, self._request_kwargs)
            return requests.get(url, params=params, **kwargs)
        except ReadTimeout as e:
            logger.exception(e)
            raise NetError

    def post(self, url, data=None, json=None, **kwargs):
        try:
            set_default(kwargs, self._request_kwargs)
            return requests.post(url, data=data, json=json, **kwargs)
        except ReadTimeout as e:
            logger.exception(e)
            raise NetError


class WeCom:
    """
    非业务数据导致的错误直接抛异常，说明是系统配置错误，业务代码不用理会
    """

    def __init__(self, corpid, corpsecret, agentid, timeout=None):
        self._corpid = corpid
        self._corpsecret = corpsecret
        self._agentid = agentid

        self._requests = Requests(timeout=timeout)
        self._init_access_token()

    def _init_access_token(self):
        self._access_token_cache_key = digest(self._corpid, self._corpsecret)

        access_token = cache.get(self._access_token_cache_key)
        if access_token:
            self._access_token = access_token
            return

        # 缓存中没有 access_token ，去企业微信请求
        params = {'corpid': self._corpid, 'corpsecret': self._corpsecret}
        response = self._requests.get(url=URL.GET_TOKEN, params=params)

        if response.status_code != 200:
            # 正常情况下不会返回非 200 响应码
            logger.error(f'Request WeCom error: '
                         f'status_code={response.status_code} '
                         f'\ncontent={response.content}')
            raise WeComError

        data = response.json()
        try:
            # 企业微信返回的数据，不能完全信任，所以字典操作包在异常里
            errcode = data['errcode']

            if errcode != 0:
                # 如果代码写的对，配置没问题，这里不该出错，系统性错误，直接抛异常
                errmsg = data['errmsg']
                logger.error(f'WeCom response 200 but errcode wrong: '
                             f'errcode={errcode} '
                             f'errmsg={errmsg} ')
                raise WeComError

            # 请求成功了
            access_token = data['access_token']
            expires_in = data['expires_in']

            cache.set(self._access_token_cache_key, access_token, expires_in)
            self._access_token = access_token
        except KeyError as e:
            logger.error(f'WeCom response 200 but get field from json error: error={e}')
            raise WeComError

    def send_text(self, users: Iterable, msg: AnyStr, **kwargs):
        """
        https://open.work.weixin.qq.com/api/doc/90000/90135/90236
        """

        extra_params = {
            "safe": 0,
            "enable_id_trans": 0,
            "enable_duplicate_check": 0,
            "duplicate_check_interval": 1800
        }
        update_values(extra_params, kwargs)

        body = {
           "touser": '|'.join(users),
           "msgtype": "text",
           "agentid": self._agentid,
           "text": {
               "content": msg
           },
           **extra_params
        }
        params = {'access_token': self._access_token}
        response = self._requests.post(URL.SEND_MESSAGE, params=params, json=body)
        return response
