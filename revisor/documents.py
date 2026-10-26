"""Lectura acotada de archivos; jamás importa ni ejecuta el contenido cargado."""
import base64
import io
import stat
import zipfile
from pathlib import PurePosixPath

MAX_UPLOAD = 80 * 1024 * 1024
MAX_MEMBER = 512 * 1024
MAX_TEXT = 140_000
SKIP = {'.git', '.venv', 'venv', 'node_modules', '__pycache__', '__MACOSX',
        '.pytest_cache', 'dist', 'build'}
TEXT_EXT = {'.py', '.ts', '.tsx', '.js', '.jsx', '.css', '.html', '.md',
            '.txt', '.json', '.g4', '.cps', '.toml', '.yaml', '.yml'}


def safe_parts(name):
    if '\\' in name or '\x00' in name:
        raise ValueError('El ZIP contiene una ruta inválida.')
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or any(':' in p for p in path.parts):
        raise ValueError('El ZIP contiene una ruta fuera del proyecto.')
    return path.parts


def pdf_text(data):
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted or len(reader.pages) > 100:
        raise ValueError('Usa un PDF sin contraseña de hasta 100 páginas.')
    result = []
    total = 0
    for page in reader.pages:
        text = page.extract_text() or ''
        total += len(text)
        if total > 300_000:
            raise ValueError('El PDF contiene demasiado texto para esta versión.')
        result.append(text)
    value = '\n\n'.join(result).strip()
    if not value:
        raise ValueError('No se encontró texto en el PDF. Esta versión no incluye OCR.')
    return value


def read_upload(upload):
    name = str(upload.get('name', ''))
    encoded = upload.get('data', '')
    if not isinstance(encoded, str) or len(encoded) > (MAX_UPLOAD * 4 // 3 + 8):
        raise ValueError('El archivo supera 80 MiB.')
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError('Archivo codificado incorrectamente.') from exc
    if not data or len(data) > MAX_UPLOAD:
        raise ValueError('El archivo está vacío o supera 80 MiB.')
    return name, data


def plain_document(name, data):
    extension = PurePosixPath(name).suffix.lower()
    if extension == '.pdf':
        return pdf_text(data)
    if extension not in TEXT_EXT:
        raise ValueError('Formato no admitido. Usa PDF con texto, TXT, MD o archivos de código.')
    return data.decode('utf-8-sig', errors='replace')


def priority(item):
    name = item[0].lower()
    # Primero puntos de integración y pruebas
    preferred = ['compiler.py', 'app.tsx', 'emitter.py', 'test_analyze.py',
                 'generate.sh', 'compiscript.g4', 'readme.md', 'requirements.txt']
    return (next((i for i, p in enumerate(preferred) if name.endswith(p)), 30),
            0 if '/src/' in name else 1, name)


def ingest_submission(name, data):
    warnings, candidates, runner_files = [], [], {}
    skipped = 0
    if PurePosixPath(name).suffix.lower() != '.zip':
        text = plain_document(name, data)
        candidates = [(PurePosixPath(name).name, text)]
    else:
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as exc:
            raise ValueError('El ZIP no es válido.') from exc
        with archive:
            infos = archive.infolist()
            if len(infos) > 20_000 or sum(i.file_size for i in infos) > 512 * 1024 * 1024:
                raise ValueError('ZIP demasiado grande: máximo 20 000 entradas y 512 MiB descomprimidos.')
            seen = set()
            runner_bytes = 0
            for info in infos:
                parts = safe_parts(info.filename)
                if info.filename in seen:
                    raise ValueError('El ZIP contiene rutas duplicadas.')
                seen.add(info.filename)
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode):
                    skipped += 1
                    continue
                if info.is_dir():
                    continue
                if any(p in SKIP or p.startswith('.') for p in parts):
                    skipped += 1
                    continue
                suffix = PurePosixPath(info.filename).suffix.lower()
                if info.flag_bits & 1:
                    raise ValueError('El ZIP incluye archivos cifrados.')
                if info.file_size > MAX_MEMBER or info.file_size > max(1, info.compress_size) * 1000:
                    skipped += 1
                    continue
                is_source = suffix == '.py' and 'src' in parts
                is_text = suffix in TEXT_EXT or parts[-1] in {'Makefile', 'generate.sh'}
                if not is_text:
                    skipped += 1
                    continue
                raw = archive.read(info)
                text = raw.decode('utf-8-sig', errors='replace')
                if is_source:
                    src_index = parts.index('src')
                    relative = '/'.join(parts[src_index:])
                    if relative in runner_files:
                        raise ValueError('Hay más de un árbol src compatible. Carga un solo proyecto.')
                    runner_bytes += len(raw)
                    if runner_bytes > 4 * 1024 * 1024 or len(runner_files) >= 200:
                        raise ValueError('El código Python supera el límite de ejecución de este prototipo.')
                    runner_files[relative] = raw
                if 'generated' in parts:
                    skipped += 1
                    continue
                candidates.append((info.filename, text))
    documents = []
    remaining = MAX_TEXT
    for path, text in sorted(candidates, key=priority):
        if remaining <= 0 or len(documents) >= 100:
            skipped += 1
            continue
        selected = text[:remaining]
        truncated = len(selected) < len(text)
        documents.append({'path': path, 'text': selected, 'truncated': truncated,
                          'lines': len(selected.splitlines())})
        remaining -= len(selected)
        if truncated:
            warnings.append(f'Se recortó {path}; solo se analiza el comienzo.')
    if not documents:
        raise ValueError('No hay documentos o código de texto admitidos en la entrega.')
    if skipped:
        warnings.append(f'{skipped} archivos omitidos (dependencias, generados, binarios o límites). '
                        'La revisión solo cubre los archivos enumerados.')
    return {'documents': documents, 'warnings': warnings, 'skipped': skipped,
            'runner_files': runner_files,
            'runner_compatible': all(p in runner_files for p in
                ['src/compiler.py', 'src/generated/CompiscriptLexer.py',
                 'src/generated/CompiscriptParser.py'])}


def context_documents(documents):
    return [{'path': d['path'], 'truncated': d['truncated'],
             'content': '\n'.join(f'{i}: {line}' for i, line in enumerate(d['text'].splitlines(), 1))}
            for d in documents]
