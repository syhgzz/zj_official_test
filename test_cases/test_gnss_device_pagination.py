# -*- coding: utf-8 -*-
import io
import json
import math
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from test_cases import test_gnss_device


class StationPageClient:
    """用可控分页响应替代外部接口。"""

    TOTAL = 3651

    def request(self, method, path, params=None, data=None):
        if method != 'GET' or path != '/api/v1/gnss-device/stations':
            raise AssertionError(f'意外请求: {method} {path}')

        page_num = params['pageNum']
        page_size = params['pageSize']
        total_pages = math.ceil(self.TOTAL / page_size)
        if page_size != 100 or page_num not in range(1, total_pages + 1):
            raise AssertionError(f'分页参数错误: pageNum={page_num}, pageSize={page_size}')

        start = (page_num - 1) * page_size + 1
        end = min(page_num * page_size, self.TOTAL)
        stations = [
            {
                'stationCode': f'S{index:04d}',
                'stationName': f'站点{index}',
                'longitude': 100.0,
                'latitude': 30.0,
                'alt': 10.0,
                'satelliteCount': {'bdCount': 1},
                'signalQuality': {'qualified': True, 'avgNoiseRatio': 30.0},
                'delay': 0,
                'status': 'online',
                'lastUpdateTime': 0,
            }
            for index in range(start, end + 1)
        ]
        return {
            'code': 200,
            'msg': 'success',
            'data': {
                'total': self.TOTAL,
                'pageNum': page_num,
                'pageSize': page_size,
                'stations': stations,
                'regionCode': '',
                'regionName': '',
            },
            'timestamp': 0,
        }


class TransientTimeoutClient(StationPageClient):
    def __init__(self):
        self.page_27_timed_out = False

    def request(self, method, path, params=None, data=None):
        if params['pageNum'] == 27 and not self.page_27_timed_out:
            self.page_27_timed_out = True
            return {'code': None, 'timeout': True, 'msg': '请求超时(超过10s)'}
        return super().request(method, path, params=params, data=data)


class TransientNoneClient(StationPageClient):
    """模拟 APIClient 遇到 requests 超时时返回 None。"""

    def __init__(self):
        self.page_3_timed_out = False

    def request(self, method, path, params=None, data=None):
        if params['pageNum'] == 3 and not self.page_3_timed_out:
            self.page_3_timed_out = True
            return None
        return super().request(method, path, params=params, data=data)


class PermanentFailureClient(StationPageClient):
    def request(self, method, path, params=None, data=None):
        if params['pageNum'] == 3:
            return None
        return super().request(method, path, params=params, data=data)


class DuplicateStationClient(StationPageClient):
    def request(self, method, path, params=None, data=None):
        response = super().request(method, path, params=params, data=data)
        if params['pageNum'] == 2:
            response['data']['stations'][0]['stationCode'] = 'S0001'
        return response


class TestGnssStationPagination(unittest.TestCase):
    def test_uses_response_total_to_fetch_all_pages_and_prints_total_elapsed_time(self):
        with tempfile.TemporaryDirectory() as response_dir:
            test_config = SimpleNamespace(
                verbose=False,
                save_response=True,
                response_dir=response_dir,
            )

            with patch.object(test_gnss_device, 'config', test_config):
                output = io.StringIO()
                with redirect_stdout(output):
                    response = test_gnss_device.test_get_stations(
                        StationPageClient(),
                        page_num=1,
                        page_size=100,
                    )

            saved_payloads = [
                json.loads(path.read_text(encoding='utf-8'))
                for path in Path(response_dir).glob('*.json')
            ]
            page_payloads = [
                payload for payload in saved_payloads
                if isinstance(payload['request_params'].get('pageNum'), int)
            ]
            merged_payloads = [
                payload for payload in saved_payloads
                if payload['request_params'].get('pageNum') == '1-37'
            ]

            self.assertEqual(38, len(saved_payloads))
            self.assertEqual(list(range(1, 38)), sorted(
                payload['request_params']['pageNum'] for payload in page_payloads
            ))
            self.assertEqual(1, len(merged_payloads))
            self.assertEqual(37, response['data']['fetchedPageCount'])
            self.assertEqual(3651, len(response['data']['stations']))
            self.assertEqual(3651, len(merged_payloads[0]['response']['data']['stations']))
            self.assertEqual(3651, len(test_gnss_device.station_codes))
            self.assertEqual('S0001', test_gnss_device.station_codes[0])
            self.assertEqual('S3651', test_gnss_device.station_codes[-1])
            self.assertRegex(
                output.getvalue(),
                re.compile(r'获取所有记录站点列表总时间: \d+\.\d{3} 秒'),
            )

    def test_retries_a_page_once_after_a_timeout(self):
        test_config = SimpleNamespace(
            verbose=False,
            save_response=False,
            response_dir='unused',
        )

        with patch.object(test_gnss_device, 'config', test_config):
            with redirect_stdout(io.StringIO()):
                try:
                    response = test_gnss_device.test_get_stations(
                        TransientTimeoutClient(),
                        page_num=1,
                        page_size=100,
                    )
                except RuntimeError as exc:
                    self.fail(f'偶发超时后没有重试成功: {exc}')

        self.assertEqual(3651, len(response['data']['stations']))
        self.assertEqual(3651, len(test_gnss_device.station_codes))

    def test_retries_when_api_client_returns_none_after_a_timeout(self):
        test_config = SimpleNamespace(
            verbose=False,
            save_response=False,
            response_dir='unused',
        )

        with patch.object(test_gnss_device, 'config', test_config):
            with redirect_stdout(io.StringIO()):
                response = test_gnss_device.test_get_stations(
                    TransientNoneClient(),
                    page_num=1,
                    page_size=100,
                )

        self.assertEqual(3651, len(response['data']['stations']))

    def test_prints_total_elapsed_time_before_reporting_permanent_failed_pages(self):
        test_config = SimpleNamespace(
            verbose=False,
            save_response=False,
            response_dir='unused',
        )
        output = io.StringIO()

        with patch.object(test_gnss_device, 'config', test_config):
            with redirect_stdout(output):
                with self.assertRaisesRegex(RuntimeError, r'站点列表请求失败页码: \[3\]'):
                    test_gnss_device.test_get_stations(
                        PermanentFailureClient(),
                        page_num=1,
                        page_size=100,
                    )

        self.assertRegex(
            output.getvalue(),
            re.compile(r'获取所有记录站点列表总时间: \d+\.\d{3} 秒'),
        )

    def test_reports_duplicate_rows_and_deduplicates_station_codes(self):
        test_config = SimpleNamespace(
            verbose=False,
            save_response=False,
            response_dir='unused',
        )

        with patch.object(test_gnss_device, 'config', test_config):
            with redirect_stdout(io.StringIO()):
                response = test_gnss_device.test_get_stations(
                    DuplicateStationClient(),
                    page_num=1,
                    page_size=100,
                )

        self.assertEqual(3651, len(response['data']['stations']))
        self.assertEqual(3650, response['data'].get('uniqueStationCount'))
        self.assertEqual(1, response['data'].get('duplicateStationCodeCount'))
        self.assertEqual(3650, len(test_gnss_device.station_codes))


if __name__ == '__main__':
    unittest.main()
