"""Offline tests for Institution pre-response transport substages."""

from __future__ import annotations

import os
import re
import socket
import ssl
import time
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch, sentinel
from urllib.request import HTTPSHandler, ProxyHandler, Request

os.environ.setdefault("MARKET_PULSE_DISABLE_BACKGROUND", "1")
os.environ.setdefault("MARKET_PULSE_LOG_LEVEL", "CRITICAL")

import app
import security


TAIFEX_URL = "https://openapi.taifex.com.tw/v1/InstitutionTest"
OTHER_URL = "https://example.com/v1/InstitutionTest"


class InstitutionPreResponseSubstageObservabilityTests(unittest.TestCase):
    @contextmanager
    def _active_institution_context(self):
        with app.app.test_request_context("/api/institution?product=TX"):
            app.institution_observability_start("TX")
            app.institution_observability_set_deadline(time.monotonic() + 60.0)
            yield

    @staticmethod
    def _event_lines(records) -> list[str]:
        return [line for line in records.output if "event=institution.provider." in line]

    @classmethod
    def _event_names(cls, records) -> list[str]:
        return [re.search(r"event=([^ ]+)", line).group(1) for line in cls._event_lines(records)]

    @staticmethod
    def _connection() -> security._InstitutionObservabilityHTTPSConnection:
        return security._InstitutionObservabilityHTTPSConnection(
            "openapi.taifex.com.tw",
            timeout=2.0,
            context=ssl.create_default_context(),
        )

    def test_prs_01_request_isolation(self) -> None:
        with patch.object(socket, "create_connection") as create_connection, \
                patch.object(app.LOGGER, "info") as info:
            connection = self._connection()
            self.assertIs(connection._create_connection, create_connection)
            connection.send = MagicMock(return_value=sentinel.result)
        self.assertFalse(any("event=institution.provider." in str(call) for call in info.call_args_list))

    def test_prs_02_wrong_host_isolation(self) -> None:
        request = Request(OTHER_URL)
        with self._active_institution_context():
            handler = security._InstitutionObservabilityHTTPSHandler(context=ssl.create_default_context())
            with patch.object(HTTPSHandler, "https_open", return_value=sentinel.response) as parent_open, \
                    patch.object(handler, "do_open") as do_open:
                result = handler.https_open(request)
        self.assertIs(result, sentinel.response)
        parent_open.assert_called_once_with(request)
        do_open.assert_not_called()

    def test_prs_03_dns_tcp_success_preserves_socket(self) -> None:
        mock_socket = sentinel.socket
        with self._active_institution_context(), \
                patch.object(socket, "create_connection", return_value=mock_socket), \
                self.assertLogs("market_pulse", level="INFO") as records:
            connection = self._connection()
            result = connection._create_connection("openapi.taifex.com.tw", 443, timeout=2.0)
        self.assertIs(result, mock_socket)
        self.assertEqual(self._event_names(records), [
            "institution.provider.dns_tcp.begin",
            "institution.provider.dns_tcp.end",
        ])

    def test_prs_04_dns_tcp_exception_preserves_same_exception(self) -> None:
        error = OSError("offline")
        with self._active_institution_context(), \
                patch.object(socket, "create_connection", side_effect=error), \
                self.assertLogs("market_pulse", level="INFO") as records:
            connection = self._connection()
            with self.assertRaises(OSError) as raised:
                connection._create_connection("openapi.taifex.com.tw", 443, timeout=2.0)
        self.assertIs(raised.exception, error)
        self.assertEqual(self._event_names(records), [
            "institution.provider.dns_tcp.begin",
            "institution.provider.dns_tcp.exception",
        ])
        self.assertIn("exception_class=OSError", " ".join(self._event_lines(records)))

    def test_prs_05_proxy_tunnel_success(self) -> None:
        with self._active_institution_context(), \
                patch.object(security.http.client.HTTPSConnection, "_tunnel", return_value=sentinel.tunnel) as parent_tunnel, \
                self.assertLogs("market_pulse", level="INFO") as records:
            connection = self._connection()
            connection._tunnel_host = "proxy.example"
            result = connection._tunnel()
        self.assertIs(result, sentinel.tunnel)
        parent_tunnel.assert_called_once_with()
        self.assertEqual(self._event_names(records), [
            "institution.provider.proxy_tunnel.begin",
            "institution.provider.proxy_tunnel.end",
        ])
        self.assertIn("proxy_active=true", " ".join(self._event_lines(records)))

    def test_prs_06_no_proxy_emits_no_tunnel_events(self) -> None:
        with self._active_institution_context(), \
                patch.object(security.http.client.HTTPSConnection, "_tunnel", return_value=sentinel.tunnel) as parent_tunnel, \
                patch.object(app.LOGGER, "info") as info:
            connection = self._connection()
            connection._tunnel_host = None
            result = connection._tunnel()
        self.assertIs(result, sentinel.tunnel)
        parent_tunnel.assert_called_once_with()
        self.assertFalse(any("institution.provider.proxy_tunnel" in str(call) for call in info.call_args_list))

    def test_prs_07_https_connect_success(self) -> None:
        with self._active_institution_context(), \
                patch.object(ssl.SSLContext, "wrap_socket", return_value=sentinel.socket), \
                patch.object(security.http.client.HTTPSConnection, "connect", return_value=sentinel.connected), \
                self.assertLogs("market_pulse", level="INFO") as records:
            connection = self._connection()
            result = connection.connect()
        self.assertIs(result, sentinel.connected)
        self.assertEqual(self._event_names(records), [
            "institution.provider.https_connect.begin",
            "institution.provider.https_connect.end",
        ])

    def test_prs_08_inferred_tls_boundary_fixture(self) -> None:
        events = [
            "institution.provider.dns_tcp.end",
            "institution.provider.https_connect.begin",
        ]
        self.assertEqual(
            security._classify_institution_pre_response_events(events),
            "TLS_HANDSHAKE_PATH",
        )

    def test_prs_09_request_send_success_preserves_return(self) -> None:
        with self._active_institution_context(), \
                patch.object(security.http.client.HTTPSConnection, "send", return_value=sentinel.sent), \
                self.assertLogs("market_pulse", level="INFO") as records:
            connection = self._connection()
            result = connection.send(b"request bytes")
        self.assertIs(result, sentinel.sent)
        self.assertEqual(self._event_names(records), [
            "institution.provider.request_send.begin",
            "institution.provider.request_send.end",
        ])
        self.assertIn("send_seq=1", " ".join(self._event_lines(records)))

    def test_prs_10_repeated_send_has_monotonic_sequence(self) -> None:
        with self._active_institution_context(), \
                patch.object(security.http.client.HTTPSConnection, "send", return_value=None), \
                self.assertLogs("market_pulse", level="INFO") as records:
            connection = self._connection()
            connection.send(b"first")
            connection.send(b"second")
        lines = self._event_lines(records)
        self.assertEqual(re.findall(r"send_seq=(\d+)", " ".join(lines)), ["1", "1", "2", "2"])

    def test_prs_11_response_headers_success_preserves_response(self) -> None:
        with self._active_institution_context(), \
                patch.object(security.http.client.HTTPSConnection, "getresponse", return_value=sentinel.response), \
                self.assertLogs("market_pulse", level="INFO") as records:
            connection = self._connection()
            result = connection.getresponse()
        self.assertIs(result, sentinel.response)
        self.assertEqual(self._event_names(records), [
            "institution.provider.response_headers.begin",
            "institution.provider.response_headers.end",
        ])

    def test_prs_12_response_headers_exception_preserves_class(self) -> None:
        error = TimeoutError("offline")
        with self._active_institution_context(), \
                patch.object(security.http.client.HTTPSConnection, "getresponse", side_effect=error), \
                self.assertLogs("market_pulse", level="INFO") as records:
            connection = self._connection()
            with self.assertRaises(TimeoutError) as raised:
                connection.getresponse()
        self.assertIs(raised.exception, error)
        self.assertEqual(self._event_names(records), [
            "institution.provider.response_headers.begin",
            "institution.provider.response_headers.exception",
        ])

    def test_prs_13_opener_parity_and_arguments(self) -> None:
        context = ssl.create_default_context()
        request = Request(TAIFEX_URL)
        request.timeout = 7.5
        with self._active_institution_context(), \
                patch("urllib.request.getproxies", return_value={"https": "http://proxy.example"}):
            handler = security._InstitutionObservabilityHTTPSHandler(context=context)
            opener = security.build_opener(handler)
            handler_types = {type(item) for item in opener.handlers}
            self.assertIn(ProxyHandler, handler_types)
            self.assertIn(security._InstitutionObservabilityHTTPSHandler, handler_types)
            with patch.object(handler, "do_open", return_value=sentinel.response) as do_open:
                result = handler.https_open(request)
        self.assertIs(result, sentinel.response)
        http_class, received_request = do_open.call_args.args[:2]
        self.assertIs(http_class, security._InstitutionObservabilityHTTPSConnection)
        self.assertIs(received_request, request)
        self.assertIs(do_open.call_args.kwargs["context"], context)
        self.assertEqual(request.timeout, 7.5)

    def test_prs_13_target_path_selects_observed_verified_open(self) -> None:
        context = ssl.create_default_context()
        request = Request(TAIFEX_URL)
        with self._active_institution_context(), \
                patch.object(security, "_get_verified_ssl_context", return_value=context), \
                patch.object(security, "_urlopen_with_institution_observability", return_value=sentinel.response) as observed_open:
            result = security._urlopen_with_ssl_fallback(request, 7)
        self.assertIs(result, sentinel.response)
        observed_open.assert_called_once_with(request, 7, context)

    def test_prs_14_non_institution_urlopen_path_remains_original(self) -> None:
        request = Request(OTHER_URL)
        with patch.object(security, "urlopen", return_value=sentinel.response) as original_urlopen, \
                patch.object(security, "_urlopen_with_institution_observability") as observed_open:
            result = security._urlopen_with_ssl_fallback(request, 3)
        self.assertIs(result, sentinel.response)
        original_urlopen.assert_called_once()
        observed_open.assert_not_called()

    def test_prs_15_ssl_fallback_policy_stays_blocked_in_production(self) -> None:
        request = Request(TAIFEX_URL)
        certificate_error = ssl.SSLCertVerificationError("certificate verify failed")
        with patch.object(security, "_get_verified_ssl_context", side_effect=certificate_error), \
                patch.dict(os.environ, {"ALLOW_UNVERIFIED_SSL_FALLBACK": "1", "RENDER": "1"}, clear=False), \
                patch.object(security, "urlopen") as original_urlopen:
            with self.assertRaises(ssl.SSLCertVerificationError):
                security._urlopen_with_ssl_fallback(request, 3)
        original_urlopen.assert_not_called()

    def test_prs_16_observability_failure_does_not_mask_provider_result(self) -> None:
        with self._active_institution_context(), \
                patch.object(app, "institution_observability_log", side_effect=RuntimeError("logging failed")), \
                patch.object(security.http.client.HTTPSConnection, "getresponse", return_value=sentinel.response):
            connection = self._connection()
            self.assertIs(connection.getresponse(), sentinel.response)

    def test_prs_17_provider_host_and_request_id_are_reused(self) -> None:
        with self._active_institution_context(), \
                patch.object(socket, "create_connection", return_value=sentinel.socket), \
                self.assertLogs("market_pulse", level="INFO") as records:
            connection = self._connection()
            connection._create_connection("openapi.taifex.com.tw", 443)
        lines = self._event_lines(records)
        self.assertTrue(lines)
        request_ids = {re.search(r"institution_request_id=([^ ]+)", line).group(1) for line in lines}
        self.assertEqual(len(request_ids), 1)
        self.assertTrue(all("provider_host=openapi.taifex.com.tw" in line for line in lines))

    def test_prs_18_ssl_context_existing_emits_enter_return_only(self) -> None:
        existing_context = sentinel.existing_context
        with self._active_institution_context(), \
                patch.object(security, "_verified_ssl_context", existing_context), \
                self.assertLogs("market_pulse", level="INFO") as records:
            result = security._get_verified_ssl_context()
        self.assertIs(result, existing_context)
        self.assertEqual(self._event_names(records), [
            "institution.provider.ssl_context.enter",
            "institution.provider.ssl_context.return",
        ])

    def test_prs_19_ssl_context_initialization_emits_full_lifecycle(self) -> None:
        created_context = sentinel.created_context
        with self._active_institution_context(), \
                patch.object(security, "_verified_ssl_context", None), \
                patch.object(security.certifi, "where", return_value="offline-ca.pem") as where, \
                patch.object(security.ssl, "create_default_context", return_value=created_context) as create, \
                self.assertLogs("market_pulse", level="INFO") as records:
            result = security._get_verified_ssl_context()
        self.assertIs(result, created_context)
        where.assert_called_once_with()
        create.assert_called_once_with(cafile="offline-ca.pem")
        self.assertEqual(self._event_names(records), [
            "institution.provider.ssl_context.enter",
            "institution.provider.ssl_context.lock_acquired",
            "institution.provider.ssl_context.create.begin",
            "institution.provider.ssl_context.create.end",
            "institution.provider.ssl_context.return",
        ])

    def test_prs_20_ssl_context_inactive_emits_no_lifecycle_events(self) -> None:
        existing_context = sentinel.existing_context
        with patch.object(security, "_verified_ssl_context", existing_context), \
                patch.object(app.LOGGER, "info") as info:
            result = security._get_verified_ssl_context()
        self.assertIs(result, existing_context)
        self.assertFalse(any("institution.provider.ssl_context" in str(call) for call in info.call_args_list))

    def test_prs_21_ssl_context_create_exception_preserves_exception(self) -> None:
        error = RuntimeError("offline context failure")
        with self._active_institution_context(), \
                patch.object(security, "_verified_ssl_context", None), \
                patch.object(security.ssl, "create_default_context", side_effect=error), \
                self.assertLogs("market_pulse", level="INFO") as records:
            with self.assertRaises(RuntimeError) as raised:
                security._get_verified_ssl_context()
        self.assertIs(raised.exception, error)
        self.assertEqual(self._event_names(records), [
            "institution.provider.ssl_context.enter",
            "institution.provider.ssl_context.lock_acquired",
            "institution.provider.ssl_context.create.begin",
        ])


if __name__ == "__main__":
    unittest.main()
