from django.conf import settings
from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User


class SessionTimeoutTest(TestCase):
    def test_session_cookie_age_configurado(self):
        self.assertEqual(settings.SESSION_COOKIE_AGE, 28800)

    def test_session_expire_at_browser_close(self):
        self.assertTrue(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)

    def test_session_save_every_request(self):
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)

    def test_session_cookie_httponly(self):
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)

    def test_session_cookie_samesite(self):
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, 'Lax')


class DebugModeTest(TestCase):
    def test_debug_mode_desligado(self):
        self.assertFalse(settings.DEBUG)


class AllowedHostsTest(TestCase):
    def test_allowed_hosts_sem_wildcard(self):
        for host in settings.ALLOWED_HOSTS:
            self.assertNotIn('0.0.0.0', host)

    def test_allowed_hosts_strip_whitespace(self):
        for host in settings.ALLOWED_HOSTS:
            self.assertEqual(host, host.strip())


class NinjaJwtRemovedTest(TestCase):
    def test_ninja_jwt_removido(self):
        self.assertFalse(hasattr(settings, 'NINJA_JWT'))


class CSRFConfigTest(TestCase):
    def test_csrf_cookie_httponly(self):
        self.assertFalse(settings.CSRF_COOKIE_HTTPONLY)

    def test_csrf_cookie_samesite(self):
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, 'Lax')


class LoginFunctionalTest(TestCase):
    def setUp(self):
        self.client = Client()
        User.objects.create_user(username='testuser', password='testpass123')

    def test_login_funciona_com_credenciais_validas(self):
        resp = self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'testpass123'
        }, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['user']['username'], 'testuser')

    def test_login_recusa_credenciais_invalidas(self):
        resp = self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'wrongpass'
        }, content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data['success'])
        self.assertIn('Credenciais inválidas', data['error'])

    def test_logout_funciona(self):
        self.client.login(username='testuser', password='testpass123')
        resp = self.client.post('/api/auth/logout/', content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])

    def test_me_sem_autenticacao(self):
        resp = self.client.get('/api/auth/me/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertFalse(data['success'])

    def test_me_com_autenticacao(self):
        self.client.login(username='testuser', password='testpass123')
        resp = self.client.get('/api/auth/me/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['user']['username'], 'testuser')


class LoginRateLimitSecurityTest(TestCase):
    _cache_name = 'test_rate_limit_cache'

    def setUp(self):
        self.client = Client()
        User.objects.create_user(username='testuser', password='testpass123')

    def _cache_settings(self):
        return {
            'default': {
                'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                'LOCATION': f'test-rate-limit-{self._testMethodName}',
            }
        }

    @override_settings(RATELIMIT_ENABLE=True)
    def test_rate_limit_bloqueia_apos_exceder_limite(self):
        with self.settings(CACHES=self._cache_settings()):
            for i in range(10):
                resp = self.client.post('/api/auth/login/', {
                    'username': 'testuser',
                    'password': 'wrongpass'
                }, content_type='application/json')
                self.assertNotIn(resp.status_code, (403, 429), f'Tentativa {i+1} foi bloqueada prematuramente')

            resp = self.client.post('/api/auth/login/', {
                'username': 'testuser',
                'password': 'wrongpass'
            }, content_type='application/json')
            self.assertIn(resp.status_code, (403, 429))

    @override_settings(RATELIMIT_ENABLE=True)
    def test_rate_limit_nao_bloqueia_login_valido(self):
        with self.settings(CACHES=self._cache_settings()):
            resp = self.client.post('/api/auth/login/', {
                'username': 'testuser',
                'password': 'testpass123'
            }, content_type='application/json')
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertTrue(data['success'])
