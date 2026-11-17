import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sqlite3

import pytest

from dagbt.browsecomp_data import (Corpus, file_hash, load_questions, load_references,
                                 prepare, verify_corpus)


def records():
    questions = [{'query_id': 'q-1', 'query': 'Which café launched the Artemis project?',
                  'answer': 'A fixture answer', 'evidence_doc_ids': ['doc-a'],
                  'gold_doc_ids': ['doc-a']}]
    documents = [
        {'docid': 'doc-a', 'url': 'https://fixture.invalid/a',
         'text': 'Header\n\nThe café launched Artemis in 2024.\nExact punctuation: “é”!\n'},
        {'docid': 'doc-b', 'url': 'https://fixture.invalid/b',
         'text': 'Artemis is a project. Unrelated additional text.'},
        {'docid': 'doc-c', 'url': 'https://fixture.invalid/c',
         'text': 'Artemis is a project. Unrelated additional text.'}]
    return questions, documents


@pytest.fixture
def dataset(tmp_path):
    questions, documents = records()
    prepare(questions, documents, tmp_path, fixture=True)
    return tmp_path


def test_prepared_generation_and_references_are_separate(dataset):
    rows, manifest = load_questions(dataset, allow_fixture=True)
    assert rows == [{'id': 'q-1', 'question': records()[0][0]['query']}]
    assert manifest['questions'] == 1 and manifest['documents'] == 3
    references = load_references(dataset, allow_fixture=True)
    assert references['q-1']['evidence_doc_ids'] == ['doc-a']
    assert references['q-1']['gold_doc_ids'] == ['doc-a']
    (dataset / 'evaluation_only.json').unlink()
    assert load_questions(dataset, allow_fixture=True)[0] == rows
    with Corpus(dataset, allow_fixture=True) as corpus:
        assert corpus.search('Artemis')


def test_fixtures_require_explicit_runtime_opt_in(dataset):
    for action in (lambda: load_questions(dataset), lambda: load_references(dataset),
                   lambda: Corpus(dataset), lambda: verify_corpus(dataset)):
        with pytest.raises(ValueError, match='fixture'):
            action()


def test_corpus_lossless_full_text_hash_and_exact_unicode_snippets(dataset):
    with Corpus(dataset, allow_fixture=True) as corpus:
        document = corpus.get('doc-a')
        assert document['text'] == records()[1][0]['text']
        assert document['text_sha256'] == hashlib.sha256(document['text'].encode('utf-8')).hexdigest()
        for hit in corpus.search('café OR "Artemis" near:evil*'):
            original = corpus.get(hit['docid'])['text']
            assert original[hit['start']:hit['end']] == hit['snippet']
        with pytest.raises(KeyError):
            corpus.get('../../evaluation_only.json')
        with pytest.raises(sqlite3.OperationalError, match='readonly'):
            corpus.connection.execute("DELETE FROM documents")


def test_search_stable_pagination_exclusions_and_empty_input(dataset):
    with Corpus(dataset, allow_fixture=True) as corpus:
        hits = corpus.search('Artemis', top_k=3)
        assert len(hits) == 3
        assert hits == corpus.search('Artemis', top_k=3)
        assert corpus.search('Artemis', top_k=1, offset=1)[0] == hits[1]
        assert corpus.search('Artemis', top_k=3, exclude_doc_ids=[hits[0]['docid']]) == hits[1:]
        tied = [hit['docid'] for hit in hits if hit['docid'] in ('doc-b', 'doc-c')]
        assert tied == ['doc-b', 'doc-c']
        assert corpus.search(' " - () *** ') == []
        with pytest.raises(ValueError):
            corpus.search('Artemis', top_k=101)
        with pytest.raises(ValueError):
            corpus.search('Artemis', offset=-1)
        with pytest.raises(ValueError):
            corpus.search('Artemis', exclude_doc_ids='doc-a')


def test_verified_receipt_avoids_rehash_and_is_bound_to_file(dataset, monkeypatch):
    receipt = verify_corpus(dataset, allow_fixture=True)
    assert receipt['sha256'] == file_hash(dataset / 'corpus.sqlite3')
    monkeypatch.setattr('dagbt.browsecomp_data.file_hash',
                        lambda path: pytest.fail('A verified worker should not rehash the database'))
    with Corpus(dataset, allow_fixture=True, verify=False, receipt=receipt) as corpus:
        assert corpus.get('doc-a')['docid'] == 'doc-a'
    with pytest.raises(ValueError, match='requires'):
        Corpus(dataset, allow_fixture=True, verify=False)
    with pytest.raises(ValueError, match='receipt'):
        Corpus(dataset, allow_fixture=True, verify=False, receipt={**receipt, 'size': 0})


