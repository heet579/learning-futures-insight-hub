"""The browser app's API: upload → themes → draft → claims → submit → admin approval → export."""
from pathlib import Path

import pytest
from clear_answers import CLEAR_OK

pytest.importorskip('fastapi')
from test_server import api, database_url, sign_in  # noqa: F401  (shared fixtures)

from src.config import DATA_DIR
from src.storage.snapshot import unpack

SAMPLE = Path(DATA_DIR) / 'synthetic_qualtrics_evaluation.csv'


@pytest.fixture
def people(api, monkeypatch):
    monkeypatch.delenv('GEMINI_API_KEY', raising=False)     # drafts use local wording in tests
    admin = sign_in(api, 'lisa', 'admin-pass')
    api.post('/users', headers=admin, json={'username': 'gopi', 'password': 'gopi-pass'})
    api.post('/users', headers=admin, json={'username': 'esrat', 'password': 'esrat-pass'})
    return admin, sign_in(api, 'gopi', 'gopi-pass'), sign_in(api, 'esrat', 'esrat-pass')


def upload(api, headers, title='Leadership course'):
    with SAMPLE.open('rb') as handle:
        return api.post('/api/reports', headers=headers, data={'title': title},
                        files=[('files', (SAMPLE.name, handle, 'text/csv'))])


def test_browser_workflow_end_to_end(api, people):
    admin, gopi, esrat = people
    created = upload(api, gopi)
    assert created.status_code == 200, created.text
    body = created.json()
    rid, ws = body['report']['id'], body['workspace']
    assert body['report']['title'] == 'Leadership course' and ws['can_edit'] and not ws['can_review']
    assert ws['metrics']['responses'] > 0 and ws['themes'] and ws['content'] == ''
    assert 'Create the draft.' in ws['blockers']

    # Masked survey rows with search.
    rows = api.get(f'/api/reports/{rid}/rows', headers=gopi).json()
    assert rows['total'] == ws['metrics']['responses'] and rows['rows']
    assert 'ResponseID' in rows['columns']

    # Another member cannot see or change it.
    assert api.get(f'/api/reports/{rid}', headers=esrat).status_code == 400
    assert api.post(f'/api/reports/{rid}/draft', headers=esrat, json={'audience': 'facilitator'}).status_code == 400

    # Drafting is blocked until every theme is decided.
    assert 'Review every theme' in api.post(f'/api/reports/{rid}/draft', headers=gopi,
                                            json={'audience': 'facilitator'}).json()['detail']
    for i, theme in enumerate(ws['themes']):
        decision = {'name': theme['name'], 'status': 'rejected' if i == len(ws['themes']) - 1 else 'confirmed'}
        ws = api.post(f'/api/reports/{rid}/themes', headers=gopi, json=decision).json()['workspace']
    assert ws['themes_progress']['reviewed'] == ws['themes_progress']['total']

    drafted = api.post(f'/api/reports/{rid}/draft', headers=gopi, json={'audience': 'facilitator'}).json()
    ws = drafted['workspace']
    assert 'local wording' in drafted['result'] and ws['content'].startswith('# Facilitator Evaluation Report')
    # CLEAR step C: facts that match the data are checked automatically; nothing is left for a person here.
    assert ws['claims'] and all(c['decision'] in ('auto', 'pending') for c in ws['claims'])
    assert ws['clear']['check']['auto_verified'] > 20 and ws['clear']['check']['passed']
    assert ws['clear']['level']['level'] == 'standard' and len(ws['clear']['level']['questions']) == 3

    # Offline revision: preview, apply, undo.
    proposed = api.post(f'/api/reports/{rid}/revisions', headers=gopi,
                        json={'sections': ['Executive Summary'], 'instruction': 'shorten', 'method': 'offline'})
    assert proposed.status_code == 200, proposed.text
    assert proposed.json()['workspace']['revision']['changes'][0]['section'] == 'Executive Summary'
    applied = api.post(f'/api/reports/{rid}/revisions/apply', headers=gopi).json()['workspace']
    assert applied['revision'] is None and applied['can_undo_revision']
    ws = api.post(f'/api/reports/{rid}/revisions/undo', headers=gopi).json()['workspace']

    # Decide every claim: reject blocking ones (removes the text), accept the rest.
    for _ in range(200):
        pending = [c for c in ws['claims'] if c['decision'] == 'pending']
        if not pending:
            break
        item = pending[0]
        decision = 'reject' if item['blocking'] else 'accept'
        response = api.post(f'/api/reports/{rid}/claims/{item["key"]}', headers=gopi, json={'decision': decision})
        assert response.status_code == 200, response.text
        ws = response.json()['workspace']
    assert ws['blockers'] == [], ws['blockers']

    version = api.get(f'/api/reports/{rid}', headers=gopi).json()['report']['version']
    submitted = api.post(f'/reports/{rid}/transition', headers=gopi, json={'version': version, 'action': 'submit'})
    assert submitted.status_code == 200, submitted.text
    locked = api.get(f'/api/reports/{rid}', headers=gopi).json()['workspace']
    assert not locked['can_edit'] and locked['workflow']['status'] == 'AWAITING HUMAN REVIEW'
    assert api.put(f'/api/reports/{rid}/content', headers=gopi, json={'content': 'x'}).status_code == 400

    # The admin reviews and approves; a draft export is still available to the author meanwhile.
    review = api.get(f'/api/reports/{rid}', headers=admin).json()
    assert review['workspace']['can_review'] and review['workspace']['summary']['claims']['total'] > 0
    approved = api.post(f'/reports/{rid}/transition', headers=admin,
                        json={'version': review['report']['version'], 'action': 'approve',
                              'role': 'Program coordinator', 'confirmed': True, 'clear': CLEAR_OK})
    assert approved.status_code == 200, approved.text
    export = api.get(f'/api/reports/{rid}/export?format=docx', headers=gopi)
    assert export.status_code == 200 and export.content[:2] == b'PK'
    assert 'reviewed.docx' in export.headers['content-disposition']
    markdown = api.get(f'/api/reports/{rid}/export?format=md', headers=admin).text
    assert 'HUMAN REVIEWED' in markdown and '## Review record' in markdown

    # Saved in the same format the desktop app opens.
    state = unpack(api.services.reports.load(rid, 'gopi')['snapshot'])
    assert state['workflow'].status == 'HUMAN REVIEWED' and state['approved_export']


