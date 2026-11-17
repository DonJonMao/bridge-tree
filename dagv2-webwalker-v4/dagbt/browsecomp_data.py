"""Pinned BrowseComp-Plus data, with references outside the generation inputs.

The fixed corpus is searched locally with SQLite FTS5 BM25.  Document text is
stored losslessly; scores and snippets are retrieval hints, never evidence
labels.  Only the offline preparer needs a parquet reader.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sqlite3
import zlib

QUERY_REVISION = '144cff8e35b5eaef7e526346aa60774a9deb941f'
CORPUS_REVISION = 'b27b02bc3e45511b8b82a13e6f90ce761df726f6'
SCHEMA = 'browsecomp_plus_fixed_corpus_v1'
QUERY_COUNT = 830
DOCUMENT_COUNT = 100195


def _safe_query_id(value):
    return (isinstance(value, str) and value not in ('.', '..')
            and re.fullmatch(r'[A-Za-z0-9_.-]+', value) is not None)


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    indent=2) + '\n', encoding='utf-8')


def _manifest(directory, allow_fixture=False):
    manifest = json.loads((Path(directory) / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != SCHEMA:
        raise ValueError('Unrecognized BrowseComp-Plus data manifest')
    if manifest.get('fixture'):
        if not allow_fixture:
            raise ValueError('A test fixture cannot replace the official BrowseComp-Plus dataset')
    elif (manifest.get('query_revision') != QUERY_REVISION
          or manifest.get('corpus_revision') != CORPUS_REVISION
          or manifest.get('questions') != QUERY_COUNT
          or manifest.get('documents') != DOCUMENT_COUNT):
        raise ValueError('BrowseComp-Plus must use the pinned complete official dataset')
    return manifest


def _checked_file(directory, name, expected):
    path = Path(directory) / name
    if not isinstance(expected, str) or file_hash(path) != expected:
        raise ValueError('Prepared BrowseComp-Plus file changed: ' + name)
    return path


def load_questions(directory, *, allow_fixture=False):
    """Load only question text and native official query IDs, never references."""
    manifest = _manifest(directory, allow_fixture)
    path = _checked_file(directory, 'questions.jsonl', manifest.get('questions_sha256'))
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if (len(rows) != manifest['questions']
            or len({row.get('id') for row in rows}) != len(rows)):
        raise ValueError('Missing/duplicate BrowseComp-Plus questions')
    for row in rows:
        if (set(row) != {'id', 'question'}
                or not _safe_query_id(row.get('id'))
                or any(not isinstance(row.get(k), str) or not row[k].strip()
                       for k in ('id', 'question'))):
            raise ValueError('Only id and question are permitted in generation inputs')
    return rows, manifest


def load_references(directory, *, allow_fixture=False):
    """Evaluation only: call after the complete generation stage has ended."""
    manifest = _manifest(directory, allow_fixture)
    path = _checked_file(directory, 'evaluation_only.json', manifest.get('evaluation_sha256'))
    references = json.loads(path.read_text(encoding='utf-8'))
    if len(references) != manifest['questions']:
        raise ValueError('Incomplete BrowseComp-Plus evaluation references')
    for qid, row in references.items():
        if (not _safe_query_id(qid)
                or set(row) != {'answer', 'evidence_doc_ids', 'gold_doc_ids'}
                or not isinstance(row['answer'], str) or not row['answer'].strip()
                or any(not isinstance(row[k], list)
                       or any(not isinstance(docid, str) or not docid for docid in row[k])
                       for k in ('evidence_doc_ids', 'gold_doc_ids'))):
            raise ValueError('Invalid BrowseComp-Plus evaluation reference')
    return references


def _identity(path, sha256):
    stat = path.stat()
    return {'path': str(path.resolve()), 'sha256': sha256, 'size': stat.st_size,
            'mtime_ns': stat.st_mtime_ns, 'inode': stat.st_ino, 'device': stat.st_dev}


def verify_corpus(directory, *, allow_fixture=False):
    """Hash and structurally check the corpus once before spawning task workers.

    The returned receipt authorizes subsequent read-only opens of the same file
    identity.  A receipt is never a replacement for this first full hash check.
    """
    directory = Path(directory).resolve()
    manifest = _manifest(directory, allow_fixture)
    path = directory / 'corpus.sqlite3'
    before = _identity(path, manifest.get('corpus_sha256'))
    _checked_file(directory, 'corpus.sqlite3', manifest.get('corpus_sha256'))
    after = _identity(path, manifest['corpus_sha256'])
    if before != after:
        raise ValueError('Corpus changed during cryptographic verification')
    connection = sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)
    try:
        if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('Prepared corpus SQLite integrity check failed')
        if connection.execute('SELECT count(*) FROM documents').fetchone()[0] != manifest['documents']:
            raise ValueError('Prepared corpus is incomplete')
        if connection.execute('SELECT count(*) FROM corpus_fts').fetchone()[0] != manifest['documents']:
            raise ValueError('Prepared corpus search index is incomplete')
    finally:
        connection.close()
    if after != _identity(path, manifest['corpus_sha256']):
        raise ValueError('Corpus changed during structural verification')
    return after


def prepare(questions, documents, directory, *, fixture=False, sources=None, progress=None):
    """Build a complete immutable dataset from official decoded source records.

    ``fixture=True`` is deliberately explicit and rejected by production loads.
    Source iterators may download, validate and discard one parquet shard at a
    time.  A manifest is published only after both complete iterators validate.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if any((directory / name).exists() for name in
           ('manifest.json', 'corpus.sqlite3', 'corpus.sqlite3.partial')):
        raise ValueError('Refusing to replace an existing prepared corpus')
    generation, references = [], {}
    for row in questions:
        qid, question, answer = (row.get(k) for k in ('query_id', 'query', 'answer'))
        if any(not isinstance(value, str) or not value.strip() for value in (qid, question, answer)):
            raise ValueError('Invalid BrowseComp-Plus question record')
        if not _safe_query_id(qid):
            raise ValueError('BrowseComp-Plus query IDs must be safe single path components')
        if qid in references:
            raise ValueError('Duplicate BrowseComp-Plus query ID')
        refs = {}
        for field in ('evidence', 'gold'):
            ids = row.get(field + '_doc_ids')
            if ids is None:
                ids = [doc['docid'] for doc in row.get(field + '_docs', [])]
            if not isinstance(ids, list) or any(not isinstance(x, str) or not x for x in ids):
                raise ValueError('Invalid BrowseComp-Plus relevance document IDs')
            refs[field + '_doc_ids'] = list(dict.fromkeys(ids))
        generation.append({'id': qid, 'question': question})
        references[qid] = {'answer': answer, **refs}
    if not generation or (not fixture and len(generation) != QUERY_COUNT):
        raise ValueError('The official BrowseComp-Plus split must contain all 830 queries')
    pending = directory / 'corpus.sqlite3.partial'
    connection = sqlite3.connect(pending)
    count = 0
    try:
        connection.executescript('''
            PRAGMA journal_mode=OFF;
            PRAGMA synchronous=OFF;
            PRAGMA temp_store=MEMORY;
            PRAGMA cache_size=-65536;
            CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE documents (
                docid TEXT NOT NULL UNIQUE, url TEXT NOT NULL,
                body BLOB NOT NULL, text_sha256 TEXT NOT NULL);
            CREATE VIRTUAL TABLE corpus_fts USING fts5(
                text, content='', tokenize='porter unicode61 remove_diacritics 2');
        ''')
        for document in documents:
            docid, url, text = (document.get(k) for k in ('docid', 'url', 'text'))
            if (not isinstance(docid, str) or not docid.strip()
                    or not isinstance(url, str) or not isinstance(text, str)):
                raise ValueError('Invalid BrowseComp-Plus corpus record')
            encoded = text.encode('utf-8')
            try:
                cursor = connection.execute(
                    'INSERT INTO documents(docid,url,body,text_sha256) VALUES(?,?,?,?)',
                    (docid, url, zlib.compress(encoded), hashlib.sha256(encoded).hexdigest()))
            except sqlite3.IntegrityError as error:
                raise ValueError('Duplicate BrowseComp-Plus corpus document ID') from error
            connection.execute('INSERT INTO corpus_fts(rowid,text) VALUES(?,?)',
                               (cursor.lastrowid, text))
            count += 1
            if count % 500 == 0:
                connection.commit()
                if progress:
                    progress(count)
        if not count or (not fixture and count != DOCUMENT_COUNT):
            raise ValueError('The official BrowseComp-Plus corpus must contain all 100195 documents')
        for ref in references.values():
            for docid in set(ref['evidence_doc_ids'] + ref['gold_doc_ids']):
                if connection.execute('SELECT 1 FROM documents WHERE docid=?', (docid,)).fetchone() is None:
                    raise ValueError('A relevance reference points outside the complete corpus')
        metadata = {'schema': SCHEMA, 'query_revision': QUERY_REVISION,
                    'corpus_revision': CORPUS_REVISION, 'documents': count,
                    'fixture': bool(fixture)}
        connection.executemany('INSERT INTO metadata(key,value) VALUES(?,?)',
                               [(k, json.dumps(v)) for k, v in metadata.items()])
        connection.execute("INSERT INTO corpus_fts(corpus_fts) VALUES('optimize')")
        connection.commit()
        if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('Prepared BrowseComp-Plus SQLite integrity check failed')
    finally:
        connection.close()
    pending.rename(directory / 'corpus.sqlite3')
    questions_path = directory / 'questions.jsonl'
    questions_path.write_text(''.join(json.dumps(row, ensure_ascii=False) + '\n'
                                      for row in generation), encoding='utf-8')
    _save(directory / 'evaluation_only.json', references)
    manifest = {'schema': SCHEMA, 'fixture': bool(fixture),
                'query_repository': 'Tevatron/browsecomp-plus',
                'query_revision': QUERY_REVISION,
                'corpus_repository': 'Tevatron/browsecomp-plus-corpus',
                'corpus_revision': CORPUS_REVISION,
                'questions': len(generation), 'documents': count,
                'generation_fields': ['id', 'question'],
                'evaluation_only_fields': ['answer', 'evidence_doc_ids', 'gold_doc_ids'],
                'retriever': 'sqlite_fts5_bm25_porter_unicode61_v1',
                'source_shards': sources or [],
                'questions_sha256': file_hash(questions_path),
                'evaluation_sha256': file_hash(directory / 'evaluation_only.json'),
                'corpus_sha256': file_hash(directory / 'corpus.sqlite3')}
    _save(directory / 'manifest.json', manifest)
    return manifest