def test_questions_and_references_detect_modification(dataset):
    (dataset / 'questions.jsonl').write_text('{"id":"q-1","question":"changed"}\n')
    with pytest.raises(ValueError, match='changed'):
        load_questions(dataset, allow_fixture=True)
    (dataset / 'evaluation_only.json').write_text('{}')
    with pytest.raises(ValueError, match='changed'):
        load_references(dataset, allow_fixture=True)


def test_generation_rejects_oracle_fields_even_with_updated_file_hash(dataset):
    path = dataset / 'questions.jsonl'
    row = json.loads(path.read_text())
    row['answer'] = 'forbidden'
    path.write_text(json.dumps(row) + '\n')
    manifest_path = dataset / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['questions_sha256'] = file_hash(path)
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match='Only id and question'):
        load_questions(dataset, allow_fixture=True)


def test_corpus_hash_detects_corruption(dataset):
    path = dataset / 'corpus.sqlite3'
    with path.open('r+b') as stream:
        stream.seek(-1, 2)
        byte = stream.read(1)
        stream.seek(-1, 2)
        stream.write(bytes([byte[0] ^ 1]))
    with pytest.raises(ValueError, match='changed'):
        Corpus(dataset, allow_fixture=True)


def test_prepare_rejects_duplicates_and_missing_evidence(tmp_path):
    questions, documents = records()
    with pytest.raises(ValueError, match='Duplicate.*query'):
        prepare(questions + questions, documents, tmp_path / 'q', fixture=True)
    with pytest.raises(ValueError, match='Duplicate.*document'):
        prepare(questions, documents + documents[:1], tmp_path / 'd', fixture=True)
    with pytest.raises(ValueError, match='outside'):
        prepare(questions, documents[1:], tmp_path / 'missing', fixture=True)
    assert not (tmp_path / 'missing/manifest.json').exists()


def test_prepare_default_requires_complete_official_split(tmp_path):
    questions, documents = records()
    with pytest.raises(ValueError, match='830'):
        prepare(questions, documents, tmp_path)


@pytest.mark.parametrize('unsafe', ['../escape', '.', '..', 'a/b', 'a\\b', 'a\x00b'])
def test_query_ids_cannot_escape_task_directories(tmp_path, unsafe):
    questions, documents = records()
    questions[0]['query_id'] = unsafe
    with pytest.raises(ValueError, match='safe single path'):
        prepare(questions, documents, tmp_path, fixture=True)


@pytest.fixture
def preparer():
    path = Path(__file__).resolve().parents[1] / 'scripts/prepare_browsecomp_plus.py'
    spec = importlib.util.spec_from_file_location('browsecomp_preparer_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DownloadResponse(io.BytesIO):
    def __init__(self, body, status=200, content_range=None):
        super().__init__(body)
        self.status = status
        self.headers = {'Content-Range': content_range} if content_range else {}


def download_source():
    return {'repository': 'fixture/repo', 'revision': 'fixture', 'path': 'data/fixture.parquet',
            'bytes': 5, 'sha256': hashlib.sha256(b'abcde').hexdigest()}


def test_short_http_eof_resumes_partial_and_verifies_full_hash(tmp_path, preparer, monkeypatch):
    requests = []
    responses = iter([DownloadResponse(b'ab'),
                      DownloadResponse(b'cde', 206, 'bytes 2-4/5')])

    def open_response(request, **kwargs):
        requests.append(request)
        return next(responses)

    monkeypatch.setattr(preparer, 'urlopen', open_response)
    monkeypatch.setattr(preparer.time, 'sleep', lambda seconds: None)
    path = preparer.download(download_source(), tmp_path)
    assert path.read_bytes() == b'abcde'
    assert requests[1].get_header('Range') == 'bytes=2-'
    assert not path.with_suffix('.part').exists()


def test_resume_rejects_wrong_range_before_appending(tmp_path, preparer, monkeypatch):
    part = tmp_path / 'repo_fixture.part'
    part.write_bytes(b'ab')
    monkeypatch.setattr(preparer, 'urlopen',
                        lambda *args, **kwargs: DownloadResponse(b'abcde', 206, 'bytes 0-4/5'))
    with pytest.raises(ValueError, match='Content-Range'):
        preparer.download(download_source(), tmp_path)
    assert part.read_bytes() == b'ab'


def test_complete_download_hash_mismatch_is_never_accepted(tmp_path, preparer, monkeypatch):
    monkeypatch.setattr(preparer, 'urlopen', lambda *args, **kwargs: DownloadResponse(b'abXde'))
    with pytest.raises(ValueError, match='SHA256'):
        preparer.download(download_source(), tmp_path)
    assert not (tmp_path / 'repo_fixture.parquet').exists()