def test_upload_rejects_wrong_files(api, people):
    _, gopi, _ = people
    bad = api.post('/api/reports', headers=gopi, files=[('files', ('notes.txt', b'hello', 'text/plain'))])
    assert bad.status_code == 400 and 'CSV, XLSX or XLS' in bad.json()['detail']
    assert api.post('/api/reports', headers={}, files=[('files', ('a.csv', b'x', 'text/csv'))]).status_code == 401


def test_browser_app_is_served(api):
    page = api.get('/')
    assert page.status_code == 200 and 'Insight Hub' in page.text
    assert api.get('/api/config').json()['approver_roles']
    script = api.get('/app.js').text
    assert '/review/draft' in script and "Save failed" in script and 'setTimeout' in script


def submit_ready_report(api, headers):
    rid = upload(api, headers).json()['report']['id']
    ws = api.get(f'/api/reports/{rid}', headers=headers).json()['workspace']
    for theme in ws['themes']:
        api.post(f'/api/reports/{rid}/themes', headers=headers, json={'name': theme['name'], 'status': 'confirmed'})
    ws = api.post(f'/api/reports/{rid}/draft', headers=headers, json={'audience': 'facilitator'}).json()['workspace']
    for _ in range(200):
        pending = [c for c in ws['claims'] if c['decision'] == 'pending']
        if not pending:
            break
        decision = 'reject' if pending[0]['blocking'] else 'accept'
        ws = api.post(f'/api/reports/{rid}/claims/{pending[0]["key"]}', headers=headers, json={'decision': decision}).json()['workspace']
    return rid


