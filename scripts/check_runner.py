import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import app  # Lee la configuración local .env.
from revisor.documents import ingest_submission
from revisor.runner import run_checks

example = Path(__file__).resolve().parents[1] / 'examples' / 'compiscript-ejemplo.zip'
submission = ingest_submission(example.name, example.read_bytes())
result = run_checks(submission['runner_files'])
print(json.dumps(result, ensure_ascii=False, indent=2))
sys.exit(0 if result.get('executed') and all(c['passed'] for c in result['cases']) else 1)
