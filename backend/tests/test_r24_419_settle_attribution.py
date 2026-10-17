"""R24 #265: settle_generation no longer writes 'multiple' (it entered the success-rate denominator:
llm_auth_invalid + authentication became a product failure). Primary via failure_attribution."""
from backend.services.studio import store


def _data(*codes):
    return {'output_variants': [{'status': 'failed', 'error_code': c, 'render_job_id': f'j{i}'} for i, c in enumerate(codes)],
            'jobs': [], 'generation': {}, 'analysis': {'run_id': 'r'}}


def test_265_two_user_causes_stay_a_user_cause():
    d = _data('llm_auth_invalid', 'authentication')
    store.settle_generation(d)
    assert d['generation']['error_code'] == 'llm_auth_invalid' and d['analysis']['error_code'] == 'llm_auth_invalid', d
    assert d['generation']['secondary_error_codes'] == ['authentication']


def test_265_product_cause_wins_whatever_the_order():
    for codes in (('authentication', 'timeout'), ('timeout', 'authentication')):
        d = _data(*codes)
        store.settle_generation(d)
        assert d['generation']['error_code'] == 'timeout' and d['analysis']['error_code'] == 'timeout', d
        assert d['analysis']['secondary_error_codes'] == ['authentication']