def test_clear_review_drafts_restore_isolate_and_clear_after_submission(api, people, monkeypatch):
    admin, gopi, _ = people
    api.post('/users', headers=admin, json={'username': 'heet', 'password': 'heet-pass', 'role': 'admin'})
    heet = sign_in(api, 'heet', 'heet-pass')

    rid = submit_ready_report(api, gopi)
    version = api.get(f'/api/reports/{rid}', headers=gopi).json()['report']['version']
    assert api.post(f'/reports/{rid}/transition', headers=gopi,
                    json={'version': version, 'action': 'submit', 'reviewer': 'lisa'}).status_code == 200
    review = api.get(f'/api/reports/{rid}', headers=admin).json()
    report_version = review['report']['version']
    draft = {'faithful': 'partly', 'faithful_note': 'Include the quieter learners.',
             'owned': 'Compare the online and in-person groups next term.'}
    saved = api.put(f'/api/reports/{rid}/review/draft', headers=admin, json={'answers': draft})
    assert saved.status_code == 200 and saved.json() == {'saved': True}

    # A fresh session for the same account restores the same report/version draft.
    signed_in_again = sign_in(api, 'lisa', 'admin-pass')
    restored = api.get(f'/api/reports/{rid}', headers=signed_in_again).json()['workspace']['clear']['draft']
    assert restored == draft

    # Neither another account nor another report can see this draft.
    other_user = api.get(f'/api/reports/{rid}', headers=heet).json()['workspace']
    assert not other_user['can_review'] and 'draft' not in other_user['clear']
    assert api.put(f'/api/reports/{rid}/review/draft', headers=heet,
                   json={'answers': {'owned': 'not mine'}}).status_code == 403
    other_rid = submit_ready_report(api, gopi)
    other_version = api.get(f'/api/reports/{other_rid}', headers=gopi).json()['report']['version']
    api.post(f'/reports/{other_rid}/transition', headers=gopi,
             json={'version': other_version, 'action': 'submit', 'reviewer': 'lisa'})
    assert api.get(f'/api/reports/{other_rid}', headers=admin).json()['workspace']['clear']['draft'] == {}

    # A failed write reports failure and leaves the last successfully saved value intact.
    save = api.services.reports.save_clear_draft
    monkeypatch.setattr(api.services.reports, 'save_clear_draft',
                        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError('draft storage unavailable')))
    failed = api.put(f'/api/reports/{rid}/review/draft', headers=admin,
                     json={'answers': {'owned': 'must not replace the saved draft'}})
    assert failed.status_code == 400 and failed.json()['detail'] == 'draft storage unavailable'
    monkeypatch.setattr(api.services.reports, 'save_clear_draft', save)
    assert api.get(f'/api/reports/{rid}', headers=admin).json()['workspace']['clear']['draft'] == draft

    # Formal submission is still the existing workflow operation and removes the separate draft.
    approved = api.post(f'/reports/{rid}/transition', headers=admin, json={
        'version': report_version, 'action': 'approve', 'role': 'Program coordinator',
        'confirmed': True, 'clear': CLEAR_OK})
    assert approved.status_code == 200, approved.text
    assert api.services.reports.load_clear_draft(rid, 'lisa', report_version) == {}
    final_clear = api.get(f'/api/reports/{rid}', headers=admin).json()['workspace']['clear']
    assert 'draft' not in final_clear and final_clear['answers']['owned'] == CLEAR_OK['owned']


def test_author_chooses_the_reviewer_and_names_are_shown(api, people):
    admin, gopi, _ = people
    api.patch('/auth/me', headers=gopi, json={'display_name': 'Gopi Ravula'})
    api.post('/users', headers=admin, json={'username': 'heet', 'password': 'heet-pass', 'role': 'admin',
                                            'display_name': 'Heet Patel'})
    heet = sign_in(api, 'heet', 'heet-pass')
    assert {r['username'] for r in api.get('/api/reviewers', headers=gopi).json()} == {'lisa', 'heet'}
    assert 'heet' not in {r['username'] for r in api.get('/api/reviewers', headers=heet).json()}

    rid = submit_ready_report(api, gopi)
    version = api.get(f'/api/reports/{rid}', headers=gopi).json()['report']['version']
    bad = api.post(f'/reports/{rid}/transition', headers=gopi, json={'version': version, 'action': 'submit', 'reviewer': 'esrat'})
    assert bad.status_code == 400 and 'administrator' in bad.json()['detail']
    sent = api.post(f'/reports/{rid}/transition', headers=gopi, json={'version': version, 'action': 'submit', 'reviewer': 'heet'})
    assert sent.status_code == 200 and sent.json()['reviewer'] == 'heet'

    mine = api.get('/reports?view=mine', headers=gopi).json()[0]
    assert mine['reviewer'] == 'heet' and mine['reviewer_name'] == 'Heet Patel'
    view = api.get(f'/api/reports/{rid}', headers=gopi).json()['report']
    assert view['reviewer_name'] == 'Heet Patel' and view['owner_name'] == 'Gopi Ravula'

    # Only the chosen reviewer gets it; another administrator cannot decide it.
    pending = api.get('/reports?view=pending', headers=heet).json()
    assert [r['id'] for r in pending] == [rid] and pending[0]['owner_name'] == 'Gopi Ravula'
    assert api.get('/reports?view=pending', headers=admin).json() == []
    assert api.get(f'/api/reports/{rid}', headers=admin).json()['workspace']['can_review'] is False
    blocked = api.post(f'/reports/{rid}/transition', headers=admin, json={'version': version + 1, 'action': 'approve',
                                                                           'role': 'Program coordinator', 'confirmed': True})
    assert blocked.status_code == 403 and 'heet' in blocked.json()['detail']
    review = api.get(f'/api/reports/{rid}', headers=heet).json()
    assert review['workspace']['can_review'] is True
    approved = api.post(f'/reports/{rid}/transition', headers=heet, json={'version': review['report']['version'],
                        'action': 'approve', 'role': 'Program coordinator', 'confirmed': True, 'clear': CLEAR_OK})
    assert approved.status_code == 200
    assert api.get('/reports?view=approved', headers=gopi).json()[0]['reviewer_name'] == 'Heet Patel'


