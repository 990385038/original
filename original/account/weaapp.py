# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

import logging
import requests
import json

from oauthlib import common
from django.conf import settings
from django.contrib.auth import get_user_model, login
from social_django.utils import load_strategy
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response

from django_validator.decorators import POST
from common import oauth_utils
from .models import SocialAuthUnionID

logger = logging.getLogger(__name__)


User = get_user_model()
PROVIDER = '_WEAAPP'
strategy = load_strategy()
SOCIAL_AUTH_STORAGE = strategy.storage


class WEAAPPAuthAPI(APIView):
    URL = 'https://api.weixin.qq.com/sns/jscode2session'

    @POST('code', type='string', validators='required')
    def post(self, request, code):
        params = {
            'appid': settings.WEAAPP_KEY,
            'secret':settings.WEAAPP_SECRET,
            'js_code': code,
            'grant_type': 'authorization_code',
        }
        access_token = common.generate_token()
        data = requests.post(self.URL, data=params, timeout=600)
        json_data = data.json()
        logger.info('weaapp weixin response: %s', json_data)
        openid = json_data['openid']
        unionid = json_data.get('unionid', '')
        SocialAuthUnionID.objects.get_or_create(provider=PROVIDER, uid=openid, unionid=unionid)
        social = SOCIAL_AUTH_STORAGE.user.get_social_auth(PROVIDER, openid)
        if social:
            user = social.user
        else:
            username = '{}||{}'.format(PROVIDER, openid)
            user, _created = User.objects.get_or_create(
                username=username,
                defaults={
                    'name': '',
                    'avatar': '',
            })
            SOCIAL_AUTH_STORAGE.user.create_social_auth(user, openid, PROVIDER)

        user.backend = 'account.backends.WEAAPPBackend'
        login(request, user)
        access_token = oauth_utils.generate_access_token(user)
        result = {
            'data': {
                'openid': openid,
                'unionid': unionid,
                'is_staff': user.is_staff,
                'access_token': access_token.token,
            }
        }
        return Response(result)


class WEAAPPUserInfoAPI(APIView):
    permission_classes = (IsAuthenticated,)

    @POST('openid', type='string', validators='required')
    @POST('raw_data', type='string', validators='required')
    def post(self, request, openid, raw_data):
        social = SOCIAL_AUTH_STORAGE.user.get_social_auth(PROVIDER, openid)
        userinfo_data = json.loads(raw_data)
        if social:
            social.extra_data = userinfo_data
            social.save()
            user = social.user
            flag = False
            if not user.avatar:
                user.avatar = userinfo_data['avatarUrl']
                flag = True
            if not user.name:
                user.name = userinfo_data['nickName']
                flag = True
            if flag:
                user.save()
        return Response()
