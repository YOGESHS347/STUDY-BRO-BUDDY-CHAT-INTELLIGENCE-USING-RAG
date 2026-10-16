import json
from collections import defaultdict

with open('logs/baseline_benchmark.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

results = data['results']
print(f"Loaded {len(results)} benchmark results.\n")

out_lines = []
out_lines.append('='*70)
out_lines.append('INVESTIGATING CONCEPT COVERAGE (< 1.0):')
out_lines.append('='*70)
for r in results:
    if r.get('concepts_expected') and r.get('concept_coverage', 1.0) < 1.0:
        missing = set(r['concepts_expected']) - set(r.get('concepts_found', []))
        out_lines.append(f"[{r['id']}] Category: {r['category']}")
        out_lines.append(f"  Query: '{r['query']}'")
        out_lines.append(f"  Top Source: {r['top_source']} (p.{r.get('top_page')}) | Score: {r.get('top_rerank_score'):.4f}")
        found_cnt = len(r.get('concepts_found', []))
        exp_cnt = len(r['concepts_expected'])
        cov = r.get('concept_coverage', 0.0)
        out_lines.append(f"  Coverage: {cov:.2f} ({found_cnt}/{exp_cnt})")
        out_lines.append(f"  Found: {r.get('concepts_found', [])}")
        out_lines.append(f"  Missing: {list(missing)}")
        out_lines.append('-'*60)

with open('tests/evaluation/audit_coverage_utf8.txt', 'w', encoding='utf-8') as f_out:
    f_out.write('\n'.join(out_lines))
print('Saved audit_coverage_utf8.txt successfully.')
print('='*70)
for r in results:
    print(f"ID: {r['id']:<3} | Cat: {r['category']:<26} | TopDoc: {str(r.get('top_source')):<35} | Pg: {str(r.get('top_page')):<5} | Sem: {r.get('top_semantic_score', 0):.4f} | Rerank: {r.get('top_rerank_score', 0):.4f} | Lat: {r.get('total_latency_ms', 0):.2f}ms | Refusal: {r.get('is_refusal')} | Query: '{r['query']}'")
