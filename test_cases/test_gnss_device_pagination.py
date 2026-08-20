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


class FakeStationsClient:
    """用可配置的异常场景替代外部接口，避免为每个场景建子类。"""

    def __init__(
        self,
        total,
        timeout_pages=(),
        none_pages=(),
        fail_pages=(),
        duplicate_page=None,
    ):
        self.total = total
        self.timeout_pages = set(timeout_pages)
        self.none_pages = set(none_pages)
        self.fail_pages = set(fail_pages)
        self.duplicate_page = duplicate_page
        self._timeout_done = set()
        self._none_done = set()

    def request(self, method, path, params=None, data=None):
        if method != 'GET' or path != '/api/v1/gnss-device/stations':
            raise AssertionError(f'意外请求: {method} {path}')

        page_num = params['pageNum']
        page_size = params['pageSize']
        if page_size != 100:
            raise AssertionError(f'分页参数错误: pageSize={page_size}')

        if page_num in self.timeout_pages and page_num not in self._timeout_done:
            self._timeout_done.add(page_num)
            return {'code': None, 'timeout': True, 'msg': '请求超时(超过10s)'}
        if page_num in self.none_pages and page_num not in self._none_done:
            self._none_done.add(page_num)
            return None
        if page_num in self.fail_pages:
            return None

        response = self._build_page(page_num, page_size)
        if page_num == self.duplicate_page:
            response['data']['stations'][0]['stationCode'] = 'S0001'
        return response

    def _build_page(self, page_num, page_size):
        total_pages = math.ceil(self.total / page_size)
        if page_num not in range(1, total_pages + 1):
            raise AssertionError(f'分页参数错误: pageNum={page_num}, pageSize={page_size}')

        start = (page_num - 1) * page_size + 1
        end = min(page_num * page_size, self.total)
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
                'total': self.total,
                'pageNum': page_num,
                'pageSize': page_size,
                'stations': stations,
                'regionCode': '',
                'regionName': '',
            },
            'timestamp': 0,
        }