def test_admin_report_goes_to_another_person_even_a_member(api, people):
    admin, gopi, esrat = people
    choices = {r['username']: r['role'] for r in api.get('/api/reviewers', headers=admin).json()}
    assert choices == {'gopi': 'member', 'esrat': 'member'}        # members can review an admin's report
    assert {r['username'] for r in api.get('/api/reviewers', headers=gopi).json()} == {'lisa'}

    rid = submit_ready_report(api, admin)
    version = api.get(f'/api/reports/{rid}', headers=admin).json()['report']['version']
    assert 'Choose who' in api.post(f'/reports/{rid}/transition', headers=admin,
                                   json={'version': version, 'action': 'submit'}).json()['detail']
    assert api.post(f'/reports/{rid}/transition', headers=admin,
                    json={'version': version, 'action': 'submit', 'reviewer': 'gopi'}).status_code == 200

    assert [r['id'] for r in api.get('/reports?view=pending', headers=gopi).json()] == [rid]
    assert api.get('/reports?view=pending', headers=esrat).json() == []
    assert api.get(f'/api/reports/{rid}', headers=esrat).status_code == 400
    review = api.get(f'/api/reports/{rid}', headers=gopi).json()
    assert review['workspace']['can_review'] and review['report']['owner'] == 'lisa'
    assert api.post(f'/reports/{rid}/transition', headers=esrat, json={'version': review['report']['version'],
                    'action': 'approve', 'role': 'Program coordinator', 'confirmed': True, 'clear': CLEAR_OK}).status_code == 403
    returned = api.post(f'/reports/{rid}/transition', headers=gopi, json={'version': review['report']['version'],
                        'action': 'return', 'notes': 'Add the course dates.'})
    assert returned.status_code == 200
    mine = api.get('/reports?view=mine', headers=admin).json()[0]
    assert mine['status'] == 'CHANGES REQUESTED' and mine['return_notes'] == 'Add the course dates.'


def test_a_client_secret_is_never_offered_as_the_google_client_id(api, monkeypatch):
    monkeypatch.setenv('GOOGLE_WEB_CLIENT_ID', 'GOCSPX-not-an-id')
    assert api.get('/api/config').json()['google_web_client_id'] == ''
    monkeypatch.setenv('GOOGLE_WEB_CLIENT_ID', '123-abc.apps.googleusercontent.com')
    assert api.get('/api/config').json()['google_web_client_id'] == '123-abc.apps.googleusercontent.com'