class Corpus:
    """Read-only corpus; opening and querying it never opens evaluation files."""

    def __init__(self, directory_or_db, *, allow_fixture=False, verify=True, receipt=None):
        target = Path(directory_or_db).resolve()
        directory = target if target.is_dir() else target.parent
        manifest = _manifest(directory, allow_fixture)
        path = directory / 'corpus.sqlite3'
        if target.is_file() and target != path:
            raise ValueError('Expected the manifested corpus.sqlite3')
        if verify:
            receipt = verify_corpus(directory, allow_fixture=allow_fixture)
        elif not isinstance(receipt, dict):
            raise ValueError('Skipping a corpus hash requires a prior verification receipt')
        if receipt != _identity(path, manifest.get('corpus_sha256')):
            raise ValueError('Corpus no longer matches its cryptographic verification receipt')
        self.connection = sqlite3.connect(path.as_uri() + '?mode=ro&immutable=1', uri=True)
        try:
            metadata = {key: json.loads(value) for key, value in
                        self.connection.execute('SELECT key,value FROM metadata')}
            if (metadata.get('schema') != SCHEMA
                    or metadata.get('documents') != manifest['documents']
                    or metadata.get('fixture') != manifest.get('fixture', False)):
                raise ValueError('Corpus metadata does not match its data manifest')
        except Exception:
            self.connection.close()
            raise
        self.manifest = manifest

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def get(self, docid):
        row = self.connection.execute('SELECT docid,url,body,text_sha256 FROM documents WHERE docid=?',
                                      (docid,)).fetchone()
        if row is None:
            raise KeyError('Unknown corpus document ID: ' + str(docid))
        encoded = zlib.decompress(row[2])
        if hashlib.sha256(encoded).hexdigest() != row[3]:
            raise ValueError('Corpus document text hash mismatch')
        return {'docid': row[0], 'url': row[1], 'text': encoded.decode('utf-8'),
                'text_sha256': row[3]}

    def search(self, query, top_k=5, *, offset=0, exclude_doc_ids=()):
        """Stable lexical BM25 retrieval with exact original-text snippets.

        Caller input is tokenized and quoted, rather than interpreted as FTS
        syntax.  Pagination and exclusions expose further ranked results without
        silently choosing new queries or consulting relevance labels.
        """
        if not isinstance(query, str):
            raise ValueError('Search query must be text')
        if (isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 100
                or isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 100195):
            raise ValueError('Search requires 1..100 results and a bounded nonnegative offset')
        if isinstance(exclude_doc_ids, str):
            raise ValueError('Document exclusions must be a sequence of IDs')
        excluded = tuple(dict.fromkeys(exclude_doc_ids))
        if len(excluded) > 2000 or any(not isinstance(x, str) for x in excluded):
            raise ValueError('Invalid/oversized document exclusions')
        terms = list(dict.fromkeys(re.findall(r'[^\W_]+', query[:8192].lower(), re.UNICODE)))[:64]
        if not terms:
            return []
        expression = ' OR '.join('"' + term.replace('"', '""') + '"' for term in terms)
        sql = ('SELECT d.docid, bm25(corpus_fts) AS rank FROM corpus_fts '
               'JOIN documents d ON d.rowid=corpus_fts.rowid WHERE corpus_fts MATCH ?')
        parameters = [expression]
        if excluded:
            sql += ' AND d.docid NOT IN (' + ','.join('?' for _ in excluded) + ')'
            parameters.extend(excluded)
        sql += ' ORDER BY rank ASC,d.docid ASC LIMIT ? OFFSET ?'
        parameters.extend((top_k, offset))
        rows = self.connection.execute(sql, parameters).fetchall()
        pattern = re.compile(r'(?<!\w)(?:' + '|'.join(re.escape(t) for t in terms) + r')(?!\w)', re.I)
        result = []
        for docid, rank in rows:
            document = self.get(docid)
            text = document['text']
            match = pattern.search(text)
            start = max(0, match.start() - 150) if match else 0
            end = min(len(text), start + 1200)
            result.append({'docid': docid, 'url': document['url'], 'score': -float(rank),
                           'snippet': text[start:end], 'start': start, 'end': end})
        return result
