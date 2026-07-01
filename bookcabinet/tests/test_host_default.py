"""
Тест дефолта HOST (issue #108).

Без env HOST API должен слушать только loopback (127.0.0.1), а не 0.0.0.0.
Наружное прослушивание задаётся явно через env HOST (systemd/prod).
"""
import importlib
import os
import unittest
from unittest.mock import patch


class TestHostDefault(unittest.TestCase):
    def test_default_host_is_loopback(self):
        env = {k: v for k, v in os.environ.items() if k != 'HOST'}
        with patch.dict(os.environ, env, clear=True):
            import bookcabinet.config as cfg
            cfg = importlib.reload(cfg)
            self.assertEqual(cfg.HOST, '127.0.0.1')

    def test_env_override_respected(self):
        with patch.dict(os.environ, {'HOST': '0.0.0.0'}, clear=False):
            import bookcabinet.config as cfg
            cfg = importlib.reload(cfg)
            self.assertEqual(cfg.HOST, '0.0.0.0')

    @classmethod
    def tearDownClass(cls):
        # Вернуть модуль к состоянию текущего окружения, чтобы не влиять
        # на другие тесты в той же сессии.
        import bookcabinet.config as cfg
        importlib.reload(cfg)


if __name__ == '__main__':
    unittest.main()