def test_report_charts_are_chosen_for_the_data_and_described_in_words(api, people):
    pytest.importorskip('matplotlib')
    pytest.importorskip('reportlab')
    _, gopi, esrat = people
    rid = upload(api, gopi).json()['report']['id']
    ws = api.get(f'/api/reports/{rid}', headers=gopi).json()['workspace']
    for theme in ws['themes']:
        api.post(f'/api/reports/{rid}/themes', headers=gopi, json={'name': theme['name'], 'status': 'confirmed'})
    ws = api.post(f'/api/reports/{rid}/draft', headers=gopi, json={'audience': 'facilitator'}).json()['workspace']
    assert ws['charts_enabled'] and 2 <= len(ws['charts']) <= 4 and all(c.get('reason') for c in ws['charts'])
    assert ws['chart_kinds']['max'] == 4

    image = api.get(f'/api/reports/{rid}/charts/1.png', headers=gopi)
    assert image.status_code == 200 and image.content[:4] == b'\x89PNG'
    assert api.get(f'/api/reports/{rid}/charts/1.png', headers=esrat).status_code == 400

    asked = api.post(f'/api/reports/{rid}/charts/describe', headers=gopi,
                     json={'text': 'box plot of content quality per delivery mode'}).json()
    assert asked['workspace']['charts'][-1]['kind'] == 'group_box'
    assert asked['workspace']['charts'][-1]['measure'] == 'ContentQuality'
    unclear = api.post(f'/api/reports/{rid}/charts/describe', headers=gopi, json={'text': 'something nice'})
    assert unclear.status_code == 400
    count = len(asked['workspace']['charts'])
    ws = api.delete(f'/api/reports/{rid}/charts/0', headers=gopi).json()['workspace']
    assert len(ws['charts']) == count - 1
    ws = api.post(f'/api/reports/{rid}/charts/auto', headers=gopi).json()['workspace']
    assert len(ws['charts']) >= 2

    # Text only: the downloads still fill exactly two pages.
    ws = api.put(f'/api/reports/{rid}/charts/enabled', headers=gopi, json={'enabled': False}).json()['workspace']
    assert ws['charts_enabled'] is False
    pypdf = pytest.importorskip('pypdf')
    from io import BytesIO
    for enabled in (False, True):
        api.put(f'/api/reports/{rid}/charts/enabled', headers=gopi, json={'enabled': enabled})
        pdf = api.get(f'/api/reports/{rid}/export?format=pdf', headers=gopi)
        assert pdf.status_code == 200 and pdf.headers['content-type'] == 'application/pdf'
        assert len(pypdf.PdfReader(BytesIO(pdf.content)).pages) == 2
    word = api.get(f'/api/reports/{rid}/export?format=docx', headers=gopi)
    assert word.status_code == 200 and word.content[:2] == b'PK'


