
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
即梦AI完整API实现 - Python版本
"""

import hashlib
import hmac
import json
import random
import time
import uuid
import requests
import base64
import urllib.parse
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
import os
from pathlib import Path
import binascii
import asyncio
from pprint import pprint
import gzip
import zlib # <--- 导入zlib用于deflate
import brotli # <--- 导入brotli

# CRC32实现
try:
    import zlib
    def crc32(data):
        return zlib.crc32(data) & 0xffffffff
except ImportError:
    def crc32(data):
        return binascii.crc32(data) & 0xffffffff

class JimengCompleteAPI:
    """即梦AI完整功能API - Python实现"""
    
    def __init__(self, refresh_token: str = None):
        print("      [CORE_DEBUG] JimengCompleteAPI.__init__ called.")
        self.refresh_token = refresh_token or os.getenv('JIMENG_API_TOKEN', '')
        if not self.refresh_token:
            print("      [CORE_ERROR] Token not provided.")
            raise ValueError('JIMENG_API_TOKEN 环境变量未设置或未提供refresh_token参数')
        
        self.MODEL_MAP = {
            "jimeng-4.5":"high_aes_general_v40l",
            "jimeng-4.0":"high_aes_general_v40",
            'jimeng-3.1': 'high_aes_general_v30l_art_fangzhou:general_v3.0_18b',
            'jimeng-3.0': 'high_aes_general_v30l:general_v3.0_18b', 
            'jimeng-2.1': 'high_aes_general_v21_L:general_v2.1_L',
            'jimeng-2.0-pro': 'high_aes_general_v20_L:general_v2.0_L',
            'jimeng-2.0': 'high_aes_general_v20:general_v2.0',
            'jimeng-1.4': 'high_aes_general_v14:general_v1.4',
            'jimeng-xl-pro': 'text2img_xl_sft',
            'jimeng-video-3.0-pro': 'dreamina_ic_generate_video_model_vgfm_3.0_pro',
            'jimeng-video-3.0-fast': 'dreamina_ic_generate_video_model_vgfm_3.0_fast',
            'jimeng-video-3.0': 'dreamina_ic_generate_video_model_vgfm_3.0',
            'jimeng-video-2.0': 'dreamina_ic_generate_video_model_vgfm_lite',
            'jimeng-video-2.0-pro': 'dreamina_ic_generate_video_model_vgfm1.0'
        }
        
        # 视频支持的宽高比配置
        self.VIDEO_RATIO_MAP = {
            '9:16': '9:16',  # 竖屏
            '3:4': '3:4',    # 竖屏
            '1:1': '1:1',    # 正方形
            '4:3': '4:3',    # 横屏
            '16:9': '16:9',  # 横屏
            '21:9': '21:9'   # 超宽屏
        }
        
        # 图片支持的宽高比及其对应的分辨率配置
        self.IMAGE_RATIO_MAP = {
            '4:3': {'width': 1472, 'height': 1104},  # 横屏
            '3:2': {'width': 1584, 'height': 1056},  # 横屏
            '2:3': {'width': 1056, 'height': 1584},  # 竖屏
            '21:9': {'width': 2016, 'height': 864},  # 超宽屏
            '16:9': {'width': 1664, 'height': 936},  # 横屏
            '9:16': {'width': 936, 'height': 1664},  # 竖屏
            '1:1': {'width': 1328, 'height': 1328},  # 正方形
            '3:4': {'width': 1104, 'height': 1472}   # 竖屏
        }
        
        # 2K分辨率配置
        self.IMAGE_RATIO_MAP_2K = {
            '4:3': {'width': 2304, 'height': 1728},
            '3:2': {'width': 2496, 'height': 1664},
            '2:3': {'width': 1664, 'height': 2496},
            '21:9': {'width': 3024, 'height': 1296},
            '16:9': {'width': 2560, 'height': 1440},
            '9:16': {'width': 1440, 'height': 2560},
            '1:1': {'width': 2048, 'height': 2048},
            '3:4': {'width': 1728, 'height': 2304}
        }
        
        self.DEFAULT_MODEL = 'jimeng-3.1'
        self.DEFAULT_VIDEO_MODEL = 'jimeng-video-3.0'
        self.DEFAULT_BLEND_MODEL = 'jimeng-3.0'
        self.DRAFT_VERSION = '3.0.2'
        self.DEFAULT_ASSISTANT_ID = '513695'
        
        self.WEB_ID = int(random.random() * 999999999999999999 + 7000000000000000000)
        self.USER_ID = str(uuid.uuid4()).replace('-', '')
        self.UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        
        self.BASE_URL = 'https://jimeng.jianying.com'
        self.UPLOAD_URL = 'https://imagex.bytedanceapi.com/'
        print("      [CORE_DEBUG] JimengCompleteAPI instance created successfully.")

    def get_model(self, model: str) -> str:
        return self.MODEL_MAP.get(model, self.MODEL_MAP[self.DEFAULT_MODEL])
    
    def generate_uuid(self) -> str:
        return str(uuid.uuid4())
    
    def generate_ms_token(self, length: int = 128) -> str:
        base_str = 'ABCDEFGHIGKLMNOPQRSTUVWXYZabcdefghigklmnopqrstuvwxyz0123456789='
        random_str = ''
        base_length = len(base_str) - 1
        for _ in range(length):
            random_str += base_str[random.randint(0, base_length)]
        return random_str
    
    def to_url_params(self, params: Dict[str, Any]) -> str:
        return "&".join([f"{key}={value}" for key, value in params.items()])
    
    def generate_cookie(self) -> str:
        unix_timestamp = int(time.time())
        cookie_parts = [
            f"_tea_web_id={self.WEB_ID}", "is_staff_user=false", "store-region=cn-gd",
            "store-region-src=uid", f"sid_guard={self.refresh_token}%7C{unix_timestamp}%7C5184000%7CMon%2C+03-Feb-2025+08%3A17%3A09+GMT",
            f"uid_tt={self.USER_ID}", f"uid_tt_ss={self.USER_ID}", f"sid_tt={self.refresh_token}",
            f"sessionid={self.refresh_token}", f"sessionid_ss={self.refresh_token}", f"sid_tt={self.refresh_token}"
        ]
        return "; ".join(cookie_parts)
    
    async def request(self, method: str, path: str, data: Any = None, params: Any = None, headers: Any = None) -> Any:
        url = path if path.startswith('https://') else f"{self.BASE_URL}{path}"
        fake_headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-language": "zh-CN,zh;q=0.9",
            "Cache-control": "no-cache",
            "Origin": "https://jimeng.jianying.com",
            "Pragma": "no-cache",
            "Referer": "https://jimeng.jianying.com/ai-tool/generate?type=image",
            "Sec-Ch-Ua": '"Google Chrome";v="141", "Not?A_Brand";v="8", "Chromium";v="141"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": self.UA,
            "appid": self.DEFAULT_ASSISTANT_ID,
            "appvr": "8.4.0",
            "lan": "zh-Hans",
            "loc": "cn",
            "pf": "7"
        }
        request_headers = {**fake_headers, 'Cookie': self.generate_cookie()}
        if headers: request_headers.update(headers)
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, params=params or data, headers=request_headers, timeout=60)
            elif method.upper() == 'POST':
                if isinstance(data, bytes):
                    response = requests.post(url, data=data, params=params, headers=request_headers, timeout=60)
                else:
                    # 【重要】设置 stream=True 以便后续可以读取原始字节流
                    response = requests.post(url, json=data, params=params, headers=request_headers, timeout=60, stream=True)
            else: raise ValueError(f"不支持的HTTP方法: {method}")
            
            response.raise_for_status()

            # 【终极修复】实现健壮的解压和解析链
            raw_content = response.content # 读取原始字节
            
            # 1. 尝试直接解析 (无压缩)
            try:
                return json.loads(raw_content.decode('utf-8'))
            except (json.JSONDecodeError, UnicodeDecodeError):
                print("      [CORE_WARN] 直接解析JSON失败，尝试解压...")

            # 2. 尝试 Gzip 解压
            try:
                decompressed = gzip.decompress(raw_content)
                print("      [CORE_DEBUG] Gzip解压成功。")
                return json.loads(decompressed.decode('utf-8'))
            except (gzip.BadGzipFile, json.JSONDecodeError, UnicodeDecodeError):
                print("      [CORE_WARN] Gzip解压失败，尝试Brotli...")

            # 3. 尝试 Brotli 解压
            try:
                decompressed = brotli.decompress(raw_content)
                print("      [CORE_DEBUG] Brotli解压成功。")
                return json.loads(decompressed.decode('utf-8'))
            except (brotli.error, json.JSONDecodeError, UnicodeDecodeError):
                print("      [CORE_WARN] Brotli解压失败，尝试Deflate...")

            # 4. 尝试 Deflate (zlib) 解压
            try:
                decompressed = zlib.decompress(raw_content)
                print("      [CORE_DEBUG] Deflate (zlib)解压成功。")
                return json.loads(decompressed.decode('utf-8'))
            except (zlib.error, json.JSONDecodeError, UnicodeDecodeError):
                print("      [CORE_ERROR] 所有解压和解析尝试均失败。")
                raise Exception(f"无法处理的API响应格式。内容开头: {raw_content[:100]}")

        except requests.exceptions.RequestException as e:
            print(f"      [CORE_ERROR] 即梦API请求失败: {e}")
            raise Exception(f"即梦API请求失败: {str(e)}")

    # ===== 图片上传相关方法 (移植自 jimeng_complete_api111.py) =====
    
    def get_file_content(self, file_path: str) -> bytes:
        """获取文件内容"""
        try:
            if file_path.startswith(('https://', 'http://')):
                response = requests.get(file_path, timeout=30)
                response.raise_for_status()
                return response.content
            else:
                absolute_path = os.path.abspath(file_path)
                with open(absolute_path, 'rb') as f:
                    return f.read()
        except Exception as error:
            print(f'读取文件失败: {error}')
            raise Exception(f'读取文件失败: {file_path}')
    
    def generate_random_string(self, length: int) -> str:
        """生成随机字符串"""
        characters = 'abcdefghijklmnopqrstuvwxyz0123456789'
        return ''.join(random.choice(characters) for _ in range(length))
    
    def add_headers(self, amz_date: str, session_token: str, request_body: Any) -> Dict[str, str]:
        """生成请求所需Header"""
        headers = {
            'X-Amz-Date': amz_date,
            'X-Amz-Security-Token': session_token,
        }
        if request_body and len(str(request_body)) > 0:
            content_sha256 = hashlib.sha256(json.dumps(request_body).encode()).hexdigest()
            headers['X-Amz-Content-Sha256'] = content_sha256
        return headers
    
    def credential_string(self, amz_date: str, region: str, service: str) -> str:
        """获取credentialString"""
        return '/'.join([amz_date[:8], region, service, 'aws4_request'])
    
    def http_build_query(self, params: Dict[str, Any]) -> str:
        """生成http请求参数字符串"""
        if not params:
            return ''
        query_parts = []
        for key, value in params.items():
            query_parts.append(f"{key}={value}")
        return '&'.join(query_parts)
    
    def signed_headers(self, request_headers: Dict[str, str]) -> str:
        """生成签名头列表"""
        headers = [key.lower() for key in request_headers.keys()]
        return ';'.join(sorted(headers))
    
    def canonical_string(self, request_method: str, request_params: Any,
                        request_headers: Dict[str, str], request_body: Any) -> str:
        """生成canonicalString"""
        canonical_headers = []
        header_keys = sorted([key.lower() for key in request_headers.keys()])
        for key in header_keys:
            original_key = next(k for k in request_headers.keys() if k.lower() == key)
            canonical_headers.append(f"{key}:{request_headers[original_key]}")
        canonical_headers_str = '\n'.join(canonical_headers) + '\n'
        
        body = ''
        if request_body and len(str(request_body)) > 0:
            body = json.dumps(request_body)
        
        canonical_string_arr = [
            request_method.upper(),
            '/',
            self.http_build_query(request_params) if request_params else '',
            canonical_headers_str,
            self.signed_headers(request_headers),
            hashlib.sha256(body.encode()).hexdigest()
        ]
        
        return '\n'.join(canonical_string_arr)
    
    def signature(self, secret_access_key: str, amz_date: str, region: str, service: str,
                 request_method: str, request_params: Any, request_headers: Dict[str, str],
                 request_body: Any) -> str:
        """生成AWS签名"""
        amz_day = amz_date[:8]
        k_date = hmac.new(f'AWS4{secret_access_key}'.encode(), amz_day.encode(), hashlib.sha256).digest()
        k_region = hmac.new(k_date, region.encode(), hashlib.sha256).digest()
        k_service = hmac.new(k_region, service.encode(), hashlib.sha256).digest()
        signing_key = hmac.new(k_service, 'aws4_request'.encode(), hashlib.sha256).digest()
        
        string_to_sign_arr = [
            'AWS4-HMAC-SHA256',
            amz_date,
            self.credential_string(amz_date, region, service),
            hashlib.sha256(
                self.canonical_string(request_method, request_params, request_headers, request_body).encode()
            ).hexdigest()
        ]
        string_to_sign = '\n'.join(string_to_sign_arr)
        
        return hmac.new(signing_key, string_to_sign.encode(), hashlib.sha256).hexdigest()
    
    def generate_authorization_and_header(self, access_key_id: str, secret_access_key: str,
                                        session_token: str, region: str, service: str,
                                        request_method: str, request_params: Any,
                                        request_body: Any = None) -> Dict[str, str]:
        """生成请求所需Header和Authorization"""
        now = datetime.utcnow()
        iso_string = now.isoformat() + 'Z'
        amz_date = iso_string.replace('-', '').replace(':', '').replace('.', '')[:-7] + 'Z'
        
        request_headers = self.add_headers(amz_date, session_token, request_body)
        
        if request_body and len(str(request_body)) > 0:
            request_headers['X-Amz-Content-Sha256'] = hashlib.sha256(
                json.dumps(request_body).encode()
            ).hexdigest()
        
        authorization_params = [
            f'AWS4-HMAC-SHA256 Credential={access_key_id}/{self.credential_string(amz_date, region, service)}',
            f'SignedHeaders={self.signed_headers(request_headers)}',
            f'Signature={self.signature(secret_access_key, amz_date, region, service, request_method, request_params, request_headers, request_body)}'
        ]
        authorization = ', '.join(authorization_params)
        
        headers = dict(request_headers)
        headers['Authorization'] = authorization
        return headers
    
    async def get_upload_auth(self) -> Dict[str, Any]:
        """获取上传凭证所需Ak和Tk"""
        try:
            auth_res = await self.request(
                'POST',
                '/mweb/v1/get_upload_token?aid=513695&da_version=3.2.2&aigc_features=app_lip_sync',
                {'scene': 2}
            )
            
            if not auth_res.get('data'):
                raise Exception(auth_res.get('errmsg', '获取上传凭证失败,账号可能已掉线!'))
            
            return auth_res['data']
            
        except Exception as err:
            print(f'获取上传凭证失败: {err}')
            raise err
    
    async def upload_file(self, url: str, file_content: bytes, headers: Dict[str, str]) -> Any:
        """上传文件到远程服务器"""
        return await self.request('POST', url, file_content, {}, headers)
    
    async def upload_cover_file(self, file_path: str) -> str:
        """上传文件 - 三步上传流程"""
        try:
            print(f'      [CORE_DEBUG] Step B: 开始上传文件: {file_path}')
            
            # 第一步：获取上传令牌
            upload_auth = await self.get_upload_auth()
            
            # 获取图片数据和CRC32
            image_data = self.get_file_content(file_path)
            image_crc32 = hex(crc32(image_data))[2:]
            
            # 第二步：获取图片上传凭证
            get_upload_image_proof_request_params = {
                'Action': 'ApplyImageUpload',
                'FileSize': len(image_data),
                'ServiceId': 'tb4s082cfz',
                'Version': '2018-08-01',
                's': self.generate_random_string(11),
            }
            
            request_headers_info = self.generate_authorization_and_header(
                upload_auth['access_key_id'],
                upload_auth['secret_access_key'],
                upload_auth['session_token'],
                'cn-north-1',
                'imagex',
                'GET',
                get_upload_image_proof_request_params
            )
            
            upload_img_res = await self.request(
                'GET',
                f"{self.UPLOAD_URL}?{self.http_build_query(get_upload_image_proof_request_params)}",
                {},
                {},
                request_headers_info
            )
            
            if upload_img_res.get('ResponseMetadata', {}).get('Error'):
                raise Exception(upload_img_res['ResponseMetadata']['Error']['Message'])
            
            if 'Result' not in upload_img_res:
                raise Exception(f"上传凭证响应格式错误: {upload_img_res}")
            
            upload_address = upload_img_res['Result']['UploadAddress']
            upload_img_url = f"https://{upload_address['UploadHosts'][0]}/upload/v1/{upload_address['StoreInfos'][0]['StoreUri']}"
            
            # 第三步：上传图片
            image_upload_res = await self.upload_file(
                upload_img_url,
                image_data,
                {
                    'Authorization': upload_address['StoreInfos'][0]['Auth'],
                    'Content-Crc32': image_crc32,
                    'Content-Type': 'application/octet-stream',
                }
            )
            
            if image_upload_res.get('code') != 2000:
                raise Exception(image_upload_res.get('message', '上传失败'))
            
            # 第四步：提交上传确认
            commit_img_params = {
                'Action': 'CommitImageUpload',
                'FileSize': len(image_data),
                'ServiceId': 'tb4s082cfz',
                'Version': '2018-08-01',
            }
            
            commit_img_content = {'SessionKey': upload_address['SessionKey']}
            
            commit_img_head = self.generate_authorization_and_header(
                upload_auth['access_key_id'],
                upload_auth['secret_access_key'],
                upload_auth['session_token'],
                'cn-north-1',
                'imagex',
                'POST',
                commit_img_params,
                commit_img_content
            )
            
            commit_img = await self.request(
                'POST',
                f"{self.UPLOAD_URL}?{self.http_build_query(commit_img_params)}",
                commit_img_content,
                {},
                {**commit_img_head, 'Content-Type': 'application/json'}
            )
            
            if commit_img.get('ResponseMetadata', {}).get('Error'):
                raise Exception(commit_img['ResponseMetadata']['Error']['Message'])
            
            print(f"      [CORE_DEBUG] Step B finished. 文件上传成功。")
            return commit_img['Result']['Results'][0]['Uri']
            
        except Exception as err:
            print(f'      [CORE_ERROR] 上传文件失败: {err}')
            raise Exception(f'上传失败,失败原因: {str(err)}')

    # ===== 新增人脸识别相关方法 =====
    
    async def face_recognize(self, image_uri: str) -> dict:
        """
        人脸识别API - 获取人脸关键点数据
        
        Args:
            image_uri: 上传图片后返回的ImageUri
            
        Returns:
            dict: 人脸识别结果
        """
        print(f"      [CORE_DEBUG] 开始人脸识别: {image_uri}")
        
        face_params = {
            "aid": self.DEFAULT_ASSISTANT_ID,
            "web_version": "6.6.0", 
            "da_version": "3.2.8",
            "aigc_features": "app_lip_sync"
        }
        
        face_data = {
            "image_uri_list": [image_uri]
        }
        
        try:
            result = await self.request('POST', '/mweb/v1/face_recognize', face_data, face_params)
            print(f"      [CORE_DEBUG] 人脸识别结果: {result}")
            return result
        except Exception as e:
            print(f"      [CORE_ERROR] 人脸识别失败: {e}")
            raise e
    
    def format_face_recognize_list(self, face_result: dict, image_uri: str) -> List[List[dict]]:
        """
        格式化人脸识别结果为图生图所需的格式
        
        Args:
            face_result: 人脸识别API返回的结果
            image_uri: 图片URI
            
        Returns:
            List[List[dict]]: 格式化后的人脸数据列表
        """
        if not face_result or face_result.get('ret') != '0':
            return []
        
        data = face_result.get('data', {})
        face_recognize_list = data.get('face_recognize_list', [])
        
        if not face_recognize_list or not face_recognize_list[0]:
            return []
        
        # 格式化人脸数据
        formatted_faces = []
        for face in face_recognize_list[0]:
            formatted_face = {
                "type": "",
                "id": self.generate_uuid(),
                "keypoint": face.get('keypoint', []),
                "face_rect": face.get('face_rect', []),
                "is_selected": True
            }
            formatted_faces.append(formatted_face)
        
        return [formatted_faces] if formatted_faces else []
    
    def _build_ability_list(self, upload_id: str, reference_mode: str, face_recognize_data: List = None, sample_strength: float = 0.5) -> List[dict]:
        """
        构建图生图的ability_list
        
        Args:
            upload_id: 上传的图片URI
            reference_mode: 参考模式 ("byte_edit" 或 "face_gan")
            face_recognize_data: 人脸识别数据（仅face_gan模式需要）
            sample_strength: 生成强度
            
        Returns:
            List[dict]: ability_list配置
        """
        base_ability = {
            "type": "",
            "id": self.generate_uuid(),
            "name": reference_mode,
            "image_uri_list": [upload_id],
            "image_list": [{
                "type": "image",
                "id": self.generate_uuid(),
                "source_from": "upload",
                "platform_type": 1,
                "name": "",
                "image_uri": upload_id,
                "width": 0,
                "height": 0,
                "format": "",
                "uri": upload_id
            }]
        }
        
        if reference_mode == "byte_edit":
            # 智能参考模式
            base_ability["strength"] = sample_strength
        elif reference_mode == "face_gan":
            # 人像写真模式，需要添加人脸识别数据
            if face_recognize_data:
                base_ability["face_recognize_list"] = face_recognize_data
        
        return [base_ability]
    
    def _build_multi_ability_list(self, upload_ids: List[str], reference_mode: str, face_recognize_data: List = None, sample_strength: float = 0.5) -> List[dict]:
        """
        构建多图图生图的ability_list
        
        Args:
            upload_ids: 上传的图片URI列表
            reference_mode: 参考模式 ("byte_edit" 或 "face_gan")
            face_recognize_data: 人脸识别数据（仅face_gan模式需要，仅应用于第一张图）
            sample_strength: 生成强度
            
        Returns:
            List[dict]: ability_list配置（每张图一个条目）
        """
        ability_list = []
        
        for i, upload_id in enumerate(upload_ids):
            base_ability = {
                "type": "",
                "id": self.generate_uuid(),
                "name": reference_mode,
                "image_uri_list": [upload_id],
                "image_list": [{
                    "type": "image",
                    "id": self.generate_uuid(),
                    "source_from": "upload",
                    "platform_type": 1,
                    "name": "",
                    "image_uri": upload_id,
                    "width": 0,
                    "height": 0,
                    "format": "",
                    "uri": upload_id
                }]
            }
            
            if reference_mode == "byte_edit":
                # 智能参考模式：每张图都使用相同的强度
                base_ability["strength"] = sample_strength
            elif reference_mode == "face_gan":
                # 人像写真模式：仅第一张图使用人脸识别数据
                if i == 0 and face_recognize_data:
                    base_ability["face_recognize_list"] = face_recognize_data
                else:
                    # 其他图片降级为智能参考模式
                    base_ability["name"] = "byte_edit"
                    base_ability["strength"] = sample_strength
            
            ability_list.append(base_ability)
        
        print(f"      [CORE_DEBUG] 构造了 {len(ability_list)} 个 ability 条目")
        return ability_list
    
    def _build_placeholder_info_list(self, ability_count: int) -> List[dict]:
        """
        构建与ability_list匹配的prompt_placeholder_info_list
        
        Args:
            ability_count: ability_list的数量
            
        Returns:
            List[dict]: placeholder_info_list配置
        """
        placeholder_list = []
        for i in range(ability_count):
            placeholder_list.append({
                "type": "",
                "id": self.generate_uuid(),
                "ability_index": i
            })
        
        print(f"      [CORE_DEBUG] 构造了 {len(placeholder_list)} 个 placeholder 条目")
        return placeholder_list

    async def get_credit(self) -> Dict[str, int]:
        print("      [CORE_DEBUG] Step A: 获取积分信息 (get_credit)")
        result = await self.request('POST', '/commerce/v1/benefits/user_credit', {}, {}, {'Referer': 'https://jimeng.jianying.com/ai-tool/image/generate'})
        credit = result.get('credit', {})
        gift_credit = credit.get('gift_credit', 0)
        purchase_credit = credit.get('purchase_credit', 0)
        vip_credit = credit.get('vip_credit', 0)
        total = gift_credit + purchase_credit + vip_credit
        print(f"      [CORE_DEBUG] 积分获取成功: totalCredit={total}")
        return {'giftCredit': gift_credit, 'purchaseCredit': purchase_credit, 'vipCredit': vip_credit, 'totalCredit': total}
    
    async def receive_credit(self) -> None:
        """领取积分"""
        print("      [CORE_DEBUG] 尝试领取每日积分...")
        credit = await self.request(
            'POST',
            '/commerce/v1/benefits/credit_receive',
            {'time_zone': 'Asia/Shanghai'},
            {},
            {'Referer': 'https://jimeng.jianying.com/ai-tool/image/generate'}
        )
        print(f"      [CORE_DEBUG] 领取积分响应: {credit}")
    
    async def poll_result_with_history(self, result: Any) -> List[Any]:
        history_id = result.get('data', {}).get('aigc_data', {}).get('history_record_id')
        print(f"      [CORE_DEBUG] Step D: 开始轮询结果 (poll_result_with_history), history_id: {history_id}")
        if not history_id:
            if result.get('errmsg'):
                print(f"      [CORE_ERROR] 无法获取 history_id, 错误信息: {result['errmsg']}")
                raise Exception(result['errmsg'])
            else:
                print(f"      [CORE_ERROR] 无法获取 history_id, 原始响应: {result}")
                raise Exception('记录ID不存在')
        
        # 初始默认状态与轮询参数
        status = 20
        poll_count = 1
        max_polls = 200  # 兜底最多轮询200次
        max_duration_seconds = 30 * 60  # 或最多30分钟
        start_time = time.time()
        interval_seconds = 2  # 固定为2秒，不采用服务端建议的30秒间隔
        first_result_timestamp = None # 图片结果计时器
        
        # 定义持续状态：进行中/排队中等（42 视为成功进行中，直至 item_list 出现）
        ongoing_status_set = {20, 42}
        
        while True:
            # 超时保护
            if poll_count > max_polls or (time.time() - start_time) > max_duration_seconds:
                print("      [CORE_WARN] 轮询超时，达到最大尝试次数或最长时长。")
                break
            
            print(f"        [CORE_DEBUG] D-{poll_count}: 轮询中... (等待{interval_seconds}秒)")
            await asyncio.sleep(interval_seconds)
            
            poll_data = {
                "history_ids": [history_id], 
                "image_info": {
                    "width": 2048, 
                    "height": 2048, 
                    "format": "webp", 
                    "image_scene_list": [
                        {"scene": "smart_crop", "width": 360, "height": 360, "uniq_key": "smart_crop-w:360-h:360", "format": "webp"}, 
                        {"scene": "smart_crop", "width": 480, "height": 480, "uniq_key": "smart_crop-w:480-h:480", "format": "webp"}, 
                        {"scene": "smart_crop", "width": 720, "height": 720, "uniq_key": "smart_crop-w:720-h:720", "format": "webp"}, 
                        {"scene": "normal", "width": 2400, "height": 2400, "uniq_key": "2400", "format": "webp"}, 
                        {"scene": "normal", "width": 1080, "height": 1080, "uniq_key": "1080", "format": "webp"}, 
                        {"scene": "normal", "width": 720, "height": 720, "uniq_key": "720", "format": "webp"}
                    ]
                }, 
                "http_common_info": {"aid": int(self.DEFAULT_ASSISTANT_ID)}
            }
            result = await self.request('POST', '/mweb/v1/get_history_by_ids', poll_data)
            
            record = result.get('data', {}).get(history_id)
            if not record:
                print(f"      [CORE_ERROR] 轮询时记录消失, 原始响应: {result}")
                raise Exception('记录不存在')
            
            # 不再读取服务端建议的 interval_seconds，固定 2 秒快速轮询
            
            status = record.get('status')
            fail_code = record.get('fail_code')
            print(f"        [CORE_DEBUG] D-{poll_count}: 轮询状态 status={status}, fail_code={fail_code}")
            
            # 强制调试：完整打印本轮 record JSON（限制长度避免刷屏）
            # try:
            #     model_for_debug = getattr(self, '_debug_current_model_name', None)
            #     if model_for_debug == 'jimeng-4.0' or True:
            #         print("        [CORE_DEBUG] [RAW_RECORD]", json.dumps(record, ensure_ascii=False)[:4000])
            # except Exception:
            #     print("        [CORE_DEBUG] [RAW_RECORD] <unserializable>")
            
            # 失败状态处理
            if status == 30:
                if fail_code == '2038':
                    raise Exception('内容被过滤')
                raise Exception('生成失败')
            
            # 成功结果优先：根据类型判断返回
            if record.get('item_list') and len(record['item_list']) > 0:
                print(f"      [CORE_DEBUG] 检测到 item_list，当前长度: {len(record['item_list'])}")
                print(f"      [CORE_DEBUG] item_list 内容: {record['item_list']}")

                first_item = record['item_list'][0]
                # 通过检查第一个结果中是否包含 'video' 键来判断任务类型
                is_video_result = 'video' in first_item

                if is_video_result:
                    # 视频任务，获得1个结果即可结束
                    print("      [CORE_DEBUG] Step D finished. 轮询成功，获取到1个视频结果。")
                    return record['item_list']
                else:
                    # 图片任务
                    if first_result_timestamp is None:
                        print("      [CORE_DEBUG] 收到第一个图片结果，启动30秒倒计时...")
                        first_result_timestamp = time.time()

                    # 1. 优先判断是否已集齐4个结果
                    if len(record['item_list']) >= 4:
                        print("      [CORE_DEBUG] Step D finished. 轮询成功，获取到全部4个图片结果。")
                        return record['item_list']
                    
                    # 2. 如果结果没齐，再判断30秒计时器是否超时
                    if time.time() - first_result_timestamp > 30:
                        print("      [CORE_WARN] 等待4个图片结果超时（30秒）。返回当前已有的结果。")
                        return record['item_list']
                    
                    # 3. 如果既没集齐也没超时，继续等待
                    print(f"      [CORE_DEBUG] 当前只有 {len(record['item_list'])} 个图片结果，继续等待...")
                    # 继续轮询，不返回
            
            # 若仍在进行中（含status=42），继续轮询直到 item_list 出现
            if status in ongoing_status_set:
                poll_count += 1
                continue
            
            # 其他未知状态：继续少量尝试，等待 item_list（兼容4.0可能的中间态）
            poll_count += 1
            continue
        
        print("      [CORE_WARN] Step D finished. 轮询结束但未获取到 item_list。")
        return []

    async def generate_image(self, prompt: str, file_path: Union[str, List[str]] = None, model: str = None, model_index: Optional[int] = None,
                           width: int = 1024, height: int = 1024, sample_strength: float = 0.5,
                           negative_prompt: str = "", reference_mode: str = "byte_edit") -> Union[List[str], str]:
        """
        即梦AI图像生成 - 支持文生图和图生图（单图/多图）

        Args:
            prompt: 生成图像的提示词
            file_path: 参考图片路径，支持单图(str)或多图(List[str])（可选）
            model: 模型名称（可选）
            model_index: 模型序号（可选）
            width: 图像宽度（默认1024）
            height: 图像高度（默认1024）
            sample_strength: 生成强度0-1（默认0.5）
            negative_prompt: 负面提示词（可选）
            reference_mode: 参考模式，可选值：
                - "byte_edit": 智能参考模式（默认，支持多图）
                - "face_gan": 人像写真模式（仅支持单图，需要人脸图片）

        Returns:
            Union[List[str], str]: 生成的图像URL列表，或错误代码字符串
        """
        print("      [CORE_DEBUG] --- 调用 generate_image ---")
        print(f"      [CORE_DEBUG]   - prompt: {prompt}")
        print(f"      [CORE_DEBUG]   - file_path: {file_path}")
        print(f"      [CORE_DEBUG]   - model: {model}, model_index: {model_index}")
        print(f"      [CORE_DEBUG]   - reference_mode: {reference_mode}")

        if not prompt or not isinstance(prompt, str): raise Exception('prompt必须是非空字符串')
        
        credit_info = await self.get_credit()
        if credit_info.get('totalCredit', 0) <= 0:
            print("      [CORE_WARN] 积分不足，尝试自动领取...")
            try:
                await self.receive_credit()
                credit_info = await self.get_credit()
                if credit_info.get('totalCredit', 0) <= 0:
                    print("      [CORE_ERROR] 领取后积分仍然不足。")
            except Exception as e:
                print(f"      [CORE_ERROR] 自动领取积分失败: {e}")

        # 处理多图参数：标准化为列表
        file_paths = []
        if file_path:
            if isinstance(file_path, list):
                file_paths = file_path
                print(f"      [CORE_DEBUG]   - 多图模式: {len(file_paths)}张图片")
            else:
                file_paths = [file_path]
                print(f"      [CORE_DEBUG]   - 单图模式: 1张图片")
        
        has_file_path = bool(file_paths)
        upload_ids = []
        face_recognize_data = None
        
        if file_paths:
            # 上传所有图片
            for i, path in enumerate(file_paths):
                upload_id = await self.upload_cover_file(path)
                upload_ids.append(upload_id)
                print(f"      [CORE_DEBUG]   - 图片{i+1}上传完成: {upload_id}")
            
            # 多图模式下的特殊处理
            if len(file_paths) > 1:
                if reference_mode == "face_gan":
                    print("⚠️  多图模式下，人像写真模式仅使用第一张图片进行人脸识别")
                    # 仅对第一张图片进行人脸识别
                    first_upload_id = upload_ids[0]
                else:
                    print(f"✅ 多图智能参考模式: 使用{len(upload_ids)}张图片")
            
            # 如果是人像写真模式，需要获取人脸识别数据（仅处理第一张图）
            if reference_mode == "face_gan":
                target_upload_id = upload_ids[0]  # 使用第一张图片
                print("🔍 检测人脸模式，开始获取人脸识别数据...")
                try:
                    face_result = await self.face_recognize(target_upload_id)
                    face_recognize_data = self.format_face_recognize_list(face_result, target_upload_id)
                    
                    if not face_recognize_data or len(face_recognize_data) == 0 or len(face_recognize_data[0]) == 0:
                        print("❌ 未检测到人脸，人像写真模式需要包含清晰人脸的图片")
                        raise ValueError("USER_INPUT_ERROR:未检测到人脸，人像写真模式需要包含清晰人脸的图片，请更换图片或选择智能参考模式")
                    else:
                        print(f"✅ 检测到 {len(face_recognize_data[0])} 个人脸")
                except ValueError as e:
                    if "USER_INPUT_ERROR:" in str(e):
                        # 重新抛出用户输入错误
                        raise e
                    else:
                        print(f"❌ 人脸识别失败: {e}")
                        raise Exception(f"人脸识别失败: {e}，请检查图片质量或网络连接")
                except Exception as e:
                    print(f"❌ 人脸识别失败: {e}")
                    raise Exception(f"人脸识别失败: {e}，请检查图片质量或网络连接")
        
        model_name = self.DEFAULT_BLEND_MODEL if has_file_path else (model or self.DEFAULT_MODEL)
        
        if model_index is not None:
            image_models = [k for k in self.MODEL_MAP.keys() if 'video' not in k]
            if 0 <= model_index < len(image_models):
                model_name = image_models[model_index]
                print(f"      [CORE_DEBUG]   - Selected model by index {model_index}: {model_name}")
            else:
                raise ValueError(f"无效的图片模型序号。请从 0 到 {len(image_models)-1} 中选择。")

        actual_model = self.get_model(model_name)
        
        # 根据模型确定分辨率类型
        resolution_type = '2k' if model_name in ['jimeng-4.0', 'jimeng-4.5'] else '1k'
        print(f"      [CORE_DEBUG]   - Resolution type set to: {resolution_type} for model {model_name}")

        component_id = self.generate_uuid()
        
        if has_file_path:
            # 构建图生图的ability_list（支持多图）
            ability_list = self._build_multi_ability_list(upload_ids, reference_mode, face_recognize_data, sample_strength)
            
            abilities = {
                "blend": {
                    "type": "", 
                    "id": self.generate_uuid(), 
                    "min_features": [], 
                    "core_param": {
                        "type": "", 
                        "id": self.generate_uuid(), 
                        "model": actual_model, 
                        "prompt": prompt + '##', 
                        "sample_strength": sample_strength, 
                        "image_ratio": 1, 
                        "large_image_info": {
                            "type": "", 
                            "id": self.generate_uuid(), 
                            "height": height, 
                            "width": width, 
                            "resolution_type": resolution_type
                        }
                    }, 
                    "ability_list": ability_list, 
                    "history_option": {"type": "", "id": self.generate_uuid()}, 
                    "prompt_placeholder_info_list": self._build_placeholder_info_list(len(ability_list)), 
                    "postedit_param": {"type": "", "id": self.generate_uuid(), "generate_type": 0}
                }
            }
        else:
            abilities = {
                "generate": {
                    "type": "",
                    "id": self.generate_uuid(),
                    "core_param": {
                        "type": "",
                        "id": self.generate_uuid(),
                        "model": actual_model,
                        "prompt": prompt,
                        "negative_prompt": negative_prompt,
                        "seed": random.randint(2500000000, 2600000000),
                        "sample_strength": sample_strength,
                        "image_ratio": 1,
                        "large_image_info": {
                            "type": "",
                            "id": self.generate_uuid(),
                            "height": height,
                            "width": width,
                            "resolution_type": resolution_type,
                            "intelligent_ratio": False
                        }
                    },
                    "gen_option": {
                        "type": "",
                        "id": self.generate_uuid(),
                        "generate_all": False
                    }
                }
            }

        submit_id = self.generate_uuid()
        
        rq_data = {
            "extend": {"root_model": actual_model},
            "submit_id": submit_id,
            "metrics_extra": None if has_file_path else json.dumps({
                "promptSource": "custom",
                "generateCount": 1,
                "enterFrom": "click",
                "generateId": submit_id,
                "isRegenerate": False
            }, separators=(',', ':')),
            "draft_content": json.dumps({
                "type": "draft",
                "id": self.generate_uuid(),
                "min_version": self.DRAFT_VERSION,
                "min_features": [],
                "is_from_tsn": True,
                "version": "3.3.3",
                "main_component_id": component_id,
                "component_list": [{
                    "type": "image_base_component",
                    "id": component_id,
                    "min_version": self.DRAFT_VERSION,
                    "metadata": {
                        "type": "",
                        "id": self.generate_uuid(),
                        "created_platform": 3,
                        "created_platform_version": "",
                        "created_time_in_ms": str(int(time.time() * 1000)),
                        "created_did": ""
                    },
                    "generate_type": "blend" if has_file_path else "generate",
                    "aigc_mode": "workbench",
                    "abilities": {"type": "", "id": self.generate_uuid(), **abilities}
                }]
            }, separators=(',', ':')),
            "http_common_info": {
                "aid": int(self.DEFAULT_ASSISTANT_ID)
            }
        }
        
        rq_params = {
            "aid": int(self.DEFAULT_ASSISTANT_ID),
            "device_platform": "web",
            "region": "cn",
            "webId": self.WEB_ID,
            "da_version": "3.3.3",
            "web_component_open_flag": "1",
            "web_version": "7.5.0",
            "aigc_features": "app_lip_sync",
            "msToken": self.generate_ms_token()
        }

        print("      [CORE_DEBUG] Step C: 发送生成请求 (generate)")
        print("------ FULL REQUEST DATA (generate_image) ------")
        try:
            print(json.dumps(rq_data, indent=2, ensure_ascii=False))
        except Exception:
            pprint(rq_data)
        print("--------------------------------------------------")
        result = await self.request('POST', '/mweb/v1/aigc_draft/generate', rq_data, rq_params)
        
        # 强制调试：打印 /generate 原始响应（仅用于定位4.0问题）
        # try:
        #     print("      [CORE_DEBUG] [RAW_GENERATE_RESPONSE]", json.dumps(result, ensure_ascii=False)[:2000])
        # except Exception:
        #     print("      [CORE_DEBUG] [RAW_GENERATE_RESPONSE] <unserializable>")
        
        # 记录本次调用的模型名称，便于轮询阶段定向调试
        # try:
        #     self._debug_current_model_name = model_name
        # except Exception:
        #     pass
        
        ret_code = result.get('ret')
        print(f"      [CORE_DEBUG] Step C finished. 收到生成请求响应, ret_code: {ret_code}")
        
        if str(ret_code) in ['5000', '1015']:
            print(f"      [CORE_WARN] 检测到特殊返回码 {ret_code}, 将其返回给上层处理。")
            return str(ret_code) # 返回字符串以便fastapi捕获
        elif str(ret_code) == '0':
            item_list = await self.poll_result_with_history(result)
            print(f"      [CORE_DEBUG] poll_result_with_history 返回的 item_list 长度: {len(item_list) if item_list else 0}")
            result_list = []
            for i, item in enumerate(item_list or []):
                print(f"      [CORE_DEBUG] 处理第 {i+1} 个 item: {item}")
                image_url = None
                # 优先获取无水印的 cover_url
                if item.get('common_attr', {}).get('cover_url'):
                    image_url = item['common_attr']['cover_url']
                    print(f"      [CORE_DEBUG] 从 cover_url (无水印) 获取到 URL: {image_url}")
                elif item.get('image', {}).get('large_images') and len(item['image']['large_images']) > 0:
                    image_url = item['image']['large_images'][0].get('image_url')
                    print(f"      [CORE_DEBUG] 从 large_images 获取到 URL: {image_url}")
                
                if image_url: 
                    result_list.append(image_url)
                    print(f"      [CORE_DEBUG] 添加到结果列表，当前长度: {len(result_list)}")
            print(f"      [CORE_DEBUG] --- generate_image 调用结束, 返回 {len(result_list)} 个结果 ---")
            return result_list
        else:
            print(f"      [CORE_ERROR] 未知的 ret_code: {ret_code}. 响应: {result}")
            raise Exception(f"生成失败，未知返回码: {ret_code} - {result.get('errmsg', 'No error message')}")

    async def generate_video(self, prompt: Union[str, List[str]], file_path: Union[str, List[str]] = None, model: str = None, model_index: Optional[int] = None,
                           resolution: str = "720p", width: int = 1024, height: int = 1024, video_aspect_ratio: Optional[str] = None,
                           video_gen_mode: str = 'default', frame_durations_ms: Optional[List[int]] = None) -> Union[str, None]:
        # [DEBUG] Ensure resolution has a value and log it
        resolution = resolution or "720p"
        
        print("      [CORE_DEBUG] --- 调用 generate_video ---")
        print(f"      [CORE_DEBUG]   - prompt: {prompt}")
        print(f"      [CORE_DEBUG]   - file_path: {file_path}")
        print(f"      [CORE_DEBUG]   - model: {model}, model_index: {model_index}")
        print(f"      [CORE_DEBUG]   - video_aspect_ratio: {video_aspect_ratio}")
        print(f"      [CORE_DEBUG]   - resolution (received): {resolution}")

        # [FIX] 尝试解析 JSON 格式的字符串列表，防止将 JSON 字符串当作单个文件路径处理
        if file_path and isinstance(file_path, str) and file_path.strip().startswith('['):
            try:
                parsed = json.loads(file_path)
                if isinstance(parsed, list):
                    file_path = parsed
                    print(f"      [CORE_DEBUG]   - Successfully parsed JSON file_path to list: {file_path}")
            except Exception as e:
                print(f"      [CORE_DEBUG]   - Failed to parse file_path as JSON (will treat as string): {e}")

        # [FIX] 统一 file_path 格式为列表，防止传入字符串被按字符遍历导致 'h' 文件错误
        if file_path and isinstance(file_path, str):
            file_path = [file_path]
            print(f"      [CORE_DEBUG]   - Normalized file_path to list: {file_path}")

        if not prompt:
            raise Exception('prompt不能为空')
        
        model_name = model or self.DEFAULT_VIDEO_MODEL
        if model_index is not None:
            video_models = [k for k in self.MODEL_MAP.keys() if 'video' in k]
            if 0 <= model_index < len(video_models):
                model_name = video_models[model_index]
                print(f"      [CORE_DEBUG]   - Selected model by index {model_index}: {model_name}")
            else:
                raise ValueError(f"无效的视频模型序号。请从 0 到 {len(video_models)-1} 中选择。")

        actual_model = self.get_model(model_name)
        
        credit_info = await self.get_credit()
        if credit_info.get('totalCredit', 0) <= 0:
            print("      [CORE_WARN] 积分不足，尝试自动领取...")
            try:
                await self.receive_credit()
                credit_info = await self.get_credit()
                if credit_info.get('totalCredit', 0) <= 0:
                    print("      [CORE_ERROR] 领取后积分仍然不足。")
            except Exception as e:
                print(f"      [CORE_ERROR] 自动领取积分失败: {e}")

        first_frame_image = None
        end_frame_image = None
        
        if file_path:
            upload_ids = []
            for i, item in enumerate(file_path):
                if i > 0: # 从第二个文件开始，每次上传前延时
                    print("      [CORE_DEBUG] 延时1秒，避免上传过快...")
                    await asyncio.sleep(1)
                upload_id = await self.upload_cover_file(item)
                upload_ids.append(upload_id)
            
            if upload_ids and upload_ids[0]:
                first_frame_image = {
                    "format": "", 
                    "height": height, 
                    "id": self.generate_uuid(), 
                    "image_uri": upload_ids[0], 
                    "name": "", 
                    "platform_type": 1, 
                    "source_from": "upload", 
                    "type": "image", 
                    "uri": upload_ids[0], 
                    "width": width
                }
            
            if len(upload_ids) > 1 and upload_ids[1]:
                end_frame_image = {
                    "format": "", 
                    "height": height, 
                    "id": self.generate_uuid(), 
                    "image_uri": upload_ids[1], 
                    "name": "", 
                    "platform_type": 1, 
                    "source_from": "upload", 
                    "type": "image", 
                    "uri": upload_ids[1], 
                    "width": width
                }
            
            if not first_frame_image and not end_frame_image:
                raise Exception('上传封面图片失败，请检查图片路径是否正确')
        
        component_id = self.generate_uuid()
        
        # 根据 video_gen_mode 动态构建请求
        function_mode = None
        if video_gen_mode == 'first_last_frames':
            function_mode = 'first_last_frames'
        elif video_gen_mode == 'multi_frame':
            function_mode = 'multi_frame'

        metrics_data = {
            "enterFrom": "click",
            "isDefaultSeed": 1,
            "promptSource": "custom",
            "isRegenerate": False,
            "originSubmitId": self.generate_uuid()
        }
        if function_mode:
            metrics_data["functionMode"] = function_mode
        
        metrics_extra = json.dumps(metrics_data, separators=(',', ':'))

        video_gen_inputs = []
        min_features = []
        draft_min_version = "3.0.5"

        if video_gen_mode == 'multi_frame':
            min_features.append("AIGC_GenerateType_VideoMultiFrame")
            if not isinstance(prompt, list) or not file_path or len(prompt) != len(file_path):
                raise ValueError("在 'multi_frame' 模式下, 'prompt' 必须是与 'file_path' 等长的列表。")

            # 校验帧时长列表
            if frame_durations_ms and len(frame_durations_ms) != len(prompt):
                raise ValueError("`frame_durations_ms` 列表的长度必须与 `prompt` 列表的长度相同。")

            multi_frames = []
            total_duration_ms = 0
            # upload_ids should be available from the file upload logic above
            for i, (p, up_id) in enumerate(zip(prompt, upload_ids)):
                # 确定当前帧的持续时间
                current_frame_duration = frame_durations_ms[i] if frame_durations_ms else 2000
                total_duration_ms += current_frame_duration

                multi_frames.append({
                    "type": "", "id": self.generate_uuid(), "idx": i,
                    "duration_ms": current_frame_duration,  # 使用指定或默认的持续时间
                    "prompt": p,
                    "media_info": {
                        "type": "", "id": self.generate_uuid(), "media_type": 1,
                        "image_info": {
                            "type": "image", "id": self.generate_uuid(), "source_from": "upload",
                            "platform_type": 1, "name": "", "image_uri": up_id,
                            "width": width, "height": height, "format": "", "uri": up_id
                        }
                    }
                })

            video_gen_inputs.append({
                "type": "", "id": self.generate_uuid(), "min_version": "3.0.5",
                "prompt": "",  # 多帧模式下顶层prompt为空
                "video_mode": 2, "fps": 24, "duration_ms": total_duration_ms, "resolution": resolution, # 使用计算出的总时长
                "multi_frames": multi_frames,
                "idip_meta_list": []
            })
        else:  # 'default' 和 'first_last_frames' 模式
            if not isinstance(prompt, str):
                raise ValueError("在 'default' 或 'first_last_frames' 模式下, 'prompt' 必须是字符串。")
            
            video_gen_input = {
                "duration_ms": 5000, "first_frame_image": first_frame_image,
                "end_frame_image": end_frame_image, "fps": 24, "id": self.generate_uuid(),
                "min_version": "3.0.5", "prompt": prompt, "resolution": resolution,
                "type": "", "video_mode": 2
            }
            if video_gen_mode == 'first_last_frames':
                video_gen_input["ending_control"] = "1.0"
            
            video_gen_inputs.append(video_gen_input)

        rq_params = {
            "msToken": self.generate_ms_token(), "aigc_features": "app_lip_sync",
            "web_version": "6.6.0", "da_version": "3.2.8", "aid": int(self.DEFAULT_ASSISTANT_ID),
            "device_platform": "web", "region": "CN", "web_id": self.WEB_ID
        }
        
        rq_data = {
            "extend": {
                "root_model": self.MODEL_MAP['jimeng-video-3.0'] if end_frame_image or video_gen_mode == 'multi_frame' else actual_model,
                "m_video_commerce_info": {"benefit_type": "basic_video_operation_vgfm_v_three", "resource_id": "generate_video", "resource_id_type": "str", "resource_sub_type": "aigc"},
                "m_video_commerce_info_list": [{"benefit_type": "basic_video_operation_vgfm_v_three", "resource_id": "generate_video", "resource_id_type": "str", "resource_sub_type": "aigc"}]
            },
            "submit_id": self.generate_uuid(),
            "metrics_extra": metrics_extra,
            "draft_content": json.dumps({
                "type": "draft", "id": self.generate_uuid(), "min_version": draft_min_version,
                "min_features": min_features, "is_from_tsn": True, "version": "3.3.3",
                "main_component_id": component_id,
                "component_list": [{
                    "type": "video_base_component", "id": component_id, "min_version": "1.0.0",
                    "metadata": {
                        "type": "", "id": self.generate_uuid(), "created_platform": 3,
                        "created_platform_version": "", "created_time_in_ms": int(time.time() * 1000),
                        "created_did": ""
                    },
                    "generate_type": "gen_video", "aigc_mode": "workbench",
                    "abilities": {
                        "type": "", "id": self.generate_uuid(),
                        "gen_video": {
                            "id": self.generate_uuid(), "type": "",
                            "text_to_video_params": {
                                "type": "", "id": self.generate_uuid(), "model_req_key": actual_model,
                                "priority": 0, "seed": random.randint(2500000000, 2600000000),
                                "video_aspect_ratio": (video_aspect_ratio or "1:1"),
                                "video_gen_inputs": video_gen_inputs
                            },
                            "video_task_extra": metrics_extra,
                        }
                    }
                }],
            }, separators=(',', ':'))
        }
        
        print("      [CORE_DEBUG] Step C: 发送视频生成请求 (generate)")
        print(f"      [CORE_DEBUG] Video Gen Inputs payload: {json.dumps(video_gen_inputs, ensure_ascii=False)}") # DEBUG LOG ADDED HERE
        print("------ FULL REQUEST DATA (generate_video) ------")
        try:
            print(json.dumps(rq_data, indent=2, ensure_ascii=False))
        except Exception:
            pprint(rq_data)
        print("--------------------------------------------------")
        result = await self.request('POST', '/mweb/v1/aigc_draft/generate', rq_data, rq_params)
        
        ret_code = result.get('ret')
        print(f"      [CORE_DEBUG] Step C finished. 收到生成请求响应, ret_code: {ret_code}")

        if str(ret_code) in ['5000', '1015']:
            print(f"      [CORE_WARN] 检测到特殊返回码 {ret_code}, 将其返回给上层处理。")
            return str(ret_code)
        elif str(ret_code) == '0':
            item_list = await self.poll_result_with_history(result)
            video_url = None
            if item_list and len(item_list) > 0:
                video_url = item_list[0].get('video', {}).get('transcoded_video', {}).get('origin', {}).get('video_url')
            print(f"      [CORE_DEBUG] --- generate_video 调用结束, 返回结果 ---")
            return video_url
        else:
            print(f"      [CORE_ERROR] 未知的 ret_code: {ret_code}. 响应: {result}")
            raise Exception(f"生成失败，未知返回码: {ret_code} - {result.get('errmsg', 'No error message')}")