class TestGnssStationPagination(unittest.TestCase):
    def test_uses_response_total_to_fetch_all_pages_and_prints_total_elapsed_time(self):
        with tempfile.TemporaryDirectory() as response_dir:
            client = FakeStationsClient(total=3651)
            expected_total = client.total
            expected_page_count = math.ceil(expected_total / 100)
            test_config = SimpleNamespace(
                verbose=False,
                save_response=True,
                response_dir=response_dir,
            )

            with patch.object(test_gnss_device, 'config', test_config):
                output = io.StringIO()
                with redirect_stdout(output):
                    response = test_gnss_device.test_get_stations(
                        client,
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
                if payload['request_params'].get('pageNum') == f'1-{expected_page_count}'
            ]

            self.assertEqual(expected_page_count + 1, len(saved_payloads))
            self.assertEqual(list(range(1, expected_page_count + 1)), sorted(
                payload['request_params']['pageNum'] for payload in page_payloads
            ))
            self.assertEqual(1, len(merged_payloads))
            self.assertEqual(expected_page_count, response['data']['fetchedPageCount'])
            self.assertEqual(expected_total, len(response['data']['stations']))
            self.assertEqual(expected_total, len(merged_payloads[0]['response']['data']['stations']))
            self.assertEqual(expected_total, len(test_gnss_device.station_codes))
            self.assertEqual('S0001', test_gnss_device.station_codes[0])
            self.assertEqual(f'S{expected_total:04d}', test_gnss_device.station_codes[-1])
            self.assertRegex(
                output.getvalue(),
                re.compile(r'获取所有记录站点列表总时间: \d+\.\d{3} 秒'),
            )

    def test_fetches_all_pages_after_backend_total_increases(self):
        client = FakeStationsClient(total=3720)
        expected_total = client.total
        expected_page_count = math.ceil(expected_total / 100)
        test_config = SimpleNamespace(
            verbose=False,
            save_response=False,
            response_dir='unused',
        )

        with patch.object(test_gnss_device, 'config', test_config):
            with redirect_stdout(io.StringIO()):
                response = test_gnss_device.test_get_stations(
                    client,
                    page_num=1,
                    page_size=100,
                )

        self.assertEqual(expected_page_count, response['data']['fetchedPageCount'])
        self.assertEqual(expected_total, len(response['data']['stations']))
        self.assertEqual(expected_total, len(test_gnss_device.station_codes))
        self.assertEqual(f'S{expected_total:04d}', test_gnss_device.station_codes[-1])

    def test_nationwide_config_is_temporary(self):
        original = (
            test_gnss_device.startTime_file,
            test_gnss_device.endTime_file,
            test_gnss_device.minLng_file,
            test_gnss_device.maxLng_file,
            test_gnss_device.minLat_file,
            test_gnss_device.maxLat_file,
        )
        try:
            with test_gnss_device._nationwide_config():
                self.assertEqual(test_gnss_device.minLng_file, 83.353)
                self.assertEqual(test_gnss_device.maxLng_file, 126.196)
                self.assertEqual(test_gnss_device.minLat_file, 21.928)
                self.assertEqual(test_gnss_device.maxLat_file, 47.096)
                self.assertEqual(
                    test_gnss_device.startTime_file,
                    test_gnss_device._NATIONWIDE_START_TIME,
                )
                self.assertEqual(
                    test_gnss_device.endTime_file,
                    test_gnss_device._NATIONWIDE_END_TIME,
                )
        finally:
            self.assertEqual(
                (
                    test_gnss_device.startTime_file,
                    test_gnss_device.endTime_file,
                    test_gnss_device.minLng_file,
                    test_gnss_device.maxLng_file,
                    test_gnss_device.minLat_file,
                    test_gnss_device.maxLat_file,
                ),
                original,
            )

    def test_retries_a_page_once_after_a_timeout(self):
        client = FakeStationsClient(total=3651, timeout_pages={27})
        expected_total = client.total
        test_config = SimpleNamespace(
            verbose=False,
            save_response=False,
            response_dir='unused',
        )

        with patch.object(test_gnss_device, 'config', test_config):
            with redirect_stdout(io.StringIO()):
                try:
                    response = test_gnss_device.test_get_stations(
                        client,
                        page_num=1,
                        page_size=100,
                    )
                except RuntimeError as exc:
                    self.fail(f'偶发超时后没有重试成功: {exc}')

        self.assertEqual(expected_total, len(response['data']['stations']))
        self.assertEqual(expected_total, len(test_gnss_device.station_codes))

    def test_retries_when_api_client_returns_none_after_a_timeout(self):
        client = FakeStationsClient(total=3651, none_pages={3})
        expected_total = client.total
        test_config = SimpleNamespace(
            verbose=False,
            save_response=False,
            response_dir='unused',
        )

        with patch.object(test_gnss_device, 'config', test_config):
            with redirect_stdout(io.StringIO()):
                response = test_gnss_device.test_get_stations(
                    client,
                    page_num=1,
                    page_size=100,
                )

        self.assertEqual(expected_total, len(response['data']['stations']))

    def test_prints_total_elapsed_time_before_reporting_permanent_failed_pages(self):
        client = FakeStationsClient(total=3651, fail_pages={3})
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
                        client,
                        page_num=1,
                        page_size=100,
                    )

        self.assertRegex(
            output.getvalue(),
            re.compile(r'获取所有记录站点列表总时间: \d+\.\d{3} 秒'),
        )

    def test_reports_duplicate_rows_and_deduplicates_station_codes(self):
        client = FakeStationsClient(total=3651, duplicate_page=2)
        expected_total = client.total
        test_config = SimpleNamespace(
            verbose=False,
            save_response=False,
            response_dir='unused',
        )

        with patch.object(test_gnss_device, 'config', test_config):
            with redirect_stdout(io.StringIO()):
                response = test_gnss_device.test_get_stations(
                    client,
                    page_num=1,
                    page_size=100,
                )

        self.assertEqual(expected_total, len(response['data']['stations']))
        self.assertEqual(3650, response['data'].get('uniqueStationCount'))
        self.assertEqual(1, response['data'].get('duplicateStationCodeCount'))
        self.assertEqual(3650, len(test_gnss_device.station_codes))


if __name__ == '__main__':
    unittest.main()