def test_clear_review_questions_send_back_approve_and_oversight(api, people):
    admin, gopi, esrat = people
    rid = submit_ready_report(api, gopi)
    version = api.get(f'/api/reports/{rid}', headers=gopi).json()['report']['version']
    assert api.post(f'/reports/{rid}/transition', headers=gopi,
                    json={'version': version, 'action': 'submit', 'reviewer': 'lisa'}).status_code == 200

    review = api.get(f'/api/reports/{rid}', headers=admin).json()
    examine = review['workspace']['clear']['examine']
    assert [q['id'] for q in examine['questions']] == ['faithful', 'balanced', 'owned']
    assert len(examine['comments']) == 5 and examine['claim'] and examine['counter']['text']
    assert 'examine' not in api.get(f'/api/reports/{rid}', headers=gopi).json()['workspace']['clear']
    assert api.post(f'/api/reports/{rid}/review/start', headers=gopi).status_code == 403
    assert api.post(f'/api/reports/{rid}/review/start', headers=admin).status_code == 200

    # Missing answers are refused; the owned priority must be in the reviewer's own words.
    base = {'version': review['report']['version'], 'action': 'approve', 'role': 'Program coordinator'}
    missing = api.post(f'/reports/{rid}/transition', headers=admin, json={**base, 'clear': {'faithful': 'yes'}})
    assert missing.status_code == 400 and 'Balanced' in missing.json()['detail']
    short = api.post(f'/reports/{rid}/transition', headers=admin,
                     json={**base, 'clear': {**CLEAR_OK, 'owned': 'ok'}})
    assert short.status_code == 400 and 'own words' in short.json()['detail']
    assert api.post(f'/reports/{rid}/transition', headers=admin, json=base).status_code == 400

    # "Partly" on faithful sends it back with the reviewer's note.
    returned = api.post(f'/reports/{rid}/transition', headers=admin, json={**base, 'clear': {
        **CLEAR_OK, 'faithful': 'partly', 'faithful_note': 'Online learners were less happy than the summary says.'}})
    assert returned.status_code == 200, returned.text
    ws = api.get(f'/api/reports/{rid}', headers=gopi).json()['workspace']
    assert ws['workflow']['status'] == 'CHANGES REQUESTED'
    assert 'Online learners were less happy' in ws['workflow']['events'][-1]['notes']

    # Resubmit; this time it is approved with a caveat and the reviewer's own priority.
    version = api.get(f'/api/reports/{rid}', headers=gopi).json()['report']['version']
    api.post(f'/reports/{rid}/transition', headers=gopi, json={'version': version, 'action': 'submit', 'reviewer': 'lisa'})
    review = api.get(f'/api/reports/{rid}', headers=admin).json()
    approved = api.post(f'/reports/{rid}/transition', headers=admin, json={
        'version': review['report']['version'], 'action': 'approve', 'role': 'Program coordinator',
        'clear': {**CLEAR_OK, 'balanced': 'caveat', 'caveat': 'Online groups rated satisfaction lower than others.'}})
    assert approved.status_code == 200, approved.text
    markdown = api.get(f'/api/reports/{rid}/export?format=md', headers=gopi).text
    assert '## Reviewer notes' in markdown and "Reviewer's priority (lisa)" in markdown
    assert 'Caveat: Online groups rated satisfaction lower' in markdown
    assert 'CLEAR review: standard level, 3 questions answered' in markdown

    # The oversight panel is for administrators only and is built from the audit chain.
    assert api.get('/api/oversight', headers=gopi).status_code == 403
    panel = api.get('/api/oversight', headers=admin).json()
    assert panel['totals']['reviews'] == 2 and panel['totals']['returned_percent'] == 50
    lisa = next(r for r in panel['reviewers'] if r['reviewer'] == 'lisa')
    assert lisa['approved'] == 1 and lisa['returned'] == 1 and lisa['concern_rate'] == 100
    assert panel['recent'][0]['decision'] == 'Approved' and panel['recent'][0]['title'] == 'Leadership course'
    assert panel['recent'][0]['seconds'] is not None


def test_client_reports_need_the_two_extra_questions(api, people):
    admin, gopi, _ = people
    rid = upload(api, gopi).json()['report']['id']
    ws = api.get(f'/api/reports/{rid}', headers=gopi).json()['workspace']
    for theme in ws['themes']:
        api.post(f'/api/reports/{rid}/themes', headers=gopi, json={'name': theme['name'], 'status': 'confirmed'})
    ws = api.post(f'/api/reports/{rid}/draft', headers=gopi, json={'audience': 'client', 'charts': False}).json()['workspace']
    assert ws['clear']['level']['level'] == 'high' and len(ws['clear']['level']['questions']) == 5
    assert ws['charts_enabled'] is False
    version = api.get(f'/api/reports/{rid}', headers=gopi).json()['report']['version']
    api.post(f'/reports/{rid}/transition', headers=gopi, json={'version': version, 'action': 'submit', 'reviewer': 'lisa'})
    review = api.get(f'/api/reports/{rid}', headers=admin).json()
    base = {'version': review['report']['version'], 'action': 'approve', 'role': 'Learning Futures lead'}
    no_fit = api.post(f'/reports/{rid}/transition', headers=admin, json={**base, 'clear': {
        k: v for k, v in CLEAR_OK.items() if k != 'fit'}})
    assert no_fit.status_code == 400 and 'Fit for the audience' in no_fit.json()['detail']
    ok = api.post(f'/reports/{rid}/transition', headers=admin, json={**base, 'clear': {
        **CLEAR_OK, 'fair': 'yes', 'fairness_note': 'Results for small cohorts should not be used on their own.'}})
    assert ok.status_code == 200, ok.text
    pdf = api.get(f'/api/reports/{rid}/export?format=pdf', headers=gopi)
    pypdf = pytest.importorskip('pypdf')
    from io import BytesIO
    reader = pypdf.PdfReader(BytesIO(pdf.content))
    text = ''.join(page.extract_text() for page in reader.pages)
    assert len(reader.pages) == 2 and "Reviewer's priority" in text and 'Fairness note' not in text
    assert 'Reviewer caveat: Results for small cohorts' in text
