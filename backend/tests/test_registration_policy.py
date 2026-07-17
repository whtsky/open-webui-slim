from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / 'backend'

ENDPOINT_SCENARIO = r"""
import os
import time

from fastapi.testclient import TestClient
from sqlalchemy import text

from open_webui.internal.db import SessionLocal
from open_webui.main import app
from open_webui.models.config import Config


scenario = os.environ['REGISTRATION_POLICY_SCENARIO']

if scenario == 'initial-admin-with-stale-config':
    with SessionLocal() as db:
        db.merge(Config(key='ui.enable_signup', value=True, updated_at=int(time.time())))
        db.commit()

signup_request = {
    'name': 'Bootstrap Admin',
    'email': 'admin@example.test',
    'password': 'S3cure-Registration-Test!123',
}

with TestClient(app) as client:
    for removed_api_path in (
        '/api/v1/audio/config',
        '/api/v1/calendars',
        '/api/v1/automations',
        '/api/v1/scim/v2/Users',
    ):
        removed_api_response = client.get(removed_api_path)
        assert removed_api_response.status_code == 404, removed_api_response.text

    # Browser-side routes still need the SPA fallback so SvelteKit can render
    # its own not-found page for removed product routes.
    assert client.get('/calendar').status_code == 200

    initial_config_response = client.get('/api/config')
    assert initial_config_response.status_code == 200, initial_config_response.text
    initial_config = initial_config_response.json()
    assert initial_config['features']['enable_signup'] is False

    first_signup = client.post('/api/v1/auths/signup', json=signup_request)

    if scenario == 'default-closed':
        assert initial_config.get('onboarding', False) is False
        assert first_signup.status_code == 403, first_signup.text
    else:
        assert initial_config['onboarding'] is True
        assert first_signup.status_code == 200, first_signup.text
        assert first_signup.json()['role'] == 'admin'

        admin_config_response = client.get('/api/v1/auths/admin/config')
        assert admin_config_response.status_code == 200, admin_config_response.text
        assert 'ENABLE_SIGNUP' not in admin_config_response.json()

        config_export_response = client.get('/api/v1/configs/export')
        assert config_export_response.status_code == 200, config_export_response.text
        exported_config = config_export_response.json()
        assert 'ui.enable_signup' not in exported_config
        assert 'auth.initial_admin_signup_claimed' not in exported_config
        assert not any(
            key.startswith(('audio.', 'automations.', 'calendar.', 'scim.', 'task.voice.'))
            for key in exported_config
        )

        second_signup = client.post(
            '/api/v1/auths/signup',
            json={
                **signup_request,
                'name': 'Second User',
                'email': 'second@example.test',
            },
        )
        assert second_signup.status_code == 403, second_signup.text

        # The one-time claim is durable: deleting the first account does not
        # turn the public endpoint back into a bootstrap path.
        with SessionLocal() as db:
            db.execute(text('DELETE FROM auth'))
            db.execute(text('DELETE FROM user'))
            db.commit()

        # Resetting mutable application configuration must not erase the
        # one-time security claim and turn bootstrap signup back on.
        client.portal.call(Config.clear)
        assert client.portal.call(Config.internal_exists, 'auth.initial_admin_signup_claimed')

        client.cookies.clear()
        final_config_response = client.get('/api/config')
        assert final_config_response.status_code == 200, final_config_response.text
        final_config = final_config_response.json()
        assert final_config['features']['enable_signup'] is False
        assert final_config.get('onboarding', False) is False

        signup_after_user_deletion = client.post(
            '/api/v1/auths/signup',
            json={**signup_request, 'email': 'replacement@example.test'},
        )
        assert signup_after_user_deletion.status_code == 403, signup_after_user_deletion.text
"""


def _run_endpoint_scenario(tmp_path: Path, scenario: str, *, initial_admin_signup: bool) -> None:
    data_dir = tmp_path / scenario
    static_dir = data_dir / 'static'
    frontend_dir = data_dir / 'frontend'
    static_dir.mkdir(parents=True)
    frontend_dir.mkdir()
    (frontend_dir / 'index.html').write_text('<!doctype html><title>SPA fallback</title>')

    env = os.environ.copy()
    env.update(
        {
            'DATA_DIR': str(data_dir),
            'DATABASE_URL': f'sqlite:///{data_dir / "webui.db"}',
            'STATIC_DIR': str(static_dir),
            'FRONTEND_BUILD_DIR': str(frontend_dir),
            'WEBUI_SECRET_KEY': 'registration-policy-test-secret-key',
            'WEBUI_AUTH': 'true',
            'ENABLE_DB_MIGRATIONS': 'true',
            'ENABLE_VERSION_UPDATE_CHECK': 'false',
            'DO_NOT_TRACK': 'true',
            'SCARF_NO_ANALYTICS': 'true',
            'OFFLINE_MODE': 'true',
            'HF_HUB_OFFLINE': '1',
            'REGISTRATION_POLICY_SCENARIO': scenario,
            'PYTHONPATH': os.pathsep.join(
                [str(BACKEND_DIR), *(part for part in env.get('PYTHONPATH', '').split(os.pathsep) if part)]
            ),
        }
    )
    env.pop('WEBUI_ADMIN_EMAIL', None)
    env.pop('WEBUI_ADMIN_PASSWORD', None)
    env.pop('ENABLE_SIGNUP', None)
    env.pop('ENABLE_INITIAL_ADMIN_SIGNUP', None)

    if initial_admin_signup:
        env['ENABLE_INITIAL_ADMIN_SIGNUP'] = 'true'
        # Both legacy inputs are deliberately present in this scenario. Neither
        # may reopen public password registration after bootstrap completes.
        env['ENABLE_SIGNUP'] = 'true'

    result = subprocess.run(
        [sys.executable, '-c', ENDPOINT_SCENARIO],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )

    assert result.returncode == 0, (
        f'registration scenario {scenario!r} failed\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}'
    )


@pytest.mark.parametrize(
    ('scenario', 'initial_admin_signup'),
    [
        ('default-closed', False),
        ('initial-admin-with-stale-config', True),
    ],
)
def test_registration_endpoint_policy(tmp_path: Path, scenario: str, initial_admin_signup: bool) -> None:
    _run_endpoint_scenario(tmp_path, scenario, initial_admin_signup=initial_admin_signup)


def test_frontend_has_no_public_signup_controls() -> None:
    auth_page = (PROJECT_ROOT / 'src/routes/auth/+page.svelte').read_text()
    admin_auth_settings = (PROJECT_ROOT / 'src/lib/components/admin/Settings/Authentication.svelte').read_text()

    assert "Don't have an account?" not in auth_page
    assert '$config?.features.enable_signup &&' not in auth_page
    assert "mode === 'signin' ? $i18n.t('Sign up')" not in auth_page
    assert 'Enable New Sign Ups' not in admin_auth_settings
    assert 'ENABLE_SIGNUP' not in admin_auth_settings
